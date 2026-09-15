"""Shared offline contract tests for real provider adapters."""

import asyncio
import json
from collections.abc import Callable, Coroutine

import httpx
import pytest
from openai import AsyncOpenAI

from app.model_gateway.contracts import (
    ModelCandidate,
    ModelMessage,
    ModelRequest,
    ModelStreamEventType,
    ModelTool,
    ModelToolChoice,
    StructuredOutput,
)
from app.model_gateway.errors import ModelErrorCategory, ModelGatewayError
from app.model_gateway.providers.dashscope import DashScopeProviderAdapter
from app.model_gateway.providers.openai import OpenAIProviderAdapter
from app.model_gateway.providers.openai_compatible import OpenAICompatibleProviderAdapter

type MockHandler = (
    Callable[[httpx.Request], httpx.Response]
    | Callable[[httpx.Request], Coroutine[None, None, httpx.Response]]
)


def _adapter(
    provider: str,
    handler: MockHandler,
) -> tuple[OpenAICompatibleProviderAdapter, ModelCandidate, AsyncOpenAI]:
    client = AsyncOpenAI(
        api_key="sk-test",
        base_url="https://configured.example/v1",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    adapter: OpenAICompatibleProviderAdapter
    if provider == "openai":
        adapter = OpenAIProviderAdapter(client=client)
    else:
        adapter = DashScopeProviderAdapter(client=client)
    return (
        adapter,
        ModelCandidate(
            provider=provider,
            model=f"{provider}-model",
            capabilities=adapter.capabilities,
            timeout_seconds=1.0,
        ),
        client,
    )


def _completion(
    *,
    model: str = "resolved-model",
    content: str | None = "ok",
    tool_calls: list[dict[str, object]] | None = None,
    choices: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    if choices is None:
        message: dict[str, object] = {"role": "assistant", "content": content}
        if tool_calls is not None:
            message["tool_calls"] = tool_calls
        choices = [{"index": 0, "message": message, "finish_reason": "stop"}]
    return {
        "id": "safe-request-id",
        "object": "chat.completion",
        "created": 1,
        "model": model,
        "choices": choices,
        "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5},
    }


@pytest.mark.parametrize("provider", ["openai", "dashscope"])
@pytest.mark.asyncio
async def test_provider_streams_normalized_text_and_completion(provider: str) -> None:
    body = "\n\n".join(
        [
            'data: {"id":"stream-id","object":"chat.completion.chunk","created":1,'
            '"model":"resolved-model","choices":[{"index":0,"delta":{"content":"hel"},'
            '"finish_reason":null}]}',
            'data: {"id":"stream-id","object":"chat.completion.chunk","created":1,'
            '"model":"resolved-model","choices":[{"index":0,"delta":{"content":"lo"},'
            '"finish_reason":"stop"}]}',
            'data: {"id":"stream-id","object":"chat.completion.chunk","created":1,'
            '"model":"resolved-model","choices":[],"usage":{"prompt_tokens":2,'
            '"completion_tokens":1,"total_tokens":3}}',
            "data: [DONE]",
            "",
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream_options"] == {"include_usage": True}
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    adapter, candidate, client = _adapter(provider, handler)
    request = ModelRequest(
        route="default_chat",
        messages=(ModelMessage(role="user", content="hi"),),
        stream=True,
    )
    try:
        events = [event async for event in adapter.stream(candidate, request)]
    finally:
        await client.close()

    assert [event.event_type for event in events] == [
        ModelStreamEventType.TEXT_DELTA,
        ModelStreamEventType.TEXT_DELTA,
        ModelStreamEventType.COMPLETED,
    ]
    assert "".join(event.text_delta for event in events) == "hello"
    assert events[-1].provider == provider
    assert events[-1].model == "resolved-model"
    assert events[-1].usage is not None
    assert events[-1].usage.total_tokens == 3


@pytest.mark.parametrize("provider", ["openai", "dashscope"])
@pytest.mark.asyncio
async def test_provider_normalizes_tool_calls(provider: str) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json=_completion(
                content=None,
                tool_calls=[
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "lookup", "arguments": '{"order_id":"42"}'},
                    }
                ],
            ),
        )

    adapter, candidate, client = _adapter(provider, handler)
    request = ModelRequest(
        route="intent",
        messages=(ModelMessage(role="user", content="lookup"),),
        tools=(ModelTool(name="lookup", input_schema={"type": "object"}),),
        tool_choice=ModelToolChoice(mode="required", name="lookup"),
    )
    try:
        response = await adapter.invoke(candidate, request)
    finally:
        await client.close()

    assert captured["tool_choice"] == {
        "type": "function",
        "function": {"name": "lookup"},
    }
    assert response.tool_calls[0].id == "call-1"
    assert response.tool_calls[0].name == "lookup"
    assert response.tool_calls[0].arguments == {"order_id": "42"}


@pytest.mark.parametrize("provider", ["openai", "dashscope"])
@pytest.mark.asyncio
async def test_provider_normalizes_structured_output(provider: str) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_completion(content='{"safe":true}'))

    adapter, candidate, client = _adapter(provider, handler)
    request = ModelRequest(
        route="structured",
        messages=(ModelMessage(role="user", content="check"),),
        structured_output=StructuredOutput(
            name="safety",
            schema={
                "type": "object",
                "properties": {"safe": {"type": "boolean"}},
                "required": ["safe"],
            },
        ),
    )
    try:
        response = await adapter.invoke(candidate, request)
    finally:
        await client.close()

    assert captured["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "safety",
            "schema": {
                "type": "object",
                "properties": {"safe": {"type": "boolean"}},
                "required": ["safe"],
            },
            "strict": True,
        },
    }
    assert response.structured_output == {"safe": True}


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, ModelErrorCategory.AUTHENTICATION),
        (429, ModelErrorCategory.RATE_LIMIT),
        (503, ModelErrorCategory.PROVIDER_UNAVAILABLE),
    ],
)
@pytest.mark.parametrize("provider", ["openai", "dashscope"])
@pytest.mark.asyncio
async def test_provider_normalizes_http_errors(
    provider: str, status_code: int, expected: ModelErrorCategory
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            headers={"x-request-id": "safe-error-id"},
            json={"error": {"message": "upstream detail", "type": "provider_error"}},
        )

    adapter, candidate, client = _adapter(provider, handler)
    try:
        with pytest.raises(ModelGatewayError) as exc_info:
            await adapter.invoke(
                candidate,
                ModelRequest(
                    route="default_chat",
                    messages=(ModelMessage(role="user", content="hi"),),
                ),
            )
    finally:
        await client.close()

    assert exc_info.value.category is expected
    assert str(exc_info.value) == "Provider request failed"
    assert exc_info.value.provider_request_id == "safe-error-id"


