"""Behavior tests for the canonical conversation-run lifecycle."""

import pytest

from app.conversation.state_machine import (
    IllegalRunTransitionError,
    RunStatus,
    transition_run_status,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RunStatus.PENDING, RunStatus.RUNNING),
        (RunStatus.PENDING, RunStatus.FAILED),
        (RunStatus.RUNNING, RunStatus.WAITING_TOOL),
        (RunStatus.RUNNING, RunStatus.WAITING_HUMAN),
        (RunStatus.RUNNING, RunStatus.COMPLETED),
        (RunStatus.RUNNING, RunStatus.FAILED),
        (RunStatus.RUNNING, RunStatus.CANCELLED),
        (RunStatus.WAITING_TOOL, RunStatus.RUNNING),
        (RunStatus.WAITING_HUMAN, RunStatus.RUNNING),
    ],
)
def test_runtime_legal_lifecycle_transition_succeeds(current: RunStatus, target: RunStatus) -> None:
    assert transition_run_status(current, target) is target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RunStatus.PENDING, RunStatus.COMPLETED),
        (RunStatus.WAITING_TOOL, RunStatus.COMPLETED),
        (RunStatus.COMPLETED, RunStatus.RUNNING),
        (RunStatus.FAILED, RunStatus.RUNNING),
        (RunStatus.CANCELLED, RunStatus.RUNNING),
        (RunStatus.CANCELLED, RunStatus.COMPLETED),
    ],
)
def test_runtime_illegal_or_terminal_transition_is_rejected(
    current: RunStatus, target: RunStatus
) -> None:
    with pytest.raises(IllegalRunTransitionError):
        transition_run_status(current, target)


def test_runtime_repeated_cancellation_is_idempotent() -> None:
    assert transition_run_status(RunStatus.CANCELLED, RunStatus.CANCELLED) is RunStatus.CANCELLED
