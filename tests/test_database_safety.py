"""Regression tests for destructive test-database setup safeguards."""

import pytest

from tests._db_config import assert_test_database


def test_assert_test_database_rejects_non_test_database() -> None:
    """Ensure test setup cannot drop tables in a development database."""
    with pytest.raises(RuntimeError, match="Refusing destructive test setup"):
        assert_test_database("knowledge_base")


def test_assert_test_database_accepts_prefixed_test_database() -> None:
    """Allow destructive setup only for explicitly test-prefixed databases."""
    assert_test_database("test_knowledge_base")
