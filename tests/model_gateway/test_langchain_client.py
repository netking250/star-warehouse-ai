"""Compatibility tests for existing LangGraph/LangChain callers."""

import pytest
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.model_gateway.contracts import (
    ModelCandidate,
    ModelRoute,
    ModelToolCall,
)
from app.model_gateway.gateway import ModelGateway
from app.model_gateway.langchain import GatewayChatModel
from app.model_gateway.providers.mock import MockProviderAdapter


def _client(adapter: MockProviderAdapter) -> GatewayChatModel:
    candidate = ModelCandidate(
        provider="mock",
        model="mock-chat",
        capabilities=adapter.capabilities,
        timeout_seconds=1.0,
    )
    gateway = ModelGateway(
        adapters=[adapter],
        routes=[ModelRoute(name="default_chat", candidates=(candidate,))],
    )
    return GatewayChatModel(gateway=gateway, route="default_chat")


@pytest.mark.asyncio
async def test_langchain_client_returns_normalized_provider_metadata() -> None:
    response = await _client(MockProviderAdapter(content="hello")).ainvoke(
        [HumanMessage(content="hi")]
    )

    assert response.content == "hello"
    assert response.response_metadata["provider"] == "mock"
    assert response.response_metadata["model"] == "mock-chat"


@pytest.mark.asyncio
async def test_langchain_client_streams_provider_neutral_chunks() -> None:
    chunks = [
        chunk
        async for chunk in _client(MockProviderAdapter(stream_chunks=("hel", "lo"))).astream(
            [HumanMessage(content="hi")]
        )
    ]

    assert "".join(str(chunk.content) for chunk in chunks) == "hello"
    assert any(chunk.response_metadata.get("provider") == "mock" for chunk in chunks)


@pytest.mark.asyncio
async def test_langchain_structured_output_uses_normalized_tool_call() -> None:
    class Decision(BaseModel):
        accepted: bool

    adapter = MockProviderAdapter(
        content="",
        tool_calls=(
            ModelToolCall(
                id="call-1",
                name="Decision",
                arguments={"accepted": True},
            ),
        ),
    )
    structured = _client(adapter).with_structured_output(Decision)

    result = await structured.ainvoke([HumanMessage(content="decide")])

    assert result == Decision(accepted=True)
