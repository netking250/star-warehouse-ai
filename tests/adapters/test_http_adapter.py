"""Contract tests for the production HTTP business adapter."""

import httpx
import pytest

from app.adapters.contracts import AdapterContext, ProductQuery
from app.adapters.errors import AdapterError, AdapterErrorCode
from app.adapters.http import ProductionBusinessHTTPAdapter
from app.adapters.resilience import ResilientExecutor


@pytest.mark.asyncio
async def test_http_adapter_propagates_identity_and_trace_headers() -> None:
    captured: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(
            200,
            json={
                "user_id": 7,
                "username": "customer",
                "email": "customer@example.com",
                "full_name": "Customer",
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = ProductionBusinessHTTPAdapter("https://business.test", token="secret", client=client)
    context = AdapterContext(tenant_id="tenant-a", user_id=7, correlation_id="trace-123")

    account = await adapter.get_account(context)

    assert account is not None
    assert account.user_id == 7
    assert captured is not None
    assert captured.headers["X-Tenant-ID"] == "tenant-a"
    assert captured.headers["X-User-ID"] == "7"
    assert captured.headers["X-Correlation-ID"] == "trace-123"
    assert captured.headers["Authorization"] == "Bearer secret"
    await client.aclose()


@pytest.mark.asyncio
async def test_http_adapter_excludes_private_conversation_history_from_query() -> None:
    captured: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(200, json=[])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = ProductionBusinessHTTPAdapter("https://business.test", client=client)
    query = ProductQuery(
        query="耳机",
        conversation_history=[{"role": "user", "content": "private context"}],
    )

    assert await adapter.search(query, AdapterContext(tenant_id="t", user_id=1)) == []
    assert captured is not None
    assert "conversation_history" not in str(captured.url)
    await client.aclose()


@pytest.mark.asyncio
async def test_http_adapter_retries_server_error_then_opens_circuit() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"detail": "internal details"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    executor = ResilientExecutor(max_retries=1, failure_threshold=1, recovery_seconds=60)
    adapter = ProductionBusinessHTTPAdapter(
        "https://business.test", client=client, executor=executor
    )
    context = AdapterContext(tenant_id="t", user_id=1)

    with pytest.raises(AdapterError) as raised:
        await adapter.get_account(context)
    assert raised.value.code == AdapterErrorCode.UPSTREAM_ERROR
    assert attempts == 2

    with pytest.raises(AdapterError) as raised:
        await adapter.get_account(context)
    assert raised.value.code == AdapterErrorCode.CIRCUIT_OPEN
    assert attempts == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_http_adapter_normalizes_forbidden_response() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(403)))
    adapter = ProductionBusinessHTTPAdapter("https://business.test", client=client)

    with pytest.raises(AdapterError) as raised:
        await adapter.get_account(AdapterContext(tenant_id="t", user_id=1))
    assert raised.value.code == AdapterErrorCode.FORBIDDEN
    assert raised.value.retryable is False
    await client.aclose()
