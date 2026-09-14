# app/celery_app.py
"""Celery 异步任务系统
处理短信发送、退款网关调用等耗时操作
"""

from celery import Celery
from kombu import Exchange, Queue

from app.celery_tracing import setup_celery_langsmith_tracing
from app.core.branding import CELERY_APP_NAME
from app.core.config import settings
from app.observability.otel_setup import setup_celery_tracing
from app.task_runtime.context import build_system_task_context
from app.task_runtime.envelope import SystemTaskEnvelope


def _system_envelope(task_name: str, schedule_identity: str, payload: dict) -> dict[str, object]:
    """Build static Beat metadata that explicitly identifies a global task."""
    return SystemTaskEnvelope(
        task_context=build_system_task_context(
            task_name=task_name,
            schedule_identity=schedule_identity,
        ),
        payload=payload,
    ).to_message()


# 创建 Celery 实例
celery_app = Celery(
    CELERY_APP_NAME,
    broker=settings.CELERY_BROKER_URL.get_secret_value(),
    backend=settings.CELERY_RESULT_BACKEND,
)

# Celery 配置
task_exchange = Exchange("tasks", type="direct", durable=True)
dead_letter_exchange = Exchange("tasks.dlx", type="direct", durable=True)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5分钟超时
    task_soft_time_limit=240,  # 4分钟软超时
    task_default_queue="default",
    task_default_exchange="tasks",
    task_default_exchange_type="direct",
    task_default_routing_key="default",
    task_create_missing_queues=False,
    task_queues=(
        Queue("default", task_exchange, routing_key="default", durable=True),
        Queue(
            "critical",
            task_exchange,
            routing_key="critical",
            durable=True,
            queue_arguments={
                "x-dead-letter-exchange": "tasks.dlx",
                "x-dead-letter-routing-key": "critical.dead",
            },
        ),
        Queue("maintenance", task_exchange, routing_key="maintenance", durable=True),
        Queue(
            "critical.dlq",
            dead_letter_exchange,
            routing_key="critical.dead",
            durable=True,
        ),
    ),
    task_routes={
        "refund.*": {"queue": "critical", "routing_key": "critical"},
        "knowledge.sync_document": {"queue": "critical", "routing_key": "critical"},
        "memory.sync_vector": {"queue": "critical", "routing_key": "critical"},
        "alerting.*": {"queue": "maintenance", "routing_key": "maintenance"},
        "autoheal.*": {"queue": "maintenance", "routing_key": "maintenance"},
        "checkpoint.*": {"queue": "maintenance", "routing_key": "maintenance"},
        "compliance.*": {"queue": "maintenance", "routing_key": "maintenance"},
        "memory.prune_vector_memory": {"queue": "maintenance", "routing_key": "maintenance"},
        "notifications.check_quality_alerts": {
            "queue": "maintenance",
            "routing_key": "maintenance",
        },
        "prompt_effect.generate_monthly_report": {
            "queue": "maintenance",
            "routing_key": "maintenance",
        },
        "shadow.run_shadow_test": {"queue": "maintenance", "routing_key": "maintenance"},
        "evaluation.run_adversarial_suite": {
            "queue": "maintenance",
            "routing_key": "maintenance",
        },
    },
    task_acks_late=False,
    task_reject_on_worker_lost=False,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    broker_connection_timeout=2,
    broker_connection_retry_on_startup=True,
    broker_heartbeat=30,
    broker_transport_options={"confirm_publish": True},
    task_publish_retry=True,
    task_publish_retry_policy={
        "max_retries": 3,
        "interval_start": 0,
        "interval_step": 0.5,
        "interval_max": 2,
    },
    beat_schedule={
        "run-compliance-retention-daily": {
            "task": "compliance.run_retention_daily",
            "schedule": 86400.0,
            "kwargs": {"envelope": _system_envelope("compliance.run_retention_daily", "daily", {})},
        },
        "prune-vector-memory-daily": {
            "task": "memory.prune_vector_memory",
            "schedule": 86400.0,
            "kwargs": {"envelope": _system_envelope("memory.prune_vector_memory", "daily", {})},
        },
        "check-quality-alerts": {
            "task": "notifications.check_quality_alerts",
            "schedule": 300.0,
            "kwargs": {
                "envelope": _system_envelope(
                    "notifications.check_quality_alerts", "five-minutes", {}
                )
            },
        },
        "generate-prompt-effect-reports-monthly": {
            "task": "prompt_effect.generate_monthly_report",
            "schedule": 2592000.0,
            "kwargs": {
                "envelope": _system_envelope(
                    "prompt_effect.generate_monthly_report",
                    "monthly",
                    {"agent_name": None, "report_month": None},
                )
            },
        },
        "cleanup-old-checkpoints-daily": {
            "task": "checkpoint.cleanup_old_checkpoints",
            "schedule": 86400.0,
            "kwargs": {
                "envelope": _system_envelope("checkpoint.cleanup_old_checkpoints", "daily", {})
            },
        },
        "check-celery-workers": {
            "task": "autoheal.check_celery_workers",
            "schedule": 300.0,
            "kwargs": {
                "envelope": _system_envelope("autoheal.check_celery_workers", "five-minutes", {})
            },
        },
        "clear-redis-cache": {
            "task": "autoheal.clear_redis_cache",
            "schedule": 600.0,
            "kwargs": {
                "envelope": _system_envelope("autoheal.clear_redis_cache", "ten-minutes", {})
            },
        },
        "restart-stuck-workers": {
            "task": "autoheal.restart_stuck_workers",
            "schedule": 300.0,
            "kwargs": {
                "envelope": _system_envelope("autoheal.restart_stuck_workers", "five-minutes", {})
            },
        },
        "clear-expired-redis-keys": {
            "task": "autoheal.clear_expired_redis_keys",
            "schedule": 600.0,
            "kwargs": {
                "envelope": _system_envelope("autoheal.clear_expired_redis_keys", "ten-minutes", {})
            },
        },
        "check-db-pool-health": {
            "task": "autoheal.check_db_pool_health",
            "schedule": 300.0,
            "kwargs": {
                "envelope": _system_envelope("autoheal.check_db_pool_health", "five-minutes", {})
            },
        },
        "evaluate-alert-rules": {
            "task": "alerting.evaluate_rules",
            "schedule": 60.0,
            "kwargs": {"envelope": _system_envelope("alerting.evaluate_rules", "minutely", {})},
        },
        "check-service-health": {
            "task": "alerting.check_service_health",
            "schedule": 30.0,
            "kwargs": {
                "envelope": _system_envelope("alerting.check_service_health", "30-seconds", {})
            },
        },
        "run-shadow-tests": {
            "task": "shadow.run_shadow_test",
            "schedule": 60.0,
            "kwargs": {
                "envelope": _system_envelope(
                    "shadow.run_shadow_test",
                    "minutely",
                    {"query": "test query"},
                )
            },
        },
        "run-adversarial-suite": {
            "task": "evaluation.run_adversarial_suite",
            "schedule": 86400.0,
            "kwargs": {
                "envelope": _system_envelope(
                    "evaluation.run_adversarial_suite",
                    "daily",
                    {"triggered_by": "scheduled"},
                )
            },
        },
    },
)

# Configure LangSmith tracing for Celery workers BEFORE autodiscover (env vars must be set before potential langchain imports)
setup_celery_langsmith_tracing()

# 自动发现任务
celery_app.autodiscover_tasks(["app.tasks"])

# Instrument Celery with OpenTelemetry tracing
setup_celery_tracing()
