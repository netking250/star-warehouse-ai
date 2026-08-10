"""Regression tests for the Docker startup workflow."""

from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_docker_start_script_recreates_application_containers() -> None:
    """Ensure stale WSL bind mounts are replaced during Docker startup."""
    script = (REPOSITORY_ROOT / "start_docker.sh").read_text(encoding="utf-8")

    assert "--force-recreate --no-deps celery_worker app" in script
    assert "alembic upgrade head" in script
    assert "python scripts/initialize_vector_data.py" in script
    assert "http://localhost:8000/health" in script


def test_compose_uses_container_addresses_and_checks_api_health() -> None:
    """Ensure containers do not use localhost for sibling dependencies."""
    compose = yaml.safe_load((REPOSITORY_ROOT / "docker-compose.yaml").read_text(encoding="utf-8"))

    for service_name in ("app", "celery_worker"):
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
