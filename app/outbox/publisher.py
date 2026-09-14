"""Task publication Port and current Celery adapter."""

from __future__ import annotations

import asyncio
import uuid
from typing import Protocol

from celery import Celery

from app.task_runtime.envelope import TaskEnvelope


class TaskPublisher(Protocol):
    """Publish validated task envelopes without exposing a broker to callers."""

    async def publish(self, *, task_name: str, envelope: TaskEnvelope, task_id: uuid.UUID) -> str:
        """Publish one envelope and return the transport task identifier."""
        ...


class CeleryTaskPublisher:
    """Publish task envelopes through the currently configured Celery broker."""

    def __init__(self, celery: Celery) -> None:
        self._celery = celery

    async def publish(self, *, task_name: str, envelope: TaskEnvelope, task_id: uuid.UUID) -> str:
        """Send one task without blocking the relay event loop."""
        result = await asyncio.to_thread(
            self._celery.send_task,
            task_name,
            kwargs={"envelope": envelope.to_message()},
            task_id=str(task_id),
        )
        return result.id
