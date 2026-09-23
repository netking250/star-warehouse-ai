"""Regression tests for the Docker startup workflow."""

from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_docker_start_script_runs_canonical_bootstrap_before_runtime() -> None:
    """Ensure schema, roles, and local data are ready before runtime roles start."""
    script = (REPOSITORY_ROOT / "start_docker.sh").read_text(encoding="utf-8")

    assert (
        "--force-recreate --no-deps celery_worker celery_maintenance celery_scheduler "
        "outbox_relay app" in script
    )
    migration = script.index("alembic upgrade head")
    head_check = script.index("alembic current --check-heads")
    roles = script.index("python -m app.core.database_roles")
    bootstrap = script.index("python -m scripts.bootstrap_local_data")
    runtime = script.index(
        "--force-recreate --no-deps celery_worker celery_maintenance celery_scheduler "
    )
    assert migration < head_check < roles < bootstrap < runtime
    assert 'ENV_FILE="${ENV_FILE:-.env}"' in script
    assert 'COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-star-warehouse-ai}"' in script
    assert 'docker compose --project-name "$COMPOSE_PROJECT_NAME"' in script
    assert 'APP_HOST_PORT="${APP_HOST_PORT:-8000}"' in script
    assert 'export CORS_ORIGINS="${CORS_ORIGINS:-[' in script
    assert "http://localhost:${APP_HOST_PORT}" in script
    assert "http://localhost:${APP_HOST_PORT}/health" in script
    assert "python -m scripts.verify_local_stack" in script
    assert (
        '--api-base-url http://app:8000 --browser-origin "http://localhost:${APP_HOST_PORT}"'
        in script
    )
    assert "docker compose down -v" not in script

    verifier = (REPOSITORY_ROOT / "scripts" / "verify_local_stack.py").read_text(encoding="utf-8")
    assert "create_async_engine(settings.MIGRATION_DATABASE_URL" in verifier
    assert 'text("SELECT version_num FROM alembic_version")' in verifier


def test_compose_uses_container_addresses_and_checks_api_health() -> None:
    """Ensure containers do not use localhost for sibling dependencies."""
    compose = yaml.safe_load((REPOSITORY_ROOT / "docker-compose.yaml").read_text(encoding="utf-8"))

    for service_name in ("app", "celery_worker", "celery_maintenance"):
        environment = compose["services"][service_name]["environment"]
        assert environment["POSTGRES_SERVER"] == "db"
        assert environment["REDIS_HOST"] == "redis"
        assert environment["QDRANT_URL"] == "http://qdrant:6333"

    assert compose["services"]["app"]["healthcheck"]["test"] == [
        "CMD",
        "python",
        "-c",
        (
            "import urllib.request; "
            "urllib.request.urlopen('http://localhost:8000/health', timeout=5)"
        ),
    ]


def test_compose_uses_healthy_rabbitmq_broker_and_isolated_dlq() -> None:
    """Make RabbitMQ the broker without exposing its management UI publicly."""
    compose = yaml.safe_load((REPOSITORY_ROOT / "docker-compose.yaml").read_text(encoding="utf-8"))

    rabbitmq = compose["services"]["rabbitmq"]
    assert rabbitmq["image"] == "rabbitmq:3.13-management"
    assert rabbitmq["ports"] == [
        "127.0.0.1:${RABBITMQ_HOST_PORT:-5672}:5672",
        "127.0.0.1:${RABBITMQ_MANAGEMENT_HOST_PORT:-15672}:15672",
    ]
    assert rabbitmq["environment"]["RABBITMQ_DEFAULT_USER"].startswith("${RABBITMQ_USER")
    assert (
        rabbitmq["environment"]["RABBITMQ_DEFAULT_PASS"]
        == "${RABBITMQ_PASSWORD:-dev-rabbitmq-password}"
    )
    assert "rabbitmq-diagnostics" in " ".join(rabbitmq["healthcheck"]["test"])

    for service_name in (
        "app",
        "celery_worker",
        "celery_maintenance",
        "celery_scheduler",
        "outbox_relay",
    ):
        service = compose["services"][service_name]
        assert service["environment"]["POSTGRES_RUNTIME_USER"].startswith("${POSTGRES_RUNTIME_USER")
        assert service["environment"]["POSTGRES_RUNTIME_PASSWORD"] == (
            "${POSTGRES_RUNTIME_PASSWORD:-}"
        )
        assert service["environment"]["POSTGRES_MAINTENANCE_USER"].startswith(
            "${POSTGRES_MAINTENANCE_USER"
        )
        assert service["environment"]["POSTGRES_MAINTENANCE_PASSWORD"] == (
            "${POSTGRES_MAINTENANCE_PASSWORD:-}"
        )
        assert service["environment"]["CELERY_BROKER_URL"].startswith("amqp://")
        assert "@rabbitmq:5672//" in service["environment"]["CELERY_BROKER_URL"]
        assert service["depends_on"]["rabbitmq"]["condition"] == "service_healthy"

    worker_command = compose["services"]["celery_worker"]["command"]
    assert "--queues=critical,default" in worker_command
    assert "maintenance" not in worker_command
    assert "critical.dlq" not in worker_command
    assert "--beat" not in worker_command
    maintenance_command = compose["services"]["celery_maintenance"]["command"]
    assert "--queues=maintenance" in maintenance_command
    assert compose["services"]["celery_worker"]["environment"]["DB_CAPABILITY"] == "runtime"
    assert (
        compose["services"]["celery_maintenance"]["environment"]["DB_CAPABILITY"] == "maintenance"
    )
    assert compose["services"]["outbox_relay"]["environment"]["DB_CAPABILITY"] == "maintenance"
    assert compose["services"]["celery_scheduler"]["command"].startswith(
        "celery -A app.celery_app beat"
    )
    assert compose["services"]["outbox_relay"]["command"] == "python -m app.outbox"


