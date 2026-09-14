"""Current direct-Celery dispatch seam for versioned task envelopes."""

from __future__ import annotations

from celery.app.task import Task
from celery.result import AsyncResult
from pydantic import BaseModel, JsonValue

from app.task_runtime.context import TaskContext
from app.task_runtime.envelope import TaskEnvelope


def dispatch_task(
    task: Task,
    *,
    task_context: TaskContext,
    payload: BaseModel | dict[str, JsonValue],
    ignore_result: bool = False,
    retry: bool = True,
) -> AsyncResult:
    """Publish one validated envelope using today's direct Celery delivery semantics.

    This seam does not provide durability or atomic publication. T03/T04 own
    the outbox and reliable-delivery upgrade.
    """
    serialized_payload = (
        payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    )
    envelope = TaskEnvelope(task_context=task_context, payload=serialized_payload)
    return task.apply_async(
        kwargs={"envelope": envelope.to_message()},
        ignore_result=ignore_result,
        retry=retry,
    )
