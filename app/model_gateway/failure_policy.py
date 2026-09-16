"""Bounded retry, fallback, degradation, and circuit policy for model calls.

The policy in this module is deliberately outside :mod:`app.model_gateway.gateway` and the
provider adapters.  ``ModelGateway`` still invokes exactly one selected candidate and each
adapter still performs exactly one provider attempt.  This module is the only place that may
retry an attempt, advance through an ordered route, or consult a provider circuit.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from math import ceil, isfinite
from secrets import token_hex
from typing import Protocol, cast

import redis.asyncio as aioredis
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from app.core.tenancy import namespaced_system_key
from app.model_gateway.contracts import (
    ModelCandidate,
    ModelCapability,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventType,
)
from app.model_gateway.errors import (
    ModelConfigurationError,
    ModelErrorCategory,
    ModelGatewayError,
)
from app.observability.metrics import (
    normalize_metric_label,
    record_model_attempt,
    record_model_circuit_rejection,
    record_model_circuit_transition,
    record_model_degraded,
    record_model_fallback,
    record_model_logical_request,
    record_model_provider_attempt,
    record_model_retry,
    set_model_circuit_state,
)

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class DegradationMode(StrEnum):
    """Terminal behavior after every eligible model candidate is unavailable."""

    FAIL = "fail"
    SAFE_STATIC_RESPONSE = "safe_static_response"


class CircuitState(StrEnum):
    """Distributed provider circuit states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


_TRANSIENT_CATEGORIES = frozenset(
    {
        ModelErrorCategory.TIMEOUT,
        ModelErrorCategory.CONNECTION,
        ModelErrorCategory.RATE_LIMIT,
        ModelErrorCategory.PROVIDER_UNAVAILABLE,
    }
)