@pytest.mark.parametrize("provider", ["openai", "dashscope"])
@pytest.mark.asyncio
async def test_provider_preserves_numeric_retry_after_hint(provider: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "12", "x-request-id": "safe-error-id"},
            json={"error": {"message": "rate limited"}},
        )

    adapter, candidate, client = _adapter(provider, handler)
    try:
        with pytest.raises(ModelGatewayError) as exc_info:
            await adapter.invoke(
                candidate,
                ModelRequest(
                    route="default_chat",
                    messages=(ModelMessage(role="user", content="hi"),),
                ),
            )
    finally:
        await client.close()

    assert exc_info.value.category is ModelErrorCategory.RATE_LIMIT
    assert exc_info.value.retry_after_seconds == 12.0


@pytest.mark.parametrize("provider", ["openai", "dashscope"])
@pytest.mark.asyncio
async def test_provider_timeout_is_normalized(provider: str) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.05)
        return httpx.Response(200, json=_completion())

    adapter, candidate, client = _adapter(provider, handler)
    try:
        with pytest.raises(ModelGatewayError) as exc_info:
            await adapter.invoke(
                candidate,
                ModelRequest(
                    route="default_chat",
                    messages=(ModelMessage(role="user", content="hi"),),
                    timeout_seconds=0.001,
                ),
            )
    finally:
        await client.close()

    assert exc_info.value.category is ModelErrorCategory.TIMEOUT


@pytest.mark.parametrize("provider", ["openai", "dashscope"])
@pytest.mark.asyncio
async def test_provider_invalid_response_is_normalized(provider: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_completion(choices=[]))

    adapter, candidate, client = _adapter(provider, handler)
    try:
        with pytest.raises(ModelGatewayError) as exc_info:
            await adapter.invoke(
                candidate,
                ModelRequest(
                    route="default_chat",
                    messages=(ModelMessage(role="user", content="hi"),),
                ),
            )
    finally:
        await client.close()

    assert exc_info.value.category is ModelErrorCategory.INVALID_RESPONSE


@pytest.mark.parametrize("provider", ["openai", "dashscope"])
@pytest.mark.asyncio
async def test_provider_sdk_retries_are_disabled(provider: str) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            503,
            json={"error": {"message": "unavailable", "type": "provider_error"}},
        )

    adapter, candidate, client = _adapter(provider, handler)
    try:
        with pytest.raises(ModelGatewayError):
            await adapter.invoke(
                candidate,
                ModelRequest(
                    route="default_chat",
                    messages=(ModelMessage(role="user", content="hi"),),
                ),
            )
    finally:
        await client.close()

    assert attempts == 1


def test_real_adapter_rejects_unsafe_configured_base_url() -> None:
    with pytest.raises(ValueError, match="trusted HTTP"):
        OpenAIProviderAdapter(api_key="test-key", base_url="https://user:secret@example.test/v1")
