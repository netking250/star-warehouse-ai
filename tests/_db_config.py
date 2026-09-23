import os
import urllib.parse

_LOOPBACK_PROXY_BYPASS = ("localhost", "127.0.0.1", "::1")


def assert_test_database(database_name: str) -> None:
    """Reject destructive test setup against a non-test database.

    Args:
        database_name: PostgreSQL database selected by application settings.

    Raises:
        RuntimeError: If the database name does not use the required test prefix.
    """
    if not database_name.startswith("test_"):
        raise RuntimeError(
            f"Refusing destructive test setup for non-test database {database_name!r}; "
            "the database name must start with 'test_'."
        )


def assert_test_rabbitmq_url(url: str) -> None:
    """Reject real RabbitMQ integration tests outside a dedicated test vhost."""
    parsed = urllib.parse.urlparse(url)
    vhost = urllib.parse.unquote(parsed.path.lstrip("/"))
    if not vhost.startswith("test_"):
        raise RuntimeError(
            "Refusing RabbitMQ integration tests outside a test vhost; "
            "T04_RABBITMQ_URL must select a vhost whose name starts with 'test_'."
        )


def _configure_test_database() -> None:
    """在导入 app 模块前配置测试数据库，确保测试数据隔离。"""
    # 如果已设置 TEST_DATABASE_URL，直接提取数据库名并覆盖 POSTGRES_DB
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url:
        parsed = urllib.parse.urlparse(test_url)
        db_name = parsed.path.lstrip("/")
        os.environ["POSTGRES_DB"] = db_name
        return

    original_db = os.environ.get("POSTGRES_DB")
    if original_db and not original_db.startswith("test_"):
        os.environ["POSTGRES_DB"] = f"test_{original_db}"
    elif not original_db:
        os.environ["POSTGRES_DB"] = "test_star_warehouse_ai"

    os.environ.setdefault("RERANK_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")


def _configure_test_services() -> None:
    """Select isolated stores and transports before application imports."""
    # Normal tests are hermetic even when a developer .env enables hosted tracing.
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"
    existing_no_proxy: list[str] = []
    seen_no_proxy: set[str] = set()
    for variable in ("NO_PROXY", "no_proxy"):
        for value in os.environ.get(variable, "").split(","):
            normalized = value.strip()
            if normalized and normalized.lower() not in seen_no_proxy:
                existing_no_proxy.append(normalized)
                seen_no_proxy.add(normalized.lower())
    for host in _LOOPBACK_PROXY_BYPASS:
        if host not in seen_no_proxy:
            existing_no_proxy.append(host)
            seen_no_proxy.add(host)
    no_proxy = ",".join(existing_no_proxy)
    os.environ["NO_PROXY"] = no_proxy
    os.environ["no_proxy"] = no_proxy

    os.environ["REDIS_DB"] = "15"
    os.environ["QDRANT_COLLECTION_NAME"] = f"test_star_warehouse_ai_{os.getpid()}"
    os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"

    rabbitmq_url = os.environ.get("T04_RABBITMQ_URL")
    if rabbitmq_url:
        assert_test_rabbitmq_url(rabbitmq_url)
        os.environ["CELERY_BROKER_URL"] = rabbitmq_url
    else:
        os.environ["CELERY_BROKER_URL"] = "memory://"


_configure_test_database()
_configure_test_services()
