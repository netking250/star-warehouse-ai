"""Tests for adapter timeout, retry, and circuit-breaker behavior."""

import asyncio

import pytest

from app.adapters.errors import AdapterError, AdapterErrorCode
from app.adapters.resilience import ResilientExecutor


@pytest.mark.asyncio
async def test_executor_retryable_failure_eventually_succeeds() -> None:
    executor = ResilientExecutor(max_retries=2, failure_threshold=3)
    attempts = 0

    async def flaky_call() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise AdapterError(
                AdapterErrorCode.UNAVAILABLE,
                "temporary",
                service="oms",
                retryable=True,
            )
        return "ok"

    assert await executor.run("oms", "get_order", flaky_call) == "ok"
    assert attempts == 3


@pytest.mark.asyncio
async def test_executor_timeout_is_normalized() -> None:
    executor = ResilientExecutor(timeout_seconds=0.001, max_retries=0)

    async def slow_call() -> None:
        await asyncio.sleep(0.05)

    with pytest.raises(AdapterError) as raised:
        await executor.run("erp", "inventory", slow_call)

    assert raised.value.code == AdapterErrorCode.TIMEOUT
    assert raised.value.retryable is True


@pytest.mark.asyncio
async def test_executor_opens_circuit_after_threshold() -> None:
    executor = ResilientExecutor(max_retries=0, failure_threshold=2, recovery_seconds=60)

    async def unavailable() -> None:
        raise AdapterError(
            AdapterErrorCode.UNAVAILABLE,
            "temporary",
            service="payment",
            retryable=True,
        )

    for _ in range(2):
        with pytest.raises(AdapterError) as raised:
            await executor.run("payment", "status", unavailable)
        assert raised.value.code == AdapterErrorCode.UNAVAILABLE

    with pytest.raises(AdapterError) as raised:
        await executor.run("payment", "status", unavailable)
    assert raised.value.code == AdapterErrorCode.CIRCUIT_OPEN


@pytest.mark.asyncio
async def test_executor_does_not_open_circuit_for_validation_failure() -> None:
    executor = ResilientExecutor(max_retries=0, failure_threshold=1)

    async def invalid() -> None:
        raise AdapterError(
            AdapterErrorCode.VALIDATION,
            "invalid input",
            service="cart",
        )

    for _ in range(2):
        with pytest.raises(AdapterError) as raised:
            await executor.run("cart", "add", invalid)
        assert raised.value.code == AdapterErrorCode.VALIDATION
