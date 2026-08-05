"""Regression tests for loading the Celery application."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def _run_in_fresh_process(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_celery_app_fresh_process_import_succeeds() -> None:
    """Load the Celery application without hitting a circular import."""
    result = _run_in_fresh_process("from app.celery_app import celery_app; print(celery_app.main)")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ecommerce_agent"


def test_celery_app_scheduled_tasks_are_registered() -> None:
    """Register every task referenced by the Celery Beat schedule."""
    result = _run_in_fresh_process(
        "from app.celery_app import celery_app\n"
        "celery_app.loader.import_default_modules()\n"
        "scheduled = {entry['task'] for entry in celery_app.conf.beat_schedule.values()}\n"
        "missing = sorted(scheduled.difference(celery_app.tasks))\n"
        "print(','.join(missing))\n"
        "raise SystemExit(bool(missing))"
    )

    assert result.returncode == 0, (
        f"Unregistered scheduled tasks: {result.stdout.strip()}\n{result.stderr}"
    )
