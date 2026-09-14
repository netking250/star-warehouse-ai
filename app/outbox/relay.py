"""Concurrent-safe transactional outbox relay."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import cast

from opentelemetry import trace
from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.context.pii_filter import pii_filter
from app.core.database import async_session_maker
from app.core.utils import utc_now
from app.models.outbox import OutboxEvent, OutboxStatus
from app.observability.metrics import record_outbox_publish
from app.outbox.publisher import TaskPublisher
from app.task_runtime.binding import bind_task_context
from app.task_runtime.envelope import TaskEnvelope

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


@dataclass(frozen=True)
class RelayBatchResult:
    """Counts produced by one bounded relay pass."""

    claimed: int
    published: int
    failed: int


@dataclass(frozen=True)
class _ClaimedEvent:
    event_id: uuid.UUID
    tenant_id: str
    event_type: str
    task_name: str
    envelope: dict[str, object]
    idempotency_key: str
    attempt: int
    claim_token: uuid.UUID


class OutboxRelay:
    """Lease pending events, publish outside transactions, and record outcomes."""

    def __init__(
        self,
        *,
        publisher: TaskPublisher,
        session_factory: async_sessionmaker[AsyncSession] = async_session_maker,
        batch_size: int = 50,
        poll_interval_seconds: float = 1.0,
        lease_seconds: int = 60,
        retry_base_seconds: int = 5,
        retry_max_seconds: int = 300,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        self._publisher = publisher
        self._session_factory = session_factory
        self._batch_size = batch_size
        self._poll_interval_seconds = poll_interval_seconds
        self._lease_seconds = lease_seconds
        self._retry_base_seconds = retry_base_seconds
        self._retry_max_seconds = retry_max_seconds

    async def run_once(self) -> RelayBatchResult:
        """Claim and process at most one bounded batch."""
        claimed = await self._claim_batch()
        published = 0
        failed = 0
        for event in claimed:
            if await self._publish_claimed(event):
                published += 1
            else:
                failed += 1
        return RelayBatchResult(claimed=len(claimed), published=published, failed=failed)

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        """Poll until graceful shutdown is requested."""
        logger.info(
            "Outbox relay started",
            extra={"batch_size": self._batch_size, "poll_interval": self._poll_interval_seconds},
        )
        while not stop_event.is_set():
            result = await self.run_once()
            if result.claimed:
                continue
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._poll_interval_seconds)
            except TimeoutError:
                continue
        logger.info("Outbox relay stopped")

    async def _claim_batch(self) -> list[_ClaimedEvent]:
        now = utc_now()
        lease_until = now + timedelta(seconds=self._lease_seconds)
        async with self._session_factory() as session, session.begin():
            statement = (
                select(OutboxEvent)
                .where(
                    or_(
                        and_(
                            col(OutboxEvent.status) == OutboxStatus.PENDING,
                            col(OutboxEvent.available_at) <= now,
                        ),
                        and_(
                            col(OutboxEvent.status) == OutboxStatus.PUBLISHING,
                            col(OutboxEvent.claim_expires_at).is_not(None),
                            col(OutboxEvent.claim_expires_at) <= now,
                        ),
                    )
                )
                .order_by(col(OutboxEvent.created_at), col(OutboxEvent.event_id))
                .limit(self._batch_size)
                .with_for_update(skip_locked=True)
            )
            events = list((await session.exec(statement)).all())
            claimed: list[_ClaimedEvent] = []
            for event in events:
                claim_token = uuid.uuid4()
                event.status = OutboxStatus.PUBLISHING
                event.claim_token = claim_token
                event.claim_expires_at = lease_until
                event.attempt_count += 1
                event.updated_at = now
                session.add(event)
                claimed.append(
                    _ClaimedEvent(
                        event_id=event.event_id,
                        tenant_id=event.tenant_id,
                        event_type=event.event_type,
                        task_name=event.task_name,
                        envelope=cast(dict[str, object], event.envelope),
                        idempotency_key=event.idempotency_key,
                        attempt=event.attempt_count,
                        claim_token=claim_token,
                    )
                )
            return claimed

    async def _publish_claimed(self, event: _ClaimedEvent) -> bool:
        try:
            envelope = TaskEnvelope.from_message(event.envelope)
            if envelope.task_context.tenant_id != event.tenant_id:
                raise ValueError("Outbox tenant does not match the task envelope")
            if envelope.task_context.idempotency_key != event.idempotency_key:
                raise ValueError("Outbox idempotency key does not match the task envelope")
        except Exception as error:
            await self._mark_failed(event, error)
            record_outbox_publish(success=False)
            logger.warning(
                "Outbox envelope validation failed",
                extra={
                    **self._log_fields(event, publish_result="validation_failure"),
                    "error_type": type(error).__name__,
                },
            )
            return False

        attributes = {
            "outbox.event_id": str(event.event_id),
            "tenant.id": event.tenant_id,
            "outbox.event_type": event.event_type,
            "outbox.attempt": event.attempt,
            "task.idempotency_key": event.idempotency_key,
            "correlation.id": envelope.task_context.correlation_id,
        }
        if envelope.task_context.trace_id is not None:
            attributes["trace.id"] = envelope.task_context.trace_id
        with (
            bind_task_context(envelope.task_context),
            tracer.start_as_current_span("outbox.publish", attributes=attributes),
        ):
            try:
                await self._publisher.publish(
                    task_name=event.task_name,
                    envelope=envelope,
                    task_id=event.event_id,
                )
            except Exception as error:
                await self._mark_failed(event, error)
                record_outbox_publish(success=False)
                logger.warning(
                    "Outbox publication failed",
                    extra={
                        **self._log_fields(event, publish_result="failure"),
                        "error_type": type(error).__name__,
                    },
                )
                return False

            try:
                await self._mark_published(event)
            except Exception:
                record_outbox_publish(success=False)
                logger.exception(
                    "Outbox publication succeeded but state update failed; retry may duplicate",
                    extra=self._log_fields(event, publish_result="mark_failure"),
                )
                return False

            record_outbox_publish(success=True)
            logger.info(
                "Outbox event published",
                extra=self._log_fields(event, publish_result="success"),
            )
            return True

    async def _mark_published(self, claimed: _ClaimedEvent) -> None:
        async with self._session_factory() as session, session.begin():
            event = await self._locked_claim(session, claimed)
            if event is None:
                raise RuntimeError("Outbox claim was lost before marking publication")
            now = utc_now()
            event.status = OutboxStatus.PUBLISHED
            event.published_at = now
            event.updated_at = now
            event.last_error = None
            event.claim_token = None
            event.claim_expires_at = None
            session.add(event)

    async def _mark_failed(self, claimed: _ClaimedEvent, error: Exception) -> None:
        async with self._session_factory() as session, session.begin():
            event = await self._locked_claim(session, claimed)
            if event is None:
                return
            now = utc_now()
            backoff = min(
                self._retry_base_seconds * (2 ** max(claimed.attempt - 1, 0)),
                self._retry_max_seconds,
            )
            event.status = OutboxStatus.PENDING
            event.available_at = now + timedelta(seconds=backoff)
            event.updated_at = now
            safe_message = pii_filter.filter_text(str(error)).redacted_text
            event.last_error = f"{type(error).__name__}: {safe_message}"[:2000]
            event.claim_token = None
            event.claim_expires_at = None
            session.add(event)

    @staticmethod
    async def _locked_claim(session: AsyncSession, claimed: _ClaimedEvent) -> OutboxEvent | None:
        statement = (
            select(OutboxEvent)
            .where(
                col(OutboxEvent.event_id) == claimed.event_id,
                col(OutboxEvent.status) == OutboxStatus.PUBLISHING,
                col(OutboxEvent.claim_token) == claimed.claim_token,
            )
            .with_for_update()
        )
        return (await session.exec(statement)).one_or_none()

    @staticmethod
    def _log_fields(event: _ClaimedEvent, *, publish_result: str) -> dict[str, object]:
        return {
            "outbox_event_id": str(event.event_id),
            "tenant_id": event.tenant_id,
            "event_type": event.event_type,
            "attempt": event.attempt,
            "task_id": str(event.event_id),
            "idempotency_key": event.idempotency_key,
            "publish_result": publish_result,
        }
