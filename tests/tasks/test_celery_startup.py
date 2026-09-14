"""Regression tests for loading the Celery application."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import tests._db_config  # noqa: F401  configure isolated services before app imports

PROJECT_ROOT = Path(__file__).parents[2]


def _run_in_fresh_process(script: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["POSTGRES_DB"] = "test_star_warehouse_ai_startup"
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_celery_app_fresh_process_import_succeeds() -> None:
    """Load the Celery application without hitting a circular import."""
    result = _run_in_fresh_process("from app.celery_app import celery_app; print(celery_app.main)")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "star_warehouse_ai"


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


def test_celery_app_routes_reliable_tasks_to_rabbitmq_queues() -> None:
    """Keep reliable work isolated with late acknowledgements and a real DLX."""
    from app.celery_app import celery_app

    celery_app.loader.import_default_modules()
    queues = {queue.name: queue for queue in celery_app.conf.task_queues}

    assert set(queues) == {"critical", "default", "maintenance", "critical.dlq"}
    assert queues["critical"].queue_arguments == {
        "x-dead-letter-exchange": "tasks.dlx",
        "x-dead-letter-routing-key": "critical.dead",
    }
    assert queues["critical.dlq"].exchange.name == "tasks.dlx"
    assert queues["critical.dlq"].routing_key == "critical.dead"
    assert celery_app.amqp.router.route({}, "refund.process_payment")["queue"].name == "critical"
    assert celery_app.amqp.router.route({}, "knowledge.sync_document")["queue"].name == "critical"
    assert celery_app.amqp.router.route({}, "autoheal.check_db_pool")["queue"].name == "maintenance"
    assert (
        celery_app.amqp.router.route({}, "memory.prune_vector_memory")["queue"].name
        == "maintenance"
    )
    assert celery_app.conf.worker_prefetch_multiplier == 1

    for task_name in ("refund.process_payment", "refund.send_sms", "refund.notify_admin"):
        task = celery_app.tasks[task_name]
        assert task.ignore_result is True
        assert task.acks_late is True
        assert task.acks_on_failure_or_timeout is False
        assert task.reject_on_worker_lost is True


def test_celery_beat_entries_carry_explicit_system_context() -> None:
    """Never infer a default tenant for global scheduled work."""
    from app.celery_app import celery_app
    from app.task_runtime.envelope import SystemTaskEnvelope

    for entry in celery_app.conf.beat_schedule.values():
        envelope = SystemTaskEnvelope.from_message(entry["kwargs"]["envelope"])
        assert envelope.task_context.scope == "system"
        assert envelope.task_context.tenant_id is None
        assert envelope.task_context.idempotency_key
