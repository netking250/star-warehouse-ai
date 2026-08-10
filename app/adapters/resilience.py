"""Timeout, retry, circuit-breaker, and audit wrapper for adapters."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from app.adapters.errors import AdapterError, AdapterErrorCode

logger = logging.getLogger(__name__)
T = TypeVar("T")


@dataclass(slots=True)
class CircuitState:
    failures: int = 0
    opened_at: float | None = None


class ResilientExecutor:
    """Execute adapter calls with deterministic resilience policies."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        max_retries: int = 2,
        failure_threshold: int = 5,
        recovery_seconds: float = 30.0,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._states: dict[str, CircuitState] = {}

    async def run(self, service: str, operation: str, call: Callable[[], Awaitable[T]]) -> T:
        """Run one adapter operation and emit a safe audit log."""
        state = self._states.setdefault(service, CircuitState())
        now = time.monotonic()
        if state.opened_at is not None and now - state.opened_at < self.recovery_seconds:
            logger.warning(
                "adapter_call service=%s operation=%s outcome=circuit_open",
                service,
                operation,
            )
            raise AdapterError(
                AdapterErrorCode.CIRCUIT_OPEN,
                "Upstream circuit is open",
                service=service,
                retryable=True,
            )
        if state.opened_at is not None:
            state.opened_at = None
            state.failures = 0

        started = time.perf_counter()
        for attempt in range(self.max_retries + 1):
            try:
                result = await asyncio.wait_for(call(), timeout=self.timeout_seconds)
                state.failures = 0
                logger.info(
                    "adapter_call service=%s operation=%s outcome=success latency_ms=%.2f",
                    service,
                    operation,
                    (time.perf_counter() - started) * 1000,
                )
                return result
            except TimeoutError as error:
                failure = AdapterError(
                    AdapterErrorCode.TIMEOUT,
                    "Upstream request timed out",
                    service=service,
                    retryable=True,
                )
                if attempt == self.max_retries:
                    self._record_failure(state)
                    raise failure from error
            except AdapterError as error:
                if not error.retryable:
                    logger.warning(
                        "adapter_call service=%s operation=%s outcome=failure code=%s",
                        service,
                        operation,
                        error.code,
                    )
                    raise
                if attempt == self.max_retries:
                    self._record_failure(state)
                    logger.warning(
                        "adapter_call service=%s operation=%s outcome=failure code=%s attempts=%s",
                        service,
                        operation,
                        error.code,
                        attempt + 1,
                    )
                    raise
            if attempt < self.max_retries:
                await asyncio.sleep(0.05 * (2**attempt))
        raise AssertionError("unreachable")

    def _record_failure(self, state: CircuitState) -> None:
        state.failures += 1
        if state.failures >= self.failure_threshold:
            state.opened_at = time.monotonic()
