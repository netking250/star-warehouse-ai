"""Dead-letter message contract and publisher seam."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from celery import Celery
from kombu import Connection, Exchange, Queue
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.core.utils import utc_now


class DeadLetterMessage(BaseModel):
    """Sanitized terminal task evidence retained in the broker DLQ."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    task_id: str | None = Field(default=None, max_length=128)
    task_name: str = Field(min_length=1, max_length=192)
    tenant_id: str | None = Field(default=None, max_length=64)
    idempotency_key: str | None = Field(default=None, max_length=192)
    correlation_id: str | None = Field(default=None, max_length=128)
    trace_id: str | None = Field(default=None, max_length=32)
    attempt: int = Field(ge=1)
    failure_code: str = Field(min_length=1, max_length=64)
    failure_reason: str = Field(min_length=1, max_length=2000)
    envelope: dict[str, JsonValue] | None = None
    failed_at: datetime = Field(default_factory=utc_now)


class DeadLetterPublisher(Protocol):
    """Publish one terminal message to durable broker dead-letter storage."""

    def publish(self, message: DeadLetterMessage) -> str:
        """Publish the terminal evidence and return its broker identity."""
        ...


class CeleryDeadLetterPublisher:
    """Publish enriched terminal evidence to the RabbitMQ critical DLQ."""

    def __init__(self, celery: Celery, *, broker_url: str | None = None) -> None:
        self._celery = celery
        self._broker_url = broker_url

    def publish(self, message: DeadLetterMessage) -> str:
        """Send one persistent record directly to the DLX-bound queue.

        Terminal evidence is not an executable Celery task. Publishing a plain
        JSON record prevents an ordinary worker from acknowledging it as an
        unregistered task and keeps the queue available for explicit operators.
        """
        broker_url = self._broker_url or self._celery.conf.broker_url
        exchange = Exchange("tasks.dlx", type="direct", durable=True)
        queue = Queue("critical.dlq", exchange, routing_key="critical.dead", durable=True)
        message_id = (
            message.task_id
            or f"terminal:{message.idempotency_key or message.failed_at.isoformat()}"
        )
        with Connection(broker_url, connect_timeout=2) as connection:
            producer = connection.Producer(serializer="json")
            producer.publish(
                message.model_dump(mode="json"),
                exchange=exchange,
                routing_key="critical.dead",
                declare=[queue],
                delivery_mode=2,
                retry=True,
                retry_policy={
                    "max_retries": 3,
                    "interval_start": 0,
                    "interval_step": 0.5,
                    "interval_max": 2,
                },
                headers={"message_id": message_id, "content_type": "task-terminal-evidence"},
            )
        return message_id
