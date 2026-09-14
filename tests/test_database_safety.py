"""Regression tests for destructive test-database setup safeguards."""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.database import async_session_maker
from tests._db_config import assert_test_database, assert_test_rabbitmq_url


def test_assert_test_database_rejects_non_test_database() -> None:
    """Ensure test setup cannot drop tables in a development database."""
    with pytest.raises(RuntimeError, match="Refusing destructive test setup"):
        assert_test_database("knowledge_base")


def test_assert_test_database_accepts_prefixed_test_database() -> None:
    """Allow destructive setup only for explicitly test-prefixed databases."""
    assert_test_database("test_knowledge_base")


def test_assert_test_rabbitmq_url_rejects_default_vhost() -> None:
    """Prevent real integration tests from sharing development queues."""
    with pytest.raises(RuntimeError, match="test vhost"):
        assert_test_rabbitmq_url("amqp://guest:guest@localhost:5672//")


def test_assert_test_rabbitmq_url_accepts_test_vhost() -> None:
    """Allow a dedicated RabbitMQ test namespace."""
    assert_test_rabbitmq_url("amqp://guest:guest@localhost:5672/test_star_warehouse_ai")


def test_test_infrastructure_defaults_are_isolated_from_development() -> None:
    """Keep generic test runs away from development Redis, Qdrant, and brokers."""
    assert os.environ["REDIS_DB"] == "15"
    assert os.environ["QDRANT_COLLECTION_NAME"].startswith("test_star_warehouse_ai_")
    assert os.environ["CELERY_RESULT_BACKEND"] == "cache+memory://"
    for variable in ("NO_PROXY", "no_proxy"):
        loopback_hosts = {
            value.strip().lower() for value in os.environ[variable].split(",") if value.strip()
        }
        assert {"localhost", "127.0.0.1"} <= loopback_hosts

    rabbitmq_url = os.environ.get("T04_RABBITMQ_URL")
    expected_broker = rabbitmq_url or "memory://"
    assert os.environ["CELERY_BROKER_URL"] == expected_broker


@pytest.mark.asyncio
async def test_test_maintenance_connection_can_truncate_protected_table(
    test_maintenance_engine: AsyncEngine,
) -> None:
    """Allow only the explicit test-maintenance connection to reset protected fixtures."""
    async with test_maintenance_engine.begin() as connection:
        await connection.execute(text("TRUNCATE TABLE task_execution_receipts RESTART IDENTITY"))


@pytest.mark.asyncio
async def test_runtime_test_session_cannot_truncate_protected_table(db_setup: None) -> None:
    """Keep production-like runtime sessions unable to perform destructive cleanup."""
    async with async_session_maker() as session:
        connection = await session.connection()
        assert await connection.scalar(text("SELECT current_user")) == "star_warehouse_runtime"
        with pytest.raises(
            DBAPIError,
            match="(?i)permission denied|must be owner|not enough privilege",
        ):
            await connection.execute(text("TRUNCATE TABLE task_execution_receipts"))
