"""Regression tests for bounded embedding-provider degradation."""

import asyncio

import httpx
import pytest

from app.retrieval.embeddings import QwenEmbeddings


@pytest.mark.asyncio
async def test_embedding_failure_cooldown_avoids_repeated_provider_wait(monkeypatch) -> None:
    calls = 0

    async def failing_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("embedding timeout")

    monkeypatch.setattr(httpx.AsyncClient, "post", failing_post)
    embedder = QwenEmbeddings(
        base_url="https://embedding.invalid",
        api_key="test",
        model="test",
        dimensions=3,
        failure_cooldown_seconds=30.0,
    )

    first = await embedder.aembed_query("first query")
    second = await embedder.aembed_query("second query")

    assert first == [0.0, 0.0, 0.0]
    assert second == [0.0, 0.0, 0.0]
    assert calls == 1


@pytest.mark.asyncio
async def test_concurrent_same_embedding_request_is_coalesced(monkeypatch) -> None:
    calls = 0

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    async def successful_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return Response()

    monkeypatch.setattr(httpx.AsyncClient, "post", successful_post)
    embedder = QwenEmbeddings(
        base_url="https://embedding.invalid",
        api_key="test",
        model="test",
        dimensions=3,
        failure_cooldown_seconds=30.0,
    )

    first, second = await asyncio.gather(
        embedder.aembed_query("same query"), embedder.aembed_query("same query")
    )

    assert first == second == [0.1, 0.2, 0.3]
    assert calls == 1
