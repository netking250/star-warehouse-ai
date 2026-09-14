"""Current Celery adapter for the task publisher Port."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from celery import Celery

from app.outbox.publisher import CeleryTaskPublisher
from app.task_runtime.context import build_task_context
from app.task_runtime.envelope import TaskEnvelope


@pytest.mark.asyncio
async def test_celery_publisher_sends_envelope_with_stable_outbox_task_id() -> None:
    """Keep relay output compatible with the current Celery transport."""
    celery = MagicMock(spec=Celery)
    celery.send_task.return_value = SimpleNamespace(id="published-task-id")
    task_id = uuid.uuid4()
    envelope = TaskEnvelope(
        task_context=build_task_context(
            task_name="refund.notify_admin",
            tenant_id="default",
            user_id=1,
            correlation_id="corr-celery-publisher",
        ),
        payload={"audit_log_id": 1},
    )

    published_id = await CeleryTaskPublisher(celery).publish(
        task_name="refund.notify_admin", envelope=envelope, task_id=task_id
    )

    assert published_id == "published-task-id"
    celery.send_task.assert_called_once_with(
        "refund.notify_admin",
        kwargs={"envelope": envelope.to_message()},
        task_id=str(task_id),
    )
