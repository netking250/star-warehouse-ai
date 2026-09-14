"""Regression tests for the Docker startup workflow."""

from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_docker_start_script_recreates_application_containers() -> None:
    """Ensure stale WSL bind mounts are replaced during Docker startup."""
    script = (REPOSITORY_ROOT / "start_docker.sh").read_text(encoding="utf-8")

    assert (
        "--force-recreate --no-deps celery_worker celery_maintenance celery_scheduler "
        "outbox_relay app" in script
    )
    assert "alembic upgrade head" in script
    assert "python -m app.core.database_roles" in script
    assert "python scripts/initialize_vector_data.py" in script
    assert "http://localhost:8000/health" in script


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
    assert rabbitmq["ports"] == ["127.0.0.1:5672:5672", "127.0.0.1:15672:15672"]
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

    assert compose["services"]["db"]["ports"] == ["127.0.0.1:5432:5432"]
    assert compose["services"]["redis"]["ports"] == ["127.0.0.1:6379:6379"]
    assert compose["services"]["qdrant"]["ports"] == [
        "127.0.0.1:6333:6333",
        "127.0.0.1:6334:6334",
    ]
    assert compose["services"]["app"]["ports"] == ["8000:8000"]
