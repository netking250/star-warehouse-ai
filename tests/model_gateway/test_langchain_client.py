"""Compatibility tests for existing LangGraph/LangChain callers."""

from collections.abc import AsyncIterator

import pytest
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.model_gateway.contracts import (
    ModelCandidate,
    ModelCapability,
    ModelRequest,
    ModelResponse,
    ModelRoute,
    ModelStreamEvent,
    ModelToolCall,
)
from app.model_gateway.errors import ModelErrorCategory
from app.model_gateway.gateway import ModelGateway
from app.model_gateway.langchain import GatewayChatModel, GatewayChatModelError
from app.model_gateway.providers.mock import MockProviderAdapter


class _RecordingAdapter(MockProviderAdapter):
    def __init__(
        self,
        *,
        content: str = "mock response",
        stream_chunks: tuple[str, ...] | None = None,
    ) -> None:
        super().__init__(content=content, stream_chunks=stream_chunks)
        self.invoke_requests: list[ModelRequest] = []
        self.stream_requests: list[ModelRequest] = []

    async def invoke(self, candidate: ModelCandidate, request: ModelRequest) -> ModelResponse:
        self.invoke_requests.append(request)
        return await super().invoke(candidate, request)

    async def stream(
        self, candidate: ModelCandidate, request: ModelRequest
    ) -> AsyncIterator[ModelStreamEvent]:
        self.stream_requests.append(request)
        async for event in super().stream(candidate, request):
            yield event


def _client(
    adapter: MockProviderAdapter,
    *,
    capabilities: frozenset[ModelCapability] | None = None,
) -> GatewayChatModel:
    candidate = ModelCandidate(
        provider="mock",
        model="mock-chat",
        capabilities=capabilities or adapter.capabilities,
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
async def test_ainvoke_chat_only_candidate_uses_non_streaming_gateway_request() -> None:
    adapter = _RecordingAdapter(content="hello")
    response = await _client(
        adapter,
        capabilities=frozenset({ModelCapability.CHAT}),
    ).ainvoke([HumanMessage(content="hi")])

    assert response.content == "hello"
    assert len(adapter.invoke_requests) == 1
    assert adapter.invoke_requests[0].stream is False
    assert adapter.invoke_requests[0].required_capabilities == frozenset({ModelCapability.CHAT})
    assert adapter.stream_requests == []


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
async def test_astream_chat_only_candidate_is_rejected_before_provider_call() -> None:
    adapter = _RecordingAdapter(content="must not stream")
    model = _client(
        adapter,
        capabilities=frozenset({ModelCapability.CHAT}),
    )

    with pytest.raises(GatewayChatModelError) as exc_info:
        _chunks = [chunk async for chunk in model.astream([HumanMessage(content="hi")])]

    assert exc_info.value.gateway_error.category is ModelErrorCategory.UNSUPPORTED_CAPABILITY
    assert "chat, streaming" in str(exc_info.value)
    assert adapter.invoke_requests == []
    assert adapter.stream_requests == []


@pytest.mark.asyncio
async def test_astream_streaming_candidate_uses_streaming_gateway_request() -> None:
    adapter = _RecordingAdapter(stream_chunks=("hel", "lo"))
    chunks = [
        chunk
        async for chunk in _client(
            adapter,
            capabilities=frozenset({ModelCapability.CHAT, ModelCapability.STREAMING}),
        ).astream([HumanMessage(content="hi")])
    ]

    assert "".join(str(chunk.content) for chunk in chunks) == "hello"
    assert len(adapter.stream_requests) == 1
    assert adapter.stream_requests[0].stream is True
    assert adapter.stream_requests[0].required_capabilities == frozenset(
        {ModelCapability.CHAT, ModelCapability.STREAMING}
    )
    assert adapter.invoke_requests == []


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
