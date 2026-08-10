"""Tests for tracing configuration safeguards."""

from app.core.tracing import is_placeholder_api_key


def test_placeholder_api_keys_are_rejected():
    assert is_placeholder_api_key("")
    assert is_placeholder_api_key("your-langsmith-api-key")
    assert is_placeholder_api_key("replace-me")


def test_realistic_api_key_is_accepted():
    assert not is_placeholder_api_key("lsv2_pt_realistic-key-value")