@dataclass(frozen=True, slots=True)
class ModelFailurePolicyConfig:
    """Trusted server-side bounds for model failure handling.

    The values intentionally describe operational policy rather than user request controls.  All
    limits are finite and are validated at construction so a malformed deployment cannot create
    an unbounded retry loop.
    """

    max_attempts_per_candidate: int = 2
    max_total_attempts: int = 4
    total_deadline_seconds: float = 60.0
    retryable_categories: frozenset[ModelErrorCategory] = field(
        default_factory=lambda: _TRANSIENT_CATEGORIES
    )
    fallback_categories: frozenset[ModelErrorCategory] = field(
        default_factory=lambda: _TRANSIENT_CATEGORIES
    )
    circuit_categories: frozenset[ModelErrorCategory] = field(
        default_factory=lambda: _TRANSIENT_CATEGORIES
    )
    base_backoff_seconds: float = 0.25
    max_backoff_seconds: float = 5.0
    jitter_ratio: float = 0.2
    retry_after_max_seconds: float = 5.0
    circuit_failure_threshold: int = 5
    circuit_open_seconds: float = 30.0
    circuit_half_open_probe_seconds: float = 5.0
    degradation_mode: DegradationMode = DegradationMode.FAIL
    safe_static_response: str = "The AI service is temporarily unavailable. Please try again later."

    def __post_init__(self) -> None:
        """Validate finite retry, deadline, and circuit bounds."""
        if self.max_attempts_per_candidate < 1:
            raise ValueError("max_attempts_per_candidate must be at least one")
        if self.max_total_attempts < 1:
            raise ValueError("max_total_attempts must be at least one")
        if not isfinite(self.total_deadline_seconds) or self.total_deadline_seconds <= 0:
            raise ValueError("total_deadline_seconds must be positive")
        if not isfinite(self.base_backoff_seconds) or self.base_backoff_seconds < 0:
            raise ValueError("base_backoff_seconds cannot be negative")
        if (
            not isfinite(self.max_backoff_seconds)
            or self.max_backoff_seconds < self.base_backoff_seconds
        ):
            raise ValueError("max_backoff_seconds must be >= base_backoff_seconds")
        if not isfinite(self.jitter_ratio) or not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between zero and one")
        if not isfinite(self.retry_after_max_seconds) or self.retry_after_max_seconds < 0:
            raise ValueError("retry_after_max_seconds cannot be negative")
        if self.circuit_failure_threshold < 1:
            raise ValueError("circuit_failure_threshold must be at least one")
        if not isfinite(self.circuit_open_seconds) or self.circuit_open_seconds <= 0:
            raise ValueError("circuit_open_seconds must be positive")
        if (
            not isfinite(self.circuit_half_open_probe_seconds)
            or self.circuit_half_open_probe_seconds <= 0
        ):
            raise ValueError("circuit_half_open_probe_seconds must be positive")
        if not self.safe_static_response.strip():
            raise ValueError("safe_static_response cannot be blank")

        object.__setattr__(self, "retryable_categories", frozenset(self.retryable_categories))
        object.__setattr__(self, "fallback_categories", frozenset(self.fallback_categories))
        object.__setattr__(self, "circuit_categories", frozenset(self.circuit_categories))
        object.__setattr__(self, "degradation_mode", DegradationMode(self.degradation_mode))

    @classmethod
    def from_settings(cls, config: object) -> ModelFailurePolicyConfig:
        """Build policy bounds from trusted application settings without importing ``Settings``."""
        retryable = _TRANSIENT_CATEGORIES
        if bool(getattr(config, "MODEL_FAILURE_RETRY_INVALID_RESPONSE", False)):
            retryable = frozenset({*retryable, ModelErrorCategory.INVALID_RESPONSE})
        fallback = retryable
        return cls(
            max_attempts_per_candidate=int(
                getattr(config, "MODEL_FAILURE_MAX_ATTEMPTS_PER_CANDIDATE", 2)
            ),
            max_total_attempts=int(getattr(config, "MODEL_FAILURE_MAX_TOTAL_ATTEMPTS", 4)),
            total_deadline_seconds=float(
                getattr(config, "MODEL_FAILURE_TOTAL_DEADLINE_SECONDS", 60.0)
            ),
            retryable_categories=retryable,
            fallback_categories=fallback,
            circuit_categories=_TRANSIENT_CATEGORIES,
            base_backoff_seconds=float(getattr(config, "MODEL_FAILURE_BASE_BACKOFF_SECONDS", 0.25)),
            max_backoff_seconds=float(getattr(config, "MODEL_FAILURE_MAX_BACKOFF_SECONDS", 5.0)),
            jitter_ratio=float(getattr(config, "MODEL_FAILURE_JITTER_RATIO", 0.2)),
            retry_after_max_seconds=float(
                getattr(config, "MODEL_FAILURE_RETRY_AFTER_MAX_SECONDS", 5.0)
            ),
            circuit_failure_threshold=int(
                getattr(config, "MODEL_FAILURE_CIRCUIT_FAILURE_THRESHOLD", 5)
            ),
            circuit_open_seconds=float(getattr(config, "MODEL_FAILURE_CIRCUIT_OPEN_SECONDS", 30.0)),
            circuit_half_open_probe_seconds=float(
                getattr(config, "MODEL_FAILURE_CIRCUIT_HALF_OPEN_PROBE_SECONDS", 5.0)
            ),
            degradation_mode=DegradationMode(
                getattr(config, "MODEL_FAILURE_DEGRADATION_MODE", DegradationMode.FAIL)
            ),
            safe_static_response=str(
                getattr(
                    config,
                    "MODEL_FAILURE_SAFE_STATIC_RESPONSE",
                    "The AI service is temporarily unavailable. Please try again later.",
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class CircuitPermit:
    """Result of one atomic circuit admission decision."""

    allowed: bool
    state: CircuitState
    generation: int = 0
    probe_token: str | None = None
    transition_from: CircuitState | None = None


class CircuitStore(Protocol):
    """Storage contract for process-shared provider circuit state."""

    async def acquire(self, key: str, *, now: float) -> CircuitPermit:
        """Return whether one attempt may use the candidate."""

        ...

    async def record_success(self, key: str, permit: CircuitPermit, *, now: float) -> CircuitState:
        """Record a successful admitted attempt."""

        ...

    async def record_failure(self, key: str, permit: CircuitPermit, *, now: float) -> CircuitState:
        """Record an operational failure and return the resulting state."""

        ...


@dataclass(slots=True)
class _MemoryCircuitRecord:
    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    open_until: float = 0.0
    generation: int = 0
    probe_in_flight: bool = False


class InMemoryCircuitStore:
    """Deterministic circuit store for tests and single-process development.

    Production factories use :class:`RedisCircuitStore`; this implementation is intentionally
    injectable so policy tests never need a live Redis service.
    """

    def __init__(
        self,
        config: ModelFailurePolicyConfig | None = None,
        *,
        failure_threshold: int | None = None,
        open_seconds: float | None = None,
        half_open_probe_seconds: float | None = None,
    ) -> None:
        selected = config or ModelFailurePolicyConfig()
        self.failure_threshold = (
            failure_threshold
            if failure_threshold is not None
            else selected.circuit_failure_threshold
        )
        self.open_seconds = (
            open_seconds if open_seconds is not None else selected.circuit_open_seconds
        )
        self.half_open_probe_seconds = (
            half_open_probe_seconds
            if half_open_probe_seconds is not None
            else selected.circuit_half_open_probe_seconds
        )
        self._records: dict[str, _MemoryCircuitRecord] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str, *, now: float) -> CircuitPermit:
        """Admit at most one half-open probe while sharing state in this process."""
        async with self._lock:
            record = self._records.setdefault(key, _MemoryCircuitRecord())
            if record.state is CircuitState.OPEN:
                if now < record.open_until:
                    return CircuitPermit(False, CircuitState.OPEN, record.generation)
                previous = record.state
                record.state = CircuitState.HALF_OPEN
                record.generation += 1
                record.probe_in_flight = False
                transition_from = previous
            else:
                transition_from = None

            if record.state is CircuitState.HALF_OPEN:
                if record.probe_in_flight:
                    return CircuitPermit(
                        False,
                        CircuitState.HALF_OPEN,
                        record.generation,
                    )
                record.probe_in_flight = True
                return CircuitPermit(
                    True,
                    CircuitState.HALF_OPEN,
                    record.generation,
                    probe_token=f"memory-{record.generation}",
                    transition_from=transition_from,
                )
            return CircuitPermit(True, CircuitState.CLOSED, record.generation)

    async def record_success(self, key: str, permit: CircuitPermit, *, now: float) -> CircuitState:
        """Close a matching probe or reset consecutive failures after a normal success."""
        del now
        async with self._lock:
            record = self._records.setdefault(key, _MemoryCircuitRecord())
            if permit.generation != record.generation:
                return record.state
            if permit.state is CircuitState.HALF_OPEN:
                if not record.probe_in_flight:
                    return record.state
                record.state = CircuitState.CLOSED
                record.failures = 0
                record.open_until = 0.0
                record.probe_in_flight = False
                return record.state
            if record.state is CircuitState.CLOSED:
                record.failures = 0
            return record.state

    async def record_failure(self, key: str, permit: CircuitPermit, *, now: float) -> CircuitState:
        """Open after consecutive operational failures and reopen failed probes."""
        async with self._lock:
            record = self._records.setdefault(key, _MemoryCircuitRecord())
            if permit.generation != record.generation:
                return record.state
            if permit.state is CircuitState.HALF_OPEN:
                if record.probe_in_flight:
                    record.state = CircuitState.OPEN
                    record.failures = self.failure_threshold
                    record.open_until = now + self.open_seconds
                    record.probe_in_flight = False
                return record.state
            if record.state is not CircuitState.CLOSED:
                return record.state
            record.failures += 1
            if record.failures >= self.failure_threshold:
                record.state = CircuitState.OPEN
                record.open_until = now + self.open_seconds
            return record.state

    async def get_state(self, key: str, *, now: float | None = None) -> CircuitState:
        """Inspect state in tests without changing admission state."""
        async with self._lock:
            record = self._records.get(key)
            if record is None:
                return CircuitState.CLOSED
            if record.state is CircuitState.OPEN and now is not None and now >= record.open_until:
                return CircuitState.HALF_OPEN
            return record.state

    async def reset(self, key: str) -> None:
        """Remove one test circuit record."""
        async with self._lock:
            self._records.pop(key, None)


class _AsyncRedisClient(Protocol):
    """Small async Redis surface; redis-py's broad overloads are not awaitable to ty."""

    async def hgetall(self, name: str) -> Mapping[object, object]:
        """Read a hash."""

        ...

    async def set(
        self,
        name: str,
        value: str,
        *,
        nx: bool = False,
        ex: int | None = None,
    ) -> bool | None:
        """Set a value with optional NX/expiry semantics."""

        ...

    async def hset(self, name: str, *, mapping: Mapping[str, str]) -> int:
        """Write hash fields."""

        ...

    async def expire(self, name: str, time: int) -> bool:
        """Set key expiry."""

        ...

    async def get(self, name: str) -> object:
        """Read one value."""

        ...

    async def hincrby(self, name: str, key: str, amount: int = 1) -> int:
        """Atomically increment one hash field."""

        ...

    async def delete(self, *names: str) -> int:
        """Delete keys."""

        ...


class RedisCircuitStore:
    """Redis-backed circuit state with atomic half-open probe admission.

    State is stored in the system namespace and keyed only by a provider/model digest.  The probe
    ``SET NX`` is the cross-instance coordination primitive; no API key or tenant identifier is
    ever included in a circuit key.
    """

    _KEY_PREFIX = "model-failure:circuit"

    def __init__(
        self,
        redis: aioredis.Redis,
        config: ModelFailurePolicyConfig | None = None,
        *,
        failure_threshold: int | None = None,
        open_seconds: float | None = None,
        half_open_probe_seconds: float | None = None,
    ) -> None:
        selected = config or ModelFailurePolicyConfig()
        self.redis = cast(_AsyncRedisClient, redis)
        self.failure_threshold = (
            failure_threshold
            if failure_threshold is not None
            else selected.circuit_failure_threshold
        )
        self.open_seconds = (
            open_seconds if open_seconds is not None else selected.circuit_open_seconds
        )
        self.half_open_probe_seconds = (
            half_open_probe_seconds
            if half_open_probe_seconds is not None
            else selected.circuit_half_open_probe_seconds
        )

    def _state_key(self, key: str) -> str:
        return namespaced_system_key(f"{self._KEY_PREFIX}:{key}")

    def _probe_key(self, key: str) -> str:
        return f"{self._state_key(key)}:probe"

    @staticmethod
    def _text(value: object) -> str:
        return value.decode() if isinstance(value, bytes) else str(value)

    async def _read(self, key: str) -> dict[str, str]:
        raw = await self.redis.hgetall(self._state_key(key))
        return {self._text(name): self._text(value) for name, value in raw.items()}

    async def acquire(self, key: str, *, now: float) -> CircuitPermit:
        """Read state and use Redis ``SET NX`` to coordinate one half-open probe."""
        values = await self._read(key)
        state_text = values.get("state", CircuitState.CLOSED.value)
        try:
            state = CircuitState(state_text)
        except ValueError:
            state = CircuitState.CLOSED
        generation = int(values.get("generation", "0"))
        if state is CircuitState.OPEN:
            open_until = float(values.get("open_until", "0"))
            if now < open_until:
                return CircuitPermit(False, CircuitState.OPEN, generation)
            previous = state
            state = CircuitState.HALF_OPEN
            generation += 1
            transition_from = previous
        else:
            transition_from = None

        if state is CircuitState.HALF_OPEN:
            token = token_hex(16)
            acquired = await self.redis.set(
                self._probe_key(key),
                token,
                nx=True,
                ex=max(1, ceil(self.half_open_probe_seconds)),
            )
            if not acquired:
                return CircuitPermit(False, CircuitState.HALF_OPEN, generation)
            await self.redis.hset(
                self._state_key(key),
                mapping={"state": state.value, "generation": str(generation)},
            )
            await self.redis.expire(self._state_key(key), self._state_expiry_seconds())
            return CircuitPermit(
                True,
                CircuitState.HALF_OPEN,
                generation,
                probe_token=token,
                transition_from=transition_from,
            )
        return CircuitPermit(True, CircuitState.CLOSED, generation)

    async def record_success(self, key: str, permit: CircuitPermit, *, now: float) -> CircuitState:
        """Reset only a matching generation, leaving newer circuit decisions untouched."""
        del now
        state_key = self._state_key(key)
        values = await self._read(key)
        if int(values.get("generation", "0")) != permit.generation:
            return _parse_state(values.get("state"))
        state = _parse_state(values.get("state"))
        if permit.state is CircuitState.HALF_OPEN:
            if not await self._probe_matches(key, permit.probe_token):
                return state
        elif state is not CircuitState.CLOSED:
            return state
        await self.redis.delete(state_key, self._probe_key(key))
        return CircuitState.CLOSED

    async def record_failure(self, key: str, permit: CircuitPermit, *, now: float) -> CircuitState:
        """Increment failures atomically and open the circuit at the configured threshold."""
        state_key = self._state_key(key)
        values = await self._read(key)
        state = _parse_state(values.get("state"))
        generation = int(values.get("generation", "0"))
        if generation != permit.generation:
            return state
        if permit.state is CircuitState.HALF_OPEN:
            if not await self._probe_matches(key, permit.probe_token):
                return state
            await self.redis.hset(
                state_key,
                mapping={
                    "state": CircuitState.OPEN.value,
                    "failures": str(self.failure_threshold),
                    "open_until": str(now + self.open_seconds),
                    "generation": str(generation),
                },
            )
            await self.redis.expire(state_key, self._state_expiry_seconds())
            await self.redis.delete(self._probe_key(key))
            return CircuitState.OPEN
        if state is not CircuitState.CLOSED:
            return state
        if not values:
            await self.redis.hset(
                state_key,
                mapping={"state": CircuitState.CLOSED.value, "generation": str(generation)},
            )
        failures = int(await self.redis.hincrby(state_key, "failures", 1))
        if failures >= self.failure_threshold:
            await self.redis.hset(
                state_key,
                mapping={
                    "state": CircuitState.OPEN.value,
                    "failures": str(failures),
                    "open_until": str(now + self.open_seconds),
                    "generation": str(generation),
                },
            )
            await self.redis.expire(state_key, self._state_expiry_seconds())
            return CircuitState.OPEN
        await self.redis.expire(
            state_key,
            self._state_expiry_seconds(),
        )
        return CircuitState.CLOSED

    def _state_expiry_seconds(self) -> int:
        """Keep an OPEN record through its eligibility window for half-open admission."""
        return max(1, ceil(self.open_seconds + self.half_open_probe_seconds))

    async def _probe_matches(self, key: str, token: str | None) -> bool:
        if token is None:
            return False
        value = await self.redis.get(self._probe_key(key))
        return value is None or self._text(value) == token

    async def get_state(self, key: str, *, now: float | None = None) -> CircuitState:
        """Inspect one stored state for diagnostics and tests."""
        values = await self._read(key)
        state = _parse_state(values.get("state"))
        if (
            state is CircuitState.OPEN
            and now is not None
            and now >= float(values.get("open_until", "0"))
        ):
            return CircuitState.HALF_OPEN
        return state

    async def reset(self, key: str) -> None:
        """Remove one circuit and its probe key, primarily for isolated tests."""
        await self.redis.delete(self._state_key(key), self._probe_key(key))


def _parse_state(value: str | None) -> CircuitState:
    try:
        return CircuitState(value or CircuitState.CLOSED.value)
    except ValueError:
        return CircuitState.CLOSED


def candidate_circuit_key(candidate: ModelCandidate) -> str:
    """Return a non-secret circuit key for one configured provider/model identity."""
    identity = f"{candidate.provider}\x1f{candidate.model}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]


Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]
RandomSource = Callable[[], float]


class ModelFailurePolicy:
    """Execute bounded model retries and ordered fallback outside the T13 gateway."""

    def __init__(
        self,
        config: ModelFailurePolicyConfig | None = None,
        *,
        circuit_store: CircuitStore | None = None,
        clock: Clock = time.monotonic,
        sleep: Sleep = asyncio.sleep,
        random_source: RandomSource = random.random,
    ) -> None:
        self.config = config if config is not None else ModelFailurePolicyConfig()
        self.circuit_store = (
            circuit_store if circuit_store is not None else InMemoryCircuitStore(self.config)
        )
        self.clock = clock
        self.sleep = sleep
        self.random_source = random_source

    async def invoke(
        self,
        gateway: ModelGatewayLike,
        request: ModelRequest,
        *,
        candidates: Sequence[ModelCandidate] | None = None,
    ) -> ModelResponse:
        """Invoke one logical request and record its terminal policy outcome once."""
        started = time.perf_counter()
        outcome = "failure"
        category = "unknown"
        with tracer.start_as_current_span(
            "model.invoke",
            attributes={"model.route": normalize_metric_label(request.route)},
        ) as span:
            try:
                response = await self._invoke_with_policy(gateway, request, candidates=candidates)
                outcome = "degraded" if response.degraded else "success"
                category = "none"
                return response
            except asyncio.CancelledError:
                outcome = "cancelled"
                category = "none"
                span.set_status(Status(StatusCode.ERROR, "model request cancelled"))
                raise
            except ModelGatewayError as error:
                category = error.category.value
                span.set_attribute("error.type", type(error).__name__)
                span.set_attribute("model.error_category", category)
                span.set_status(Status(StatusCode.ERROR, "model request failed"))
                raise
            finally:
                try:
                    record_model_logical_request(
                        route=request.route,
                        outcome=outcome,
                        category=category,
                        duration_seconds=time.perf_counter() - started,
                    )
                except Exception as telemetry_error:
                    logger.debug(
                        "Model logical-request metric unavailable after %.3fs: %s",
                        time.perf_counter() - started,
                        type(telemetry_error).__name__,
                    )

    async def _invoke_with_policy(
        self,
        gateway: ModelGatewayLike,
        request: ModelRequest,
        *,
        candidates: Sequence[ModelCandidate] | None = None,
    ) -> ModelResponse:
        """Invoke candidates with bounded retries and return exactly one response."""
        resolved = self._resolve_candidates(gateway, request, candidates)
        deadline = self.clock() + self.config.total_deadline_seconds
        total_attempts = 0
        last_error: ModelGatewayError | None = None

        for candidate in resolved:
            if total_attempts >= self.config.max_total_attempts:
                break
            permit = await self._acquire(candidate)
            if not permit.allowed:
                record_model_fallback(provider=candidate.provider, outcome="circuit_unavailable")
                continue
            candidate_error: ModelGatewayError | None = None
            for attempt in range(1, self.config.max_attempts_per_candidate + 1):
                if total_attempts >= self.config.max_total_attempts:
                    break
                remaining = deadline - self.clock()
                if remaining <= 0:
                    candidate_error = self._deadline_error(candidate)
                    last_error = candidate_error
                    break
                total_attempts += 1
                attempt_started = time.perf_counter()
                record_model_attempt(provider=candidate.provider, outcome="started")
                try:
                    response = await self._invoke_once(gateway, candidate, request, remaining)
                except asyncio.CancelledError:
                    self._record_provider_attempt(
                        provider=candidate.provider,
                        route=request.route,
                        outcome="cancelled",
                        duration_seconds=time.perf_counter() - attempt_started,
                    )
                    raise
                except ModelConfigurationError:
                    # Invalid trusted route/provider configuration is not a provider failure and
                    # must remain visible to the caller instead of being normalized/retried.
                    raise
                except Exception as raw_error:
                    error = self._normalize_error(raw_error, candidate)
                    candidate_error = error
                    last_error = error
                    state = await self._record_failure(candidate, permit, error)
                    record_model_attempt(provider=candidate.provider, outcome="failed")
                    self._record_provider_attempt(
                        provider=candidate.provider,
                        route=request.route,
                        outcome="failure",
                        category=error.category.value,
                        duration_seconds=time.perf_counter() - attempt_started,
                    )
                    if not self._retry_allowed(error) or state is CircuitState.OPEN:
                        break
                    if attempt >= self.config.max_attempts_per_candidate:
                        break
                    if total_attempts >= self.config.max_total_attempts:
                        break
                    record_model_retry(provider=candidate.provider, category=error.category.value)
                    await self._backoff(error, attempt, deadline)
                else:
                    await self._record_success(candidate, permit)
                    record_model_attempt(provider=candidate.provider, outcome="succeeded")
                    self._record_provider_attempt(
                        provider=candidate.provider,
                        route=request.route,
                        outcome="success",
                        duration_seconds=time.perf_counter() - attempt_started,
                    )
                    return response

            if candidate_error is None:
                continue
            if candidate_error.category not in self.config.fallback_categories:
                raise candidate_error
            if total_attempts >= self.config.max_total_attempts or deadline <= self.clock():
                break
            record_model_fallback(provider=candidate.provider, outcome="candidate_exhausted")

        degraded = self._degraded_response(request)
        if degraded is not None:
            record_model_degraded(route=request.route)
            return degraded
        raise last_error or ModelGatewayError(
            ModelErrorCategory.PROVIDER_UNAVAILABLE,
            "No configured model candidate was available",
        )

    async def stream(
        self,
        gateway: ModelGatewayLike,
        request: ModelRequest,
        *,
        candidates: Sequence[ModelCandidate] | None = None,
    ) -> AsyncIterator[ModelStreamEvent]:
        """Stream one logical request and record its terminal policy outcome once."""
        started = time.perf_counter()
        outcome = "failure"
        category = "unknown"
        with tracer.start_as_current_span(
            "model.stream",
            attributes={"model.route": normalize_metric_label(request.route)},
        ) as span:
            try:
                async for event in self._stream_with_policy(
                    gateway, request, candidates=candidates
                ):
                    if event.degraded:
                        outcome = "degraded"
                    yield event
                if outcome != "degraded":
                    outcome = "success"
                category = "none"
            except asyncio.CancelledError:
                outcome = "cancelled"
                category = "none"
                span.set_status(Status(StatusCode.ERROR, "model stream cancelled"))
                raise
            except GeneratorExit:
                outcome = "cancelled"
                category = "none"
                span.set_status(Status(StatusCode.ERROR, "model stream closed"))
                raise
            except ModelGatewayError as error:
                category = error.category.value
                span.set_attribute("error.type", type(error).__name__)
                span.set_attribute("model.error_category", category)
                span.set_status(Status(StatusCode.ERROR, "model stream failed"))
                raise
            finally:
                try:
                    record_model_logical_request(
                        route=request.route,
                        outcome=outcome,
                        category=category,
                        duration_seconds=time.perf_counter() - started,
                    )
                except Exception as telemetry_error:
                    logger.debug(
                        "Model logical-request metric unavailable: %s",
                        type(telemetry_error).__name__,
                    )

    async def _stream_with_policy(
        self,
        gateway: ModelGatewayLike,
        request: ModelRequest,
        *,
        candidates: Sequence[ModelCandidate] | None = None,
    ) -> AsyncIterator[ModelStreamEvent]:
        """Stream one candidate, retrying/falling back only before visible output begins."""
        resolved = self._resolve_candidates(gateway, request, candidates)
        deadline = self.clock() + self.config.total_deadline_seconds
        total_attempts = 0
        last_error: ModelGatewayError | None = None

        for candidate in resolved:
            if total_attempts >= self.config.max_total_attempts:
                break
            permit = await self._acquire(candidate)
            if not permit.allowed:
                record_model_fallback(provider=candidate.provider, outcome="circuit_unavailable")
                continue
            candidate_error: ModelGatewayError | None = None
            for attempt in range(1, self.config.max_attempts_per_candidate + 1):
                if total_attempts >= self.config.max_total_attempts:
                    break
                remaining = deadline - self.clock()
                if remaining <= 0:
                    candidate_error = self._deadline_error(candidate)
                    last_error = candidate_error
                    break
                total_attempts += 1
                visible = False
                completed = False
                attempt_started = time.perf_counter()
                record_model_attempt(provider=candidate.provider, outcome="started")
                try:
                    async with asyncio.timeout(remaining):
                        async for event in gateway.stream(candidate, request):
                            if self._visible_event(event):
                                visible = True
                            if event.event_type is ModelStreamEventType.COMPLETED:
                                completed = True
                            yield event
                    if not completed:
                        raise ModelGatewayError(
                            ModelErrorCategory.INVALID_RESPONSE,
                            "Provider stream ended without a completion event",
                            provider=candidate.provider,
                            model=candidate.model,
                        )
                except asyncio.CancelledError:
                    self._record_provider_attempt(
                        provider=candidate.provider,
                        route=request.route,
                        outcome="cancelled",
                        duration_seconds=time.perf_counter() - attempt_started,
                    )
                    raise
                except ModelConfigurationError:
                    raise
                except Exception as raw_error:
                    error = self._normalize_error(raw_error, candidate)
                    candidate_error = error
                    last_error = error
                    state = await self._record_failure(candidate, permit, error)
                    record_model_attempt(provider=candidate.provider, outcome="failed")
                    self._record_provider_attempt(
                        provider=candidate.provider,
                        route=request.route,
                        outcome="failure",
                        category=error.category.value,
                        duration_seconds=time.perf_counter() - attempt_started,
                    )
                    if visible:
                        # Once any text or tool delta has escaped, switching providers would
                        # duplicate or splice two answers into one client-visible response.
                        raise error from None
                    if not self._retry_allowed(error) or state is CircuitState.OPEN:
                        break
                    if attempt >= self.config.max_attempts_per_candidate:
                        break
                    if total_attempts >= self.config.max_total_attempts:
                        break
                    record_model_retry(provider=candidate.provider, category=error.category.value)
                    await self._backoff(error, attempt, deadline)
                else:
                    await self._record_success(candidate, permit)
                    record_model_attempt(provider=candidate.provider, outcome="succeeded")
                    self._record_provider_attempt(
                        provider=candidate.provider,
                        route=request.route,
                        outcome="success",
                        duration_seconds=time.perf_counter() - attempt_started,
                    )
                    return

            if candidate_error is None:
                continue
            if candidate_error.category not in self.config.fallback_categories:
                raise candidate_error
            if total_attempts >= self.config.max_total_attempts or deadline <= self.clock():
                break
            record_model_fallback(provider=candidate.provider, outcome="stream_candidate_exhausted")

        degraded_event = self._degraded_stream_event(request)
        if degraded_event is not None:
            record_model_degraded(route=request.route)
            yield degraded_event
            yield ModelStreamEvent(
                event_type=ModelStreamEventType.COMPLETED,
                provider="degraded",
                model="static",
                finish_reason="degraded",
                degraded=True,
            )
            return
        raise last_error or ModelGatewayError(
            ModelErrorCategory.PROVIDER_UNAVAILABLE,
            "No configured model candidate was available",
        )

    @staticmethod
    def _record_provider_attempt(
        *,
        provider: str,
        route: str,
        outcome: str,
        category: str = "none",
        duration_seconds: float,
    ) -> None:
        """Record provider-attempt telemetry without changing policy behavior."""
        try:
            record_model_provider_attempt(
                provider=provider,
                route=route,
                outcome=outcome,
                category=category,
                duration_seconds=duration_seconds,
            )
        except Exception as telemetry_error:
            logger.debug(
                "Model provider-attempt metric unavailable: %s",
                type(telemetry_error).__name__,
            )

    @staticmethod
    def _resolve_candidates(
        gateway: ModelGatewayLike,
        request: ModelRequest,
        candidates: Sequence[ModelCandidate] | None,
    ) -> tuple[ModelCandidate, ...]:
        if candidates is not None:
            if not candidates:
                raise ModelConfigurationError("At least one model candidate is required")
            resolved = tuple(
                candidate
                for candidate in candidates
                if request.required_capabilities <= candidate.capabilities
            )
            if not resolved:
                required = ", ".join(sorted(request.required_capabilities))
                raise ModelGatewayError(
                    ModelErrorCategory.UNSUPPORTED_CAPABILITY,
                    f"No supplied model candidate supports: {required}",
                )
            return resolved
        return tuple(gateway.resolve(request.route, request.required_capabilities))

    async def _invoke_once(
        self,
        gateway: ModelGatewayLike,
        candidate: ModelCandidate,
        request: ModelRequest,
        remaining: float,
    ) -> ModelResponse:
        """Apply the total deadline around exactly one T13 gateway invocation."""
        try:
            async with asyncio.timeout(remaining):
                return await gateway.invoke(candidate, request)
        except asyncio.CancelledError:
            raise
        except TimeoutError as exc:
            raise self._deadline_error(candidate) from exc

    async def _backoff(
        self,
        error: ModelGatewayError,
        failed_attempt: int,
        deadline: float,
    ) -> None:
        """Sleep a bounded jittered delay while preserving cancellation."""
        delay = self._backoff_delay(error, failed_attempt)
        remaining = deadline - self.clock()
        if delay <= 0 or remaining <= 0:
            return
        await self.sleep(min(delay, remaining))

    def _backoff_delay(self, error: ModelGatewayError, failed_attempt: int) -> float:
        """Return bounded exponential jitter, respecting a clamped Retry-After hint."""
        exponential = min(
            self.config.max_backoff_seconds,
            self.config.base_backoff_seconds * (2 ** max(failed_attempt - 1, 0)),
        )
        sample = min(1.0, max(0.0, self.random_source()))
        jittered = exponential * (1 + ((sample * 2) - 1) * self.config.jitter_ratio)
        retry_after = getattr(error, "retry_after_seconds", None) or 0.0
        return min(
            self.config.max_backoff_seconds,
            max(0.0, jittered, min(float(retry_after), self.config.retry_after_max_seconds)),
        )

    def _retry_allowed(self, error: ModelGatewayError) -> bool:
        """Return whether this normalized category can consume another attempt."""
        return error.category in self.config.retryable_categories

    async def _acquire(self, candidate: ModelCandidate) -> CircuitPermit:
        key = candidate_circuit_key(candidate)
        try:
            permit = await self.circuit_store.acquire(key, now=self.clock())
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # A breaker outage must not deadlock or silently create unbounded retries.  Local
            # attempt/deadline limits remain active while this one decision fails open.
            logger.warning(
                "Model circuit storage unavailable; allowing bounded attempt",
                extra={
                    "event": "model_circuit_storage_unavailable",
                    "provider": candidate.provider,
                    "error_type": type(error).__name__,
                },
            )
            self._set_circuit_state(candidate.provider, CircuitState.CLOSED.value)
            return CircuitPermit(True, CircuitState.CLOSED)
        self._set_circuit_state(candidate.provider, permit.state.value)
        if not permit.allowed:
            self._record_circuit_rejection(candidate.provider)
        if permit.transition_from is not None:
            self._record_circuit_transition(
                provider=candidate.provider,
                from_state=permit.transition_from.value,
                to_state=permit.state.value,
            )
        return permit

    async def _record_success(self, candidate: ModelCandidate, permit: CircuitPermit) -> None:
        try:
            state = await self.circuit_store.record_success(
                candidate_circuit_key(candidate), permit, now=self.clock()
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning(
                "Model circuit success update unavailable",
                extra={
                    "event": "model_circuit_success_update_unavailable",
                    "provider": candidate.provider,
                    "error_type": type(error).__name__,
                },
            )
            self._set_circuit_state(candidate.provider, permit.state.value)
            return
        self._set_circuit_state(candidate.provider, state.value)
        if permit.state is not state:
            self._record_circuit_transition(
                provider=candidate.provider,
                from_state=permit.state.value,
                to_state=state.value,
            )

    async def _record_failure(
        self,
        candidate: ModelCandidate,
        permit: CircuitPermit,
        error: ModelGatewayError,
    ) -> CircuitState:
        if error.category not in self.config.circuit_categories:
            if permit.state is CircuitState.HALF_OPEN:
                # A validation/security/application error must not trip the breaker, but it must
                # release the single half-open probe so the circuit cannot remain stuck.
                await self._record_success(candidate, permit)
                return CircuitState.CLOSED
            return permit.state
        try:
            state = await self.circuit_store.record_failure(
                candidate_circuit_key(candidate), permit, now=self.clock()
            )
        except asyncio.CancelledError:
            raise
        except Exception as storage_error:
            logger.warning(
                "Model circuit failure update unavailable",
                extra={
                    "event": "model_circuit_failure_update_unavailable",
                    "provider": candidate.provider,
                    "error_type": type(storage_error).__name__,
                },
            )
            self._set_circuit_state(candidate.provider, permit.state.value)
            return permit.state
        self._set_circuit_state(candidate.provider, state.value)
        if permit.state is not state:
            self._record_circuit_transition(
                provider=candidate.provider,
                from_state=permit.state.value,
                to_state=state.value,
            )
        return state

    @staticmethod
    def _record_circuit_rejection(provider: str) -> None:
        """Record a breaker rejection without affecting the policy decision."""
        try:
            record_model_circuit_rejection(provider=provider)
        except Exception as telemetry_error:
            logger.debug(
                "Model circuit rejection metric unavailable: %s", type(telemetry_error).__name__
            )

    @staticmethod
    def _record_circuit_transition(*, provider: str, from_state: str, to_state: str) -> None:
        """Record a breaker transition without affecting the policy decision."""
        try:
            record_model_circuit_transition(
                provider=provider,
                from_state=from_state,
                to_state=to_state,
            )
        except Exception as telemetry_error:
            logger.debug(
                "Model circuit transition metric unavailable: %s",
                type(telemetry_error).__name__,
            )

    @staticmethod
    def _set_circuit_state(provider: str, state: str) -> None:
        """Publish breaker state defensively so telemetry cannot affect model policy."""
        try:
            set_model_circuit_state(provider=provider, state=state)
        except Exception as telemetry_error:
            logger.debug(
                "Model circuit state metric unavailable: %s", type(telemetry_error).__name__
            )

    @staticmethod
    def _visible_event(event: ModelStreamEvent) -> bool:
        """Return whether a stream event exposes output that cannot be transparently replayed."""
        if event.event_type is ModelStreamEventType.TEXT_DELTA:
            return bool(event.text_delta)
        if event.event_type is ModelStreamEventType.TOOL_CALL_DELTA:
            delta = event.tool_call_delta
            return delta is not None and bool(delta.name or delta.id or delta.arguments_delta)
        return False

    def _degraded_response(self, request: ModelRequest) -> ModelResponse | None:
        if self.config.degradation_mode is not DegradationMode.SAFE_STATIC_RESPONSE:
            return None
        if request.tools or request.structured_output is not None:
            # A static sentence cannot satisfy a tool or schema contract.
            return None
        return ModelResponse(
            content=self.config.safe_static_response,
            finish_reason="degraded",
            provider="degraded",
            model="static",
            degraded=True,
        )

    def _degraded_stream_event(self, request: ModelRequest) -> ModelStreamEvent | None:
        if self.config.degradation_mode is not DegradationMode.SAFE_STATIC_RESPONSE:
            return None
        if request.tools or request.structured_output is not None:
            return None
        return ModelStreamEvent(
            event_type=ModelStreamEventType.TEXT_DELTA,
            provider="degraded",
            model="static",
            text_delta=self.config.safe_static_response,
            degraded=True,
        )

    @staticmethod
    def _deadline_error(candidate: ModelCandidate) -> ModelGatewayError:
        return ModelGatewayError(
            ModelErrorCategory.TIMEOUT,
            "Model execution deadline exhausted",
            provider=candidate.provider,
            model=candidate.model,
        )

    @staticmethod
    def _normalize_error(raw_error: Exception, candidate: ModelCandidate) -> ModelGatewayError:
        if isinstance(raw_error, ModelGatewayError):
            if raw_error.provider is not None and raw_error.model is not None:
                return raw_error
            return ModelGatewayError(
                raw_error.category,
                str(raw_error),
                provider=raw_error.provider or candidate.provider,
                model=raw_error.model or candidate.model,
                provider_request_id=raw_error.provider_request_id,
                retry_after_seconds=raw_error.retry_after_seconds,
            )
        if isinstance(raw_error, TimeoutError):
            category = ModelErrorCategory.TIMEOUT
        elif isinstance(raw_error, ConnectionError):
            category = ModelErrorCategory.CONNECTION
        else:
            category = ModelErrorCategory.UNKNOWN
        return ModelGatewayError(
            category,
            "Model provider attempt failed",
            provider=candidate.provider,
            model=candidate.model,
        )


class ModelGatewayLike(Protocol):
    """Minimal gateway surface consumed by the policy, kept provider-neutral."""

    def resolve(
        self,
        route: str,
        required_capabilities: frozenset[ModelCapability],
    ) -> tuple[ModelCandidate, ...]:
        """Resolve ordered capable candidates."""

        ...

    async def invoke(self, candidate: ModelCandidate, request: ModelRequest) -> ModelResponse:
        """Invoke one candidate."""

        ...

    def stream(
        self, candidate: ModelCandidate, request: ModelRequest
    ) -> AsyncIterator[ModelStreamEvent]:
        """Stream one candidate."""

        ...


# Explicit aliases make the ownership seam discoverable to callers that use the architectural
# name from the T14 plan while retaining one implementation and one policy state machine.
ResilientModelExecutor = ModelFailurePolicy
CircuitBreakerStore = CircuitStore
RedisCircuitBreakerStore = RedisCircuitStore
InMemoryCircuitBreakerStore = InMemoryCircuitStore
