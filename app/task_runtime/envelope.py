"""Versioned JSON envelopes for tenant and system task messages."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.task_runtime.context import SystemTaskContext, TaskContext


class TaskEnvelope(BaseModel):
    """Versioned tenant task message with metadata separated from payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    task_context: TaskContext
    payload: dict[str, JsonValue] = Field(default_factory=dict)

    def to_message(self) -> dict[str, object]:
        """Return a Celery JSON-serializer compatible message."""
        return self.model_dump(mode="json")

    @classmethod
    def from_message(cls, message: Mapping[str, object]) -> TaskEnvelope:
        """Validate an untrusted broker message before worker execution."""
        return cls.model_validate(message)


class SystemTaskEnvelope(BaseModel):
    """Versioned message for an explicitly global scheduled task."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    task_context: SystemTaskContext
    payload: dict[str, JsonValue] = Field(default_factory=dict)

    def to_message(self) -> dict[str, object]:
        """Return a Celery JSON-serializer compatible system message."""
        return self.model_dump(mode="json")

    @classmethod
    def from_message(cls, message: Mapping[str, object]) -> SystemTaskEnvelope:
        """Validate an untrusted global-task message before worker execution."""
        return cls.model_validate(message)


def parse_task_envelope(message: Mapping[str, object]) -> TaskEnvelope | SystemTaskEnvelope:
    """Validate a task message using its explicit tenant or system scope."""
    context = message.get("task_context")
    context_mapping = cast(Mapping[str, object], context) if isinstance(context, Mapping) else {}
    if context_mapping.get("scope") == "system":
        return SystemTaskEnvelope.from_message(message)
    return TaskEnvelope.from_message(message)
