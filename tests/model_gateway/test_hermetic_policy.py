"""Tests for explicit real-provider opt-in policy."""

from tests._llm import real_llm_skip_reason


def test_valid_credentials_without_explicit_opt_in_remain_skipped() -> None:
    reason = real_llm_skip_reason(
        explicit_opt_in=False,
        openai_key="sk-valid-looking-provider-key",
        dashscope_key="dashscope-valid-looking-key",
    )

    assert reason is not None
    assert "explicit" in reason.lower()


def test_dummy_or_missing_credentials_skip_cleanly() -> None:
    reason = real_llm_skip_reason(
        explicit_opt_in=True,
        openai_key="sk-test",
        dashscope_key="",
    )

    assert reason is not None
    assert "usable" in reason.lower()


def test_explicit_opt_in_with_valid_configuration_allows_fixture() -> None:
    reason = real_llm_skip_reason(
        explicit_opt_in=True,
        openai_key="sk-valid-looking-provider-key",
        dashscope_key="dummy",
    )

    assert reason is None