def test_compose_uses_project_scoped_names_and_loopback_infrastructure_ports() -> None:
    """Avoid global container names and public development infrastructure ports."""
    compose = yaml.safe_load((REPOSITORY_ROOT / "docker-compose.yaml").read_text(encoding="utf-8"))
    monitoring = yaml.safe_load(
        (REPOSITORY_ROOT / "docker-compose.monitoring.yml").read_text(encoding="utf-8")
    )

    for service in (*compose["services"].values(), *monitoring["services"].values()):
        assert "container_name" not in service

    assert compose["services"]["db"]["ports"] == ["127.0.0.1:${POSTGRES_HOST_PORT:-5432}:5432"]
    assert compose["services"]["redis"]["ports"] == ["127.0.0.1:${REDIS_HOST_PORT:-6379}:6379"]
    assert compose["services"]["qdrant"]["ports"] == [
        "127.0.0.1:${QDRANT_HTTP_HOST_PORT:-6333}:6333",
        "127.0.0.1:${QDRANT_GRPC_HOST_PORT:-6334}:6334",
    ]
    assert compose["services"]["app"]["ports"] == ["127.0.0.1:${APP_HOST_PORT:-8000}:8000"]
    assert (
        compose["services"]["app"]["environment"]["BROWSER_AUTH_COOKIE_SECURE"]
        == "${BROWSER_AUTH_COOKIE_SECURE:-false}"
    )
    assert compose["services"]["app"]["environment"]["CORS_ORIGINS"].startswith("${CORS_ORIGINS:-")


def test_compose_can_use_an_explicit_untracked_application_env_file() -> None:
    """Allow disposable projects to use isolated settings without editing .env."""
    compose = yaml.safe_load((REPOSITORY_ROOT / "docker-compose.yaml").read_text(encoding="utf-8"))

    for service_name in (
        "app",
        "celery_worker",
        "celery_maintenance",
        "celery_scheduler",
        "outbox_relay",
    ):
        assert compose["services"][service_name]["env_file"] == ["${APP_ENV_FILE:-.env}"]


def test_compose_shares_canonical_local_knowledge_storage_with_required_processes() -> None:
    compose = yaml.safe_load((REPOSITORY_ROOT / "docker-compose.yaml").read_text(encoding="utf-8"))

    expected_root = "/app/uploads/knowledge"
    expected_mount = "knowledge_uploads:/app/uploads"
    for service_name in ("app", "celery_worker", "celery_maintenance"):
        service = compose["services"][service_name]
        assert service["environment"]["KNOWLEDGE_UPLOAD_DIR"] == expected_root
        assert expected_mount in service["volumes"]

    for service_name in ("celery_scheduler", "outbox_relay"):
        assert expected_mount not in compose["services"][service_name]["volumes"]

    assert "knowledge_uploads" in compose["volumes"]


def test_image_prepares_non_root_writable_knowledge_volume_mountpoint() -> None:
    dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")

    create_mountpoint = dockerfile.index("mkdir -p /app/uploads/knowledge")
    assign_ownership = dockerfile.index("chown -R appuser:appgroup /app")
    drop_privileges = dockerfile.index("USER appuser")
    assert create_mountpoint < assign_ownership < drop_privileges
