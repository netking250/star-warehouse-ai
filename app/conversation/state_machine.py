"""Canonical state machine for durable conversation runs."""

from enum import StrEnum


class RunStatus(StrEnum):
    """Durable lifecycle state of one conversation run attempt."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_TOOL = "WAITING_TOOL"
    WAITING_HUMAN = "WAITING_HUMAN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_RUN_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED})

_LEGAL_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.PENDING: frozenset({RunStatus.RUNNING, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.WAITING_TOOL,
            RunStatus.WAITING_HUMAN,
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.WAITING_TOOL: frozenset({RunStatus.RUNNING, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.WAITING_HUMAN: frozenset({RunStatus.RUNNING, RunStatus.FAILED, RunStatus.CANCELLED}),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}


class IllegalRunTransitionError(RuntimeError):
    """Raised when a caller attempts an illegal run-state transition."""

    code = "ILLEGAL_RUN_TRANSITION"


def transition_run_status(current: RunStatus | str, target: RunStatus | str) -> RunStatus:
    """Validate and return one legal run status transition.

    Repeating the current status is idempotent only for terminal states. Non-terminal self
    transitions are rejected so callers cannot hide duplicate lifecycle actions.
    """
    current_status = RunStatus(current)
    target_status = RunStatus(target)
    if current_status is target_status and current_status in TERMINAL_RUN_STATUSES:
        return current_status
    if target_status not in _LEGAL_TRANSITIONS[current_status]:
        raise IllegalRunTransitionError(
            f"Cannot transition run from {current_status} to {target_status}"
        )
    return target_status
