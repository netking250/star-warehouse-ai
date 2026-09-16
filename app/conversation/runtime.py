"""PostgreSQL-authoritative conversation execution runtime."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.conversation.contracts import (
    CancellationResult,
    ConversationExecutor,
    ConversationIdentity,
    ExecutionRequest,
    ExecutorEventType,
    RunSnapshot,
    RuntimeEvent,
    SubmitTurnCommand,
    ToolInvocation,
    ToolResultAcceptance,
    ToolResultEnvelope,
    TurnSubmission,
)
from app.conversation.state_machine import TERMINAL_RUN_STATUSES, RunStatus, transition_run_status
from app.core.tenancy import TenantIsolationError, get_current_tenant_id
from app.core.utils import utc_now
from app.models.conversation import (
    Conversation,
    ConversationRun,
    ConversationRuntimeEvent,
    ConversationToolExecution,
    ConversationTurn,
    RuntimeEventType,
    ToolExecutionStatus,
)
from app.models.message import MessageCard, MessageStatus, MessageType
from app.observability.metrics import (
    record_conversation_duration,
    record_conversation_lifecycle,
    record_conversation_terminal,
    record_conversation_transition,
)
from app.task_runtime.context import build_task_context

logger = logging.getLogger(__name__)


class ConversationRuntimeError(RuntimeError):
    """Base error raised by the conversation runtime interface."""


class ConversationNotFoundError(ConversationRuntimeError):
    """Raised when an owned conversation or run cannot be found."""


class ConversationBusyError(ConversationRuntimeError):
    """Raised when another mutating turn is active for the same conversation."""


class IdempotencyConflictError(ConversationRuntimeError):
    """Raised when one client key is reused for a different logical message."""


class StaleRuntimeResultError(ConversationRuntimeError):
    """Raised when asynchronous identity does not match its durable invocation."""


class ExecutorResultMissingError(ConversationRuntimeError):
    """Raised when an executor ends without a terminal result."""


def _lock_key(tenant_id: str, conversation_id: str) -> int:
    digest = hashlib.sha256(f"{tenant_id}\0{conversation_id}".encode()).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


class ConversationRuntime:
    """Own durable run lifecycle while delegating AI execution through one executor Port."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        executor: ConversationExecutor,
    ) -> None:
        self._session_factory = session_factory
        self._executor = executor

    async def submit_turn(
        self,
        *,
        identity: ConversationIdentity,
        command: SubmitTurnCommand,
    ) -> TurnSubmission:
        """Persist one logical turn/run atomically and deduplicate client retries."""
        self._validate_identity(identity)
        async with self._session_factory() as session, session.begin():
            await self._lock_conversation(session, identity.tenant_id, command.conversation_id)
            existing_turn = (
                await session.exec(
                    select(ConversationTurn).where(
                        ConversationTurn.tenant_id == identity.tenant_id,
                        ConversationTurn.conversation_id == command.conversation_id,
                        ConversationTurn.idempotency_key == command.idempotency_key,
                    )
                )
            ).one_or_none()
            if existing_turn is not None:
                self._require_owner(existing_turn.user_id, identity.user_id)
                original_message = (
                    await session.exec(
                        select(MessageCard).where(
                            MessageCard.tenant_id == identity.tenant_id,
                            MessageCard.logical_message_id == f"user:{existing_turn.turn_id}",
                        )
                    )
                ).one_or_none()
                if (
                    original_message is None
                    or original_message.content.get("text") != command.question
                ):
                    raise IdempotencyConflictError(
                        "Idempotency key was already used for a different message"
                    )
                existing_run = await self._get_run_for_update(
                    session, identity, command.conversation_id, existing_turn.current_run_id
                )
                return self._submission(existing_run, created=False)

            conversation = (
                await session.exec(
                    select(Conversation)
                    .where(
                        Conversation.tenant_id == identity.tenant_id,
                        Conversation.conversation_id == command.conversation_id,
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if conversation is None:
                conversation = Conversation(
                    tenant_id=identity.tenant_id,
                    conversation_id=command.conversation_id,
                    user_id=identity.user_id,
                )
                session.add(conversation)
                await session.flush()
            else:
                self._require_owner(conversation.user_id, identity.user_id)

            if conversation.active_run_id is not None:
                active_run = (
                    await session.exec(
                        select(ConversationRun).where(
                            ConversationRun.tenant_id == identity.tenant_id,
                            ConversationRun.run_id == conversation.active_run_id,
                        )
                    )
                ).one_or_none()
                if (
                    active_run is not None
                    and RunStatus(active_run.status) not in TERMINAL_RUN_STATUSES
                ):
                    raise ConversationBusyError(
                        f"Conversation {command.conversation_id} already has an active turn"
                    )
                conversation.active_run_id = None

            now = utc_now()
            turn_id = str(uuid.uuid4())
            run_id = str(uuid.uuid4())
            conversation.revision += 1
            conversation.active_run_id = run_id
            conversation.updated_at = now
            turn = ConversationTurn(
                tenant_id=identity.tenant_id,
                turn_id=turn_id,
                conversation_id=command.conversation_id,
                user_id=identity.user_id,
                idempotency_key=command.idempotency_key,
                current_run_id=run_id,
                status=RunStatus.PENDING,
                created_at=now,
                updated_at=now,
            )
            run = ConversationRun(
                tenant_id=identity.tenant_id,
                run_id=run_id,
                turn_id=turn_id,
                conversation_id=command.conversation_id,
                user_id=identity.user_id,
                correlation_id=identity.correlation_id,
                trace_id=identity.trace_id,
                status=RunStatus.PENDING,
                conversation_revision=conversation.revision,
                created_at=now,
                updated_at=now,
            )
            user_message = MessageCard(
                tenant_id=identity.tenant_id,
                thread_id=command.conversation_id,
                conversation_id=command.conversation_id,
                turn_id=turn_id,
                run_id=run_id,
                logical_message_id=f"user:{turn_id}",
                message_type=MessageType.TEXT,
                status=MessageStatus.SENT,
                content={"text": command.question},
                sender_id=identity.user_id,
                sender_type="user",
                receiver_id=None,
                created_at=now,
                updated_at=now,
            )
            session.add(turn)
            await session.flush()
            session.add(run)
            await session.flush()
            session.add(user_message)
            await session.flush()
            await self._append_event(
                session,
                run,
                RuntimeEventType.TURN_ACCEPTED,
                event_key="turn:accepted",
                payload={"status": RunStatus.PENDING},
            )
            await session.flush()
            return self._submission(run, created=True)

    async def execute(
        self,
        *,
        identity: ConversationIdentity,
        submission: TurnSubmission,
        question: str,
        intent_category: str | None = None,
        experiment_variant_id: int | None = None,
        memory_context_config: dict[str, object] | None = None,
        variant_llm_model: str | None = None,
        variant_retriever_top_k: int | None = None,
        variant_reranker_enabled: bool | None = None,
    ) -> AsyncIterator[RuntimeEvent]:
        """Execute only a newly accepted run and persist one terminal logical outcome."""
        self._validate_identity(identity)
        if not submission.created:
            return

        started, started_event = await self._start_run(identity, submission)
        if not started:
            return
        yield started_event
        expected_revision = started_event.payload["run_revision"]
        request = ExecutionRequest(
            tenant_id=identity.tenant_id,
            user_id=identity.user_id,
            conversation_id=submission.conversation_id,
            turn_id=submission.turn_id,
            run_id=submission.run_id,
            correlation_id=identity.correlation_id,
            trace_id=identity.trace_id,
            question=question,
            intent_category=intent_category,
            experiment_variant_id=experiment_variant_id,
            memory_context_config=memory_context_config,
            variant_llm_model=variant_llm_model,
            variant_retriever_top_k=variant_retriever_top_k,
            variant_reranker_enabled=variant_reranker_enabled,
        )
        completed_payload: dict[str, object] | None = None
        try:
            async for executor_event in self._executor.execute(request):
                if executor_event.event_type is ExecutorEventType.COMPLETED:
                    completed_payload = executor_event.payload
                    continue
                yield RuntimeEvent(
                    event_type=executor_event.event_type,
                    conversation_id=submission.conversation_id,
                    turn_id=submission.turn_id,
                    run_id=submission.run_id,
                    payload=executor_event.payload,
                    durable=False,
                )
            if completed_payload is None:
                raise ExecutorResultMissingError("Conversation executor returned no final result")
            answer = str(completed_payload.get("answer", ""))
            final_metadata = completed_payload.get("metadata")
            safe_metadata = final_metadata if isinstance(final_metadata, dict) else {}
            accepted, event = await self._complete_run(
                identity=identity,
                submission=submission,
                answer=answer,
                metadata=safe_metadata,
                expected_revision=int(expected_revision),
            )
            if accepted:
                yield event
        except asyncio.CancelledError:
            await self.cancel_run(
                identity=identity,
                conversation_id=submission.conversation_id,
                run_id=submission.run_id,
            )
            raise
        except Exception as error:
            event = await self._fail_run(identity, submission, error)
            if event is not None:
                yield event
            raise

    async def get_run(
        self,
        *,
        identity: ConversationIdentity,
        conversation_id: str,
        run_id: str,
    ) -> RunSnapshot:
        """Load a tenant/user-owned run and its durable final result."""
        self._validate_identity(identity)
        async with self._session_factory() as session:
            run = await self._get_run(session, identity, conversation_id, run_id)
            return await self._snapshot(session, run)

    async def replay_events(
        self,
        *,
        identity: ConversationIdentity,
        conversation_id: str,
        run_id: str,
        after_sequence: int = 0,
    ) -> list[RuntimeEvent]:
        """Replay durable events after a caller's last observed sequence without execution."""
        self._validate_identity(identity)
        async with self._session_factory() as session:
            await self._get_run(session, identity, conversation_id, run_id)
            rows = (
                await session.exec(
                    select(ConversationRuntimeEvent)
                    .where(
                        ConversationRuntimeEvent.tenant_id == identity.tenant_id,
                        ConversationRuntimeEvent.conversation_id == conversation_id,
                        ConversationRuntimeEvent.run_id == run_id,
                        ConversationRuntimeEvent.sequence > after_sequence,
                    )
                    .order_by(col(ConversationRuntimeEvent.sequence))
                )
            ).all()
            return [self._runtime_event(row) for row in rows]

    async def cancel_run(
        self,
        *,
        identity: ConversationIdentity,
        conversation_id: str,
        run_id: str,
    ) -> CancellationResult:
        """Logically cancel an active run; repeated and terminal cancellation are explicit."""
        self._validate_identity(identity)
        async with self._session_factory() as session, session.begin():
            await self._lock_conversation(session, identity.tenant_id, conversation_id)
            run, turn, conversation = await self._load_run_graph_for_update(
                session, identity, conversation_id, run_id
            )
            current = RunStatus(run.status)
            if current is RunStatus.CANCELLED:
                return CancellationResult(await self._snapshot(session, run), "ALREADY_CANCELLED")
            if current in {RunStatus.COMPLETED, RunStatus.FAILED}:
                return CancellationResult(await self._snapshot(session, run), "TERMINAL_UNCHANGED")

            now = utc_now()
            self._transition(conversation, turn, run, RunStatus.CANCELLED, now)
            run.cancelled_at = now
            self._record_terminal_metric(status="cancelled", category="cancelled")
            pending_tools = (
                await session.exec(
                    select(ConversationToolExecution).where(
                        ConversationToolExecution.tenant_id == identity.tenant_id,
                        ConversationToolExecution.run_id == run.run_id,
                        col(ConversationToolExecution.status).in_(
                            [ToolExecutionStatus.REQUESTED, ToolExecutionStatus.RUNNING]
                        ),
                    )
                )
            ).all()
            for tool in pending_tools:
                tool.status = ToolExecutionStatus.CANCELLED
                tool.completed_at = now
                tool.updated_at = now
            if conversation.active_run_id == run.run_id:
                conversation.active_run_id = None
            await self._append_event(
                session,
                run,
                RuntimeEventType.RUN_CANCELLED,
                event_key="run:cancelled",
                payload={"status": RunStatus.CANCELLED},
            )
            await session.flush()
            return CancellationResult(await self._snapshot(session, run), "CANCELLED")

    async def request_tool(
        self,
        *,
        identity: ConversationIdentity,
        conversation_id: str,
        run_id: str,
        tool_name: str,
        idempotency_key: str,
    ) -> ToolInvocation:
        """Persist one asynchronous tool request and pause its owning run."""
        self._validate_identity(identity)
        async with self._session_factory() as session, session.begin():
            await self._lock_conversation(session, identity.tenant_id, conversation_id)
            run, turn, conversation = await self._load_run_graph_for_update(
                session, identity, conversation_id, run_id
            )
            existing = (
                await session.exec(
                    select(ConversationToolExecution).where(
                        ConversationToolExecution.tenant_id == identity.tenant_id,
                        ConversationToolExecution.run_id == run_id,
                        ConversationToolExecution.idempotency_key == idempotency_key,
                    )
                )
            ).one_or_none()
            if existing is not None:
                return self._tool_invocation(existing, identity, duplicate=True)
            if RunStatus(run.status) is not RunStatus.RUNNING:
                raise StaleRuntimeResultError("Run is not accepting a tool request")

            now = utc_now()
            self._transition(conversation, turn, run, RunStatus.WAITING_TOOL, now)
            tool = ConversationToolExecution(
                tenant_id=identity.tenant_id,
                tool_execution_id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                turn_id=run.turn_id,
                run_id=run.run_id,
                user_id=identity.user_id,
                tool_name=tool_name,
                idempotency_key=idempotency_key,
                status=ToolExecutionStatus.REQUESTED,
                expected_run_revision=run.revision,
                created_at=now,
                updated_at=now,
            )
            session.add(tool)
            await self._append_event(
                session,
                run,
                RuntimeEventType.TOOL_REQUESTED,
                event_key=f"tool:{tool.tool_execution_id}:requested",
                payload={"tool_execution_id": tool.tool_execution_id, "tool_name": tool_name},
            )
            await session.flush()
            return self._tool_invocation(tool, identity, duplicate=False)

    async def accept_tool_result(
        self, *, identity: ConversationIdentity, envelope: ToolResultEnvelope
    ) -> ToolResultAcceptance:
        """Validate and apply one tool result without allowing stale-run mutation."""
        self._validate_identity(identity)
        if envelope.tenant_id != identity.tenant_id or envelope.user_id != identity.user_id:
            raise TenantIsolationError("Tool result identity does not match the trusted actor")
        async with self._session_factory() as session, session.begin():
            await self._lock_conversation(session, identity.tenant_id, envelope.conversation_id)
            run, turn, conversation = await self._load_run_graph_for_update(
                session, identity, envelope.conversation_id, envelope.run_id
            )
            tool = (
                await session.exec(
                    select(ConversationToolExecution)
                    .where(
                        ConversationToolExecution.tenant_id == identity.tenant_id,
                        ConversationToolExecution.tool_execution_id == envelope.tool_execution_id,
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if tool is None:
                raise ConversationNotFoundError("Tool execution was not found")
            if (
                tool.run_id != envelope.run_id
                or tool.turn_id != envelope.turn_id
                or tool.conversation_id != envelope.conversation_id
                or run.correlation_id != envelope.correlation_id
            ):
                raise StaleRuntimeResultError("Tool result does not match its durable run identity")
            if ToolExecutionStatus(tool.status) in {
                ToolExecutionStatus.SUCCEEDED,
                ToolExecutionStatus.FAILED,
            }:
                if tool.result_delivery_id == envelope.delivery_id:
                    return ToolResultAcceptance(
                        False, True, "DUPLICATE", await self._snapshot(session, run)
                    )
                raise StaleRuntimeResultError("Tool execution already has a different result")

            current = RunStatus(run.status)
            accepts_result = (
                current is RunStatus.WAITING_TOOL
                and conversation.active_run_id == run.run_id
                and run.revision == envelope.expected_run_revision
                and tool.expected_run_revision == envelope.expected_run_revision
            )
            if not accepts_result:
                logger.info(
                    "Rejected stale conversation tool result",
                    extra={
                        "tenant_id": run.tenant_id,
                        "conversation_id": run.conversation_id,
                        "turn_id": run.turn_id,
                        "run_id": run.run_id,
                        "correlation_id": run.correlation_id,
                        "tool_execution_id": tool.tool_execution_id,
                    },
                )
                await self._append_event(
                    session,
                    run,
                    RuntimeEventType.STALE_RESULT_IGNORED,
                    event_key=f"tool:{tool.tool_execution_id}:ignored:{envelope.delivery_id}",
                    payload={"tool_execution_id": tool.tool_execution_id, "reason": "STALE_RUN"},
                )
                await session.flush()
                return ToolResultAcceptance(
                    False, False, "STALE_RUN", await self._snapshot(session, run)
                )

            now = utc_now()
            tool.result_delivery_id = envelope.delivery_id
            tool.completed_at = now
            tool.updated_at = now
            if envelope.succeeded:
                tool.status = ToolExecutionStatus.SUCCEEDED
                tool.result_payload = envelope.result
                self._transition(conversation, turn, run, RunStatus.RUNNING, now)
                event_type = RuntimeEventType.TOOL_COMPLETED
                payload = {"tool_execution_id": tool.tool_execution_id, "status": "SUCCEEDED"}
            else:
                tool.status = ToolExecutionStatus.FAILED
                tool.failure_category = envelope.failure_category or "TOOL_FAILED"
                self._transition(conversation, turn, run, RunStatus.FAILED, now)
                run.failure_category = tool.failure_category
                run.failure_metadata = {"tool_name": tool.tool_name}
                run.completed_at = now
                self._record_terminal_metric(
                    status="failed", category=tool.failure_category or "tool_failed"
                )
                if conversation.active_run_id == run.run_id:
                    conversation.active_run_id = None
                event_type = RuntimeEventType.TOOL_FAILED
                payload = {
                    "tool_execution_id": tool.tool_execution_id,
                    "status": "FAILED",
                    "failure_category": tool.failure_category,
                }
            await self._append_event(
                session,
                run,
                event_type,
                event_key=f"tool:{tool.tool_execution_id}:result:{envelope.delivery_id}",
                payload=payload,
            )
            if not envelope.succeeded:
                await self._append_event(
                    session,
                    run,
                    RuntimeEventType.RUN_FAILED,
                    event_key="run:failed",
                    payload={
                        "status": RunStatus.FAILED,
                        "failure_category": tool.failure_category,
                    },
                )
            await session.flush()
            return ToolResultAcceptance(True, False, "ACCEPTED", await self._snapshot(session, run))

    async def reconcile_orphaned_runs(
        self,
        *,
        identity: ConversationIdentity,
        older_than: timedelta,
        limit: int = 100,
    ) -> list[str]:
        """Fail bounded tenant-owned non-terminal runs that exceeded the operational threshold."""
        self._validate_identity(identity)
        cutoff = utc_now() - older_than
        reconciled: list[str] = []
        async with self._session_factory() as session, session.begin():
            rows = (
                await session.exec(
                    select(ConversationRun)
                    .where(
                        ConversationRun.tenant_id == identity.tenant_id,
                        ConversationRun.user_id == identity.user_id,
                        col(ConversationRun.status).in_(
                            [
                                RunStatus.PENDING,
                                RunStatus.RUNNING,
                                RunStatus.WAITING_TOOL,
                                RunStatus.WAITING_HUMAN,
                            ]
                        ),
                        ConversationRun.updated_at < cutoff,
                    )
                    .order_by(col(ConversationRun.updated_at))
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for run in rows:
                turn = (
                    await session.exec(
                        select(ConversationTurn).where(
                            ConversationTurn.tenant_id == identity.tenant_id,
                            ConversationTurn.turn_id == run.turn_id,
                        )
                    )
                ).one()
                conversation = (
                    await session.exec(
                        select(Conversation).where(
                            Conversation.tenant_id == identity.tenant_id,
                            Conversation.conversation_id == run.conversation_id,
                        )
                    )
                ).one()
                now = utc_now()
                self._transition(conversation, turn, run, RunStatus.FAILED, now)
                run.failure_category = "ORPHANED_RUN"
                run.failure_metadata = {"reason": "operational_timeout"}
                run.completed_at = now
                self._record_terminal_metric(status="failed", category="orphaned_run")
                if conversation.active_run_id == run.run_id:
                    conversation.active_run_id = None
                await self._append_event(
                    session,
                    run,
                    RuntimeEventType.RUN_FAILED,
                    event_key="run:orphaned",
                    payload={"status": RunStatus.FAILED, "failure_category": "ORPHANED_RUN"},
                )
                reconciled.append(run.run_id)
        return reconciled

    async def _start_run(
        self, identity: ConversationIdentity, submission: TurnSubmission
    ) -> tuple[bool, RuntimeEvent]:
        async with self._session_factory() as session, session.begin():
            await self._lock_conversation(session, identity.tenant_id, submission.conversation_id)
            run, turn, conversation = await self._load_run_graph_for_update(
                session, identity, submission.conversation_id, submission.run_id
            )
            if RunStatus(run.status) is not RunStatus.PENDING:
                events = await self._events_in_session(session, identity, run.run_id, 0)
                fallback = (
                    events[-1]
                    if events
                    else RuntimeEvent(
                        event_type=str(run.status),
                        conversation_id=run.conversation_id,
                        turn_id=run.turn_id,
                        run_id=run.run_id,
                        payload={"run_revision": run.revision},
                    )
                )
                return False, fallback
            now = utc_now()
            self._transition(conversation, turn, run, RunStatus.RUNNING, now)
            run.started_at = now
            event = await self._append_event(
                session,
                run,
                RuntimeEventType.RUN_STARTED,
                event_key="run:started",
                payload={"status": RunStatus.RUNNING, "run_revision": run.revision},
            )
            await session.flush()
            return True, event

    async def _complete_run(
        self,
        *,
        identity: ConversationIdentity,
        submission: TurnSubmission,
        answer: str,
        metadata: dict[str, object],
        expected_revision: int,
    ) -> tuple[bool, RuntimeEvent]:
        async with self._session_factory() as session, session.begin():
            await self._lock_conversation(session, identity.tenant_id, submission.conversation_id)
            run, turn, conversation = await self._load_run_graph_for_update(
                session, identity, submission.conversation_id, submission.run_id
            )
            if RunStatus(run.status) is RunStatus.COMPLETED:
                existing = await self._event_by_key(session, run, "run:completed")
                if existing is None:
                    raise ConversationRuntimeError("Completed run is missing its terminal event")
                return False, self._runtime_event(existing)
            accepts_result = (
                RunStatus(run.status) is RunStatus.RUNNING
                and conversation.active_run_id == run.run_id
                and run.revision >= expected_revision
                and conversation.revision == run.conversation_revision
            )
            if not accepts_result:
                event = await self._append_event(
                    session,
                    run,
                    RuntimeEventType.STALE_RESULT_IGNORED,
                    event_key="run:completion:ignored",
                    payload={"reason": "STALE_OR_TERMINAL"},
                )
                await session.flush()
                return False, event

            now = utc_now()
            message = MessageCard(
                tenant_id=identity.tenant_id,
                thread_id=run.conversation_id,
                conversation_id=run.conversation_id,
                turn_id=run.turn_id,
                run_id=run.run_id,
                logical_message_id=f"assistant:{run.turn_id}",
                message_type=MessageType.TEXT,
                status=MessageStatus.SENT,
                content={"text": answer},
                sender_id=None,
                sender_type="agent",
                receiver_id=identity.user_id,
                meta_data=dict(metadata),
                created_at=now,
                updated_at=now,
            )
            session.add(message)
            await session.flush()
            self._transition(conversation, turn, run, RunStatus.COMPLETED, now)
            run.final_message_id = message.id
            run.completed_at = now
            self._record_terminal_metric(status="completed", category="completed")
            conversation.active_run_id = None
            event = await self._append_event(
                session,
                run,
                RuntimeEventType.RUN_COMPLETED,
                event_key="run:completed",
                payload={"status": RunStatus.COMPLETED, "message_id": message.id},
            )
            await session.flush()
            return True, event

    async def _fail_run(
        self,
        identity: ConversationIdentity,
        submission: TurnSubmission,
        error: Exception,
    ) -> RuntimeEvent | None:
        async with self._session_factory() as session, session.begin():
            await self._lock_conversation(session, identity.tenant_id, submission.conversation_id)
            run, turn, conversation = await self._load_run_graph_for_update(
                session, identity, submission.conversation_id, submission.run_id
            )
            if RunStatus(run.status) in TERMINAL_RUN_STATUSES:
                return None
            now = utc_now()
            self._transition(conversation, turn, run, RunStatus.FAILED, now)
            run.failure_category = "EXECUTOR_ERROR"
            run.failure_metadata = {"error_type": type(error).__name__}
            run.completed_at = now
            self._record_terminal_metric(status="failed", category="executor_error")
            if conversation.active_run_id == run.run_id:
                conversation.active_run_id = None
            event = await self._append_event(
                session,
                run,
                RuntimeEventType.RUN_FAILED,
                event_key="run:failed",
                payload={"status": RunStatus.FAILED, "failure_category": "EXECUTOR_ERROR"},
            )
            await session.flush()
            return event

    async def _load_run_graph_for_update(
        self,
        session: AsyncSession,
        identity: ConversationIdentity,
        conversation_id: str,
        run_id: str,
    ) -> tuple[ConversationRun, ConversationTurn, Conversation]:
        run = await self._get_run_for_update(session, identity, conversation_id, run_id)
        turn = (
            await session.exec(
                select(ConversationTurn)
                .where(
                    ConversationTurn.tenant_id == identity.tenant_id,
                    ConversationTurn.turn_id == run.turn_id,
                    ConversationTurn.user_id == identity.user_id,
                )
                .with_for_update()
            )
        ).one_or_none()
        conversation = (
            await session.exec(
                select(Conversation)
                .where(
                    Conversation.tenant_id == identity.tenant_id,
                    Conversation.conversation_id == conversation_id,
                    Conversation.user_id == identity.user_id,
                )
                .with_for_update()
            )
        ).one_or_none()
        if turn is None or conversation is None:
            raise ConversationNotFoundError("Conversation runtime identity was not found")
        return run, turn, conversation

    async def _get_run_for_update(
        self,
        session: AsyncSession,
        identity: ConversationIdentity,
        conversation_id: str,
        run_id: str,
    ) -> ConversationRun:
        statement = (
            select(ConversationRun)
            .where(
                ConversationRun.tenant_id == identity.tenant_id,
                ConversationRun.conversation_id == conversation_id,
                ConversationRun.run_id == run_id,
                ConversationRun.user_id == identity.user_id,
            )
            .with_for_update()
        )
        run = (await session.exec(statement)).one_or_none()
        if run is None:
            raise ConversationNotFoundError("Conversation run was not found")
        return run

    async def _get_run(
        self,
        session: AsyncSession,
        identity: ConversationIdentity,
        conversation_id: str,
        run_id: str,
    ) -> ConversationRun:
        run = (
            await session.exec(
                select(ConversationRun).where(
                    ConversationRun.tenant_id == identity.tenant_id,
                    ConversationRun.conversation_id == conversation_id,
                    ConversationRun.run_id == run_id,
                    ConversationRun.user_id == identity.user_id,
                )
            )
        ).one_or_none()
        if run is None:
            raise ConversationNotFoundError("Conversation run was not found")
        return run

    async def _append_event(
        self,
        session: AsyncSession,
        run: ConversationRun,
        event_type: RuntimeEventType,
        *,
        event_key: str,
        payload: dict[str, object],
    ) -> RuntimeEvent:
        existing = await self._event_by_key(session, run, event_key)
        if existing is not None:
            return self._runtime_event(existing)
        row = ConversationRuntimeEvent(
            tenant_id=run.tenant_id,
            event_id=str(uuid.uuid4()),
            conversation_id=run.conversation_id,
            turn_id=run.turn_id,
            run_id=run.run_id,
            sequence=run.next_event_sequence,
            event_key=event_key,
            event_type=event_type,
            payload=dict(payload),
            correlation_id=run.correlation_id,
        )
        run.next_event_sequence += 1
        session.add(run)
        session.add(row)
        await session.flush()
        return self._runtime_event(row)

    @staticmethod
    async def _event_by_key(
        session: AsyncSession, run: ConversationRun, event_key: str
    ) -> ConversationRuntimeEvent | None:
        return (
            await session.exec(
                select(ConversationRuntimeEvent).where(
                    ConversationRuntimeEvent.tenant_id == run.tenant_id,
                    ConversationRuntimeEvent.run_id == run.run_id,
                    ConversationRuntimeEvent.event_key == event_key,
                )
            )
        ).one_or_none()

    async def _events_in_session(
        self,
        session: AsyncSession,
        identity: ConversationIdentity,
        run_id: str,
        after_sequence: int,
    ) -> list[RuntimeEvent]:
        rows = (
            await session.exec(
                select(ConversationRuntimeEvent)
                .where(
                    ConversationRuntimeEvent.tenant_id == identity.tenant_id,
                    ConversationRuntimeEvent.run_id == run_id,
                    ConversationRuntimeEvent.sequence > after_sequence,
                )
                .order_by(col(ConversationRuntimeEvent.sequence))
            )
        ).all()
        return [self._runtime_event(row) for row in rows]

    async def _snapshot(self, session: AsyncSession, run: ConversationRun) -> RunSnapshot:
        answer: str | None = None
        if run.final_message_id is not None:
            message = (
                await session.exec(
                    select(MessageCard).where(
                        MessageCard.id == run.final_message_id,
                        MessageCard.tenant_id == run.tenant_id,
                        MessageCard.conversation_id == run.conversation_id,
                        MessageCard.turn_id == run.turn_id,
                        MessageCard.run_id == run.run_id,
                    )
                )
            ).one_or_none()
            if message is not None:
                raw_answer = message.content.get("text")
                answer = str(raw_answer) if raw_answer is not None else None
        return RunSnapshot(
            conversation_id=run.conversation_id,
            turn_id=run.turn_id,
            run_id=run.run_id,
            status=RunStatus(run.status),
            revision=run.revision,
            conversation_revision=run.conversation_revision,
            final_answer=answer,
            failure_category=run.failure_category,
        )

    @staticmethod
    def _transition(
        conversation: Conversation,
        turn: ConversationTurn,
        run: ConversationRun,
        target: RunStatus,
        now: datetime,
    ) -> None:
        previous_status = RunStatus(run.status)
        new_status = transition_run_status(previous_status, target)
        run.status = new_status
        run.revision += 1
        conversation.revision += 1
        run.conversation_revision = conversation.revision
        turn.status = new_status
        run.updated_at = now
        turn.updated_at = now
        conversation.updated_at = now
        logger.info(
            "Conversation run transitioned",
            extra={
                "tenant_id": run.tenant_id,
                "conversation_id": run.conversation_id,
                "turn_id": run.turn_id,
                "run_id": run.run_id,
                "correlation_id": run.correlation_id,
                "transition": f"{previous_status}->{new_status}",
            },
        )
        try:
            record_conversation_transition(
                from_status=previous_status.value,
                to_status=new_status.value,
            )
            lifecycle_event = {
                RunStatus.RUNNING: "started",
                RunStatus.WAITING_TOOL: "waiting_tool",
                RunStatus.WAITING_HUMAN: "waiting_human",
                RunStatus.COMPLETED: "completed",
                RunStatus.FAILED: "failed",
                RunStatus.CANCELLED: "cancelled",
            }.get(new_status)
            if lifecycle_event is not None:
                record_conversation_lifecycle(lifecycle_event)
            if new_status in TERMINAL_RUN_STATUSES:
                record_conversation_duration(
                    terminal_status=new_status.value,
                    duration_seconds=(now - run.created_at).total_seconds(),
                )
        except Exception as telemetry_error:
            logger.debug(
                "Conversation metric recording unavailable: %s",
                type(telemetry_error).__name__,
            )

    @staticmethod
    def _record_terminal_metric(*, status: str, category: str) -> None:
        """Record terminal classification without affecting durable state transitions."""
        try:
            record_conversation_terminal(status=status, category=category)
        except Exception as telemetry_error:
            logger.debug(
                "Conversation terminal metric unavailable: %s",
                type(telemetry_error).__name__,
            )

    @staticmethod
    async def _lock_conversation(
        session: AsyncSession, tenant_id: str, conversation_id: str
    ) -> None:
        connection = await session.connection()
        if connection.dialect.name == "postgresql":
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": _lock_key(tenant_id, conversation_id)},
            )

    @staticmethod
    def _runtime_event(row: ConversationRuntimeEvent) -> RuntimeEvent:
        return RuntimeEvent(
            event_type=row.event_type,
            conversation_id=row.conversation_id,
            turn_id=row.turn_id,
            run_id=row.run_id,
            payload=row.payload,
            sequence=row.sequence,
            event_id=row.event_id,
            durable=True,
        )

    @staticmethod
    def _submission(run: ConversationRun, *, created: bool) -> TurnSubmission:
        return TurnSubmission(
            conversation_id=run.conversation_id,
            turn_id=run.turn_id,
            run_id=run.run_id,
            status=RunStatus(run.status),
            run_revision=run.revision,
            created=created,
        )

    @staticmethod
    def _require_owner(actual_user_id: int, expected_user_id: int) -> None:
        if actual_user_id != expected_user_id:
            raise ConversationNotFoundError("Conversation was not found")

    @staticmethod
    def _validate_identity(identity: ConversationIdentity) -> None:
        if get_current_tenant_id() != identity.tenant_id:
            raise TenantIsolationError("Runtime identity does not match the bound tenant")

    @staticmethod
    def _tool_invocation(
        tool: ConversationToolExecution,
        identity: ConversationIdentity,
        *,
        duplicate: bool,
    ) -> ToolInvocation:
        task_context = build_task_context(
            task_name=f"conversation.tool.{tool.tool_name}",
            tenant_id=identity.tenant_id,
            user_id=identity.user_id,
            correlation_id=identity.correlation_id,
            trace_id=identity.trace_id,
            thread_id=tool.conversation_id,
            operation_id=tool.tool_execution_id,
        )
        return ToolInvocation(
            tool_execution_id=tool.tool_execution_id,
            run_id=tool.run_id,
            turn_id=tool.turn_id,
            conversation_id=tool.conversation_id,
            tool_name=tool.tool_name,
            expected_run_revision=tool.expected_run_revision,
            task_context=task_context,
            duplicate=duplicate,
        )
