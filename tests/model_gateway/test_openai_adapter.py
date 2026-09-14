"""Offline contract tests for the OpenAI provider adapter."""

import json

import httpx
import pytest
from openai import AsyncOpenAI

from app.model_gateway.contracts import (
    ModelCandidate,
    ModelMessage,
    ModelRequest,
)
from app.model_gateway.providers.openai import OpenAIProviderAdapter


@pytest.mark.asyncio
async def test_openai_normalized_request_and_response() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-safe-id",
                "object": "chat.completion",
                "created": 1,
                "model": "gpt-test-resolved",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "hello"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncOpenAI(
        api_key="sk-test",
        base_url="https://configured.example/v1",
        max_retries=0,
        http_client=http_client,
    )
    adapter = OpenAIProviderAdapter(client=client)
    candidate = ModelCandidate(
        provider="openai",
        model="gpt-test",
        capabilities=adapter.capabilities,
        timeout_seconds=2.0,
    )
    request = ModelRequest(
        route="default_chat",
        messages=(ModelMessage(role="user", content="hi"),),
        temperature=0.2,
        max_output_tokens=17,
    )

    try:
        response = await adapter.invoke(candidate, request)
    finally:
        await client.close()

    assert captured == {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "gpt-test",
        "max_tokens": 17,
        "temperature": 0.2,
    }
    assert response.content == "hello"
    assert response.provider == "openai"
    assert response.model == "gpt-test-resolved"
    assert response.provider_request_id == "chatcmpl-safe-id"
    assert response.usage is not None
    assert response.usage.total_tokens == 5
