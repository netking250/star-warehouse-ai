from unittest.mock import patch

import pytest

from app.core.llm_factory import create_llm, create_openai_llm
from app.model_gateway.langchain import GatewayChatModel


def test_legacy_openai_factory_returns_gateway_client() -> None:
    client = create_openai_llm(route="intent", temperature=0.2, timeout=3.0)

    assert isinstance(client, GatewayChatModel)
    assert client.route == "intent"
    assert client.temperature == 0.2
    assert client.timeout_seconds == 3.0


def test_legacy_openai_factory_rejects_retry_ownership() -> None:
    with pytest.raises(ValueError, match="T14"):
        create_openai_llm(max_retries=1)


def test_canonical_factory_delegates_to_gateway_client() -> None:
    with patch("app.core.llm_factory.create_model_client") as factory:
        expected = factory.return_value

        result = create_llm(route="evaluation", model="configured-override")

    assert result is expected
    factory.assert_called_once_with(
        "evaluation",
        model_override="configured-override",
        temperature=0,
        timeout=None,
        default_config=None,
    )
