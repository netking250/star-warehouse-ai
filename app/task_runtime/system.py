"""Execution wrapper for explicitly scoped scheduled system tasks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import wraps
from typing import TypeVar, cast

from app.task_runtime.binding import task_execution_scope
from app.task_runtime.envelope import SystemTaskEnvelope

R = TypeVar("R")


def system_task_handler(task_name: str) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """Validate and bind Beat's explicit system envelope around a task body.

    ``None`` remains accepted for direct in-process maintenance calls. Every
    production Beat entry supplies an envelope, so scheduled execution is
    explicitly global and never invents a tenant.
    """

    def decorate(function: Callable[..., R]) -> Callable[..., R]:
        @wraps(function)
        def wrapped(*args: object, **kwargs: object) -> R:
            envelope = kwargs.pop("envelope", None)
            if envelope is None:
                return function(*args, **kwargs)
            if not isinstance(envelope, Mapping):
                raise ValueError("System task envelope must be a mapping")
            parsed = SystemTaskEnvelope.from_message(cast(Mapping[str, object], envelope))
            bound_task = args[0] if args else None
            request = getattr(bound_task, "request", None)
            task_id = getattr(request, "id", None)
            with task_execution_scope(
                parsed.task_context,
                task_name=f"celery.{task_name}",
                task_id=task_id,
            ):
                return function(*args, **kwargs)

        return wrapped

    return decorate
