import os


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


def _configure_test_database() -> None:
    """在导入 app 模块前配置测试数据库，确保测试数据隔离。"""
    # 如果已设置 TEST_DATABASE_URL，直接提取数据库名并覆盖 POSTGRES_DB
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url:
        import urllib.parse

        parsed = urllib.parse.urlparse(test_url)
        db_name = parsed.path.lstrip("/")
        os.environ["POSTGRES_DB"] = db_name
        return

    original_db = os.environ.get("POSTGRES_DB")
    if original_db and not original_db.startswith("test_"):
        os.environ["POSTGRES_DB"] = f"test_{original_db}"
    elif not original_db:
        os.environ["POSTGRES_DB"] = "test_ecommerce_agent"

    os.environ.setdefault("RERANK_BASE_URL", "https://dashscope.aliyuncs.com/compatible-api/v1")


_configure_test_database()
