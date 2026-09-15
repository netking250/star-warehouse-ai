"""Focused tests for the T14 model failure policy seam."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import cast

import pytest
import redis.asyncio as aioredis
from langchain_core.messages import HumanMessage

from app.model_gateway.contracts import (
    ModelCandidate,
    ModelCapability,
    ModelRequest,
    ModelResponse,
    ModelRoute,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelTool,
)
from app.model_gateway.errors import ModelConfigurationError, ModelErrorCategory, ModelGatewayError
from app.model_gateway.failure_policy import (
    CircuitState,
    DegradationMode,
    InMemoryCircuitStore,
    ModelFailurePolicy,
    ModelFailurePolicyConfig,
    RedisCircuitStore,
    candidate_circuit_key,
)
from app.model_gateway.gateway import ModelGateway
from app.model_gateway.langchain import GatewayChatModel

_CAPABILITIES = frozenset(
    {
        ModelCapability.CHAT,
        ModelCapability.STREAMING,
        ModelCapability.TOOLS,
        ModelCapability.STRUCTURED_OUTPUT,
    }
)


@dataclass
class _Clock:
    value: float = 0.0

    def __call__(self) -> float:
        return self.value


class _ScriptedAdapter:
    """Provider-neutral adapter whose scripted failures expose policy behavior."""

    capabilities = _CAPABILITIES

    def __init__(
        self,
        name: str,
        responses: Sequence[ModelResponse | Exception],
        streams: Sequence[Sequence[ModelStreamEvent | Exception]] | None = None,
    ) -> None:
        self.name = name
        self.responses = list(responses)
        self.streams = [list(stream) for stream in (streams or [])]
        self.invoke_count = 0
        self.stream_count = 0

    async def invoke(self, candidate: ModelCandidate, request: ModelRequest) -> ModelResponse:
        self.invoke_count += 1
        item = self.responses[min(self.invoke_count - 1, len(self.responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    async def stream(
        self, candidate: ModelCandidate, request: ModelRequest
    ) -> AsyncIterator[ModelStreamEvent]:
        self.stream_count += 1
        events = self.streams[min(self.stream_count - 1, len(self.streams) - 1)]
        for item in events:
            if isinstance(item, Exception):
                raise item
            yield item


class _FakeRedis:
    """Minimal in-memory Redis surface for cross-store circuit coordination tests."""

    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.values: dict[str, str] = {}
        self.expiries: dict[str, int] = {}

    async def hgetall(self, name: str) -> dict[str, str]:
        return dict(self.hashes.get(name, {}))

    async def set(
        self,
        name: str,
        value: str,
        *,
        nx: bool = False,
        ex: int | None = None,
    ) -> bool | None:
        del ex
        if nx and name in self.values:
            return None
        self.values[name] = value
        return True

    async def hset(self, name: str, *, mapping: dict[str, str]) -> int:
        self.hashes.setdefault(name, {}).update(mapping)
        return len(mapping)

    async def expire(self, name: str, time: int) -> bool:
        self.expiries[name] = time
        return True

    async def get(self, name: str) -> str | None:
        return self.values.get(name)

    async def hincrby(self, name: str, key: str, amount: int = 1) -> int:
        fields = self.hashes.setdefault(name, {})
        value = int(fields.get(key, "0")) + amount
        fields[key] = str(value)
        return value

    async def delete(self, *names: str) -> int:
        deleted = 0
        for name in names:
            if name in self.hashes:
                del self.hashes[name]
                deleted += 1
            if name in self.values:
                del self.values[name]
                deleted += 1
        return deleted


def _response(provider: str, model: str, content: str = "ok") -> ModelResponse:
    return ModelResponse(content=content, finish_reason="stop", provider=provider, model=model)


def _event(provider: str, model: str, content: str) -> ModelStreamEvent:
    return ModelStreamEvent(
        event_type=ModelStreamEventType.TEXT_DELTA,
        provider=provider,
        model=model,
        text_delta=content,
    )


def _completed(provider: str, model: str) -> ModelStreamEvent:
    return ModelStreamEvent(
        event_type=ModelStreamEventType.COMPLETED,
        provider=provider,
        model=model,
        finish_reason="stop",
    )


def _gateway(
    primary: _ScriptedAdapter,
    alternate: _ScriptedAdapter | None = None,
) -> tuple[ModelGateway, tuple[ModelCandidate, ...]]:
    adapters = [primary] if alternate is None else [primary, alternate]
    candidates = tuple(
        ModelCandidate(
            provider=adapter.name,
            model=f"{adapter.name}-model",
            capabilities=_CAPABILITIES,
            timeout_seconds=1.0,
        )
        for adapter in adapters
    )
    return (
        ModelGateway(adapters=adapters, routes=[ModelRoute(name="chat", candidates=candidates)]),
        candidates,
    )


def _request(*, stream: bool = False) -> ModelRequest:
    from app.model_gateway.contracts import ModelMessage

    return ModelRequest(
        route="chat",
        messages=(ModelMessage(role="user", content="hello"),),
        stream=stream,
    )


def _policy(
    *,
    store: InMemoryCircuitStore | None = None,
    max_attempts_per_candidate: int = 2,
    max_total_attempts: int = 4,
    degradation_mode: DegradationMode = DegradationMode.FAIL,
    safe_static_response: str = "The AI service is temporarily unavailable. Please try again later.",
) -> ModelFailurePolicy:
    config = ModelFailurePolicyConfig(
        max_attempts_per_candidate=max_attempts_per_candidate,
        max_total_attempts=max_total_attempts,
        base_backoff_seconds=0.0,
        max_backoff_seconds=0.0,
        jitter_ratio=0.0,
        circuit_failure_threshold=20,
        degradation_mode=degradation_mode,
        safe_static_response=safe_static_response,
    )
    return ModelFailurePolicy(config=config, circuit_store=store or InMemoryCircuitStore(config))


@pytest.mark.asyncio
async def test_transient_failure_retries_then_succeeds() -> None:
    primary = _ScriptedAdapter(
        "openai",
        [
            ModelGatewayError(ModelErrorCategory.CONNECTION, "temporary"),
            _response("openai", "openai-model"),
        ],
    )
    gateway, candidates = _gateway(primary)

    result = await _policy().invoke(gateway, _request(), candidates=candidates)

    assert result.provider == "openai"
    assert primary.invoke_count == 2


@pytest.mark.asyncio
async def test_non_retryable_failure_does_not_call_alternate() -> None:
    primary = _ScriptedAdapter(
        "openai", [ModelGatewayError(ModelErrorCategory.BAD_REQUEST, "invalid")]
    )
    alternate = _ScriptedAdapter("dashscope", [_response("dashscope", "qwen")])
    gateway, candidates = _gateway(primary, alternate)

    with pytest.raises(ModelGatewayError) as exc_info:
        await _policy().invoke(gateway, _request(), candidates=candidates)

    assert exc_info.value.category is ModelErrorCategory.BAD_REQUEST
    assert primary.invoke_count == 1
    assert alternate.invoke_count == 0


@pytest.mark.asyncio
async def test_exhausted_primary_falls_back_and_reports_actual_provider() -> None:
    primary = _ScriptedAdapter(
        "openai",
        [ModelGatewayError(ModelErrorCategory.PROVIDER_UNAVAILABLE, "down")],
    )
    alternate = _ScriptedAdapter("dashscope", [_response("dashscope", "qwen", "alternate")])
    gateway, candidates = _gateway(primary, alternate)

    result = await _policy().invoke(gateway, _request(), candidates=candidates)

    assert result.content == "alternate"
    assert result.provider == "dashscope"
    assert result.model == "qwen"
    assert primary.invoke_count == 2
    assert alternate.invoke_count == 1


@pytest.mark.asyncio
async def test_cancellation_during_backoff_stops_all_attempts() -> None:
    primary = _ScriptedAdapter("openai", [ModelGatewayError(ModelErrorCategory.TIMEOUT, "slow")])
    alternate = _ScriptedAdapter("dashscope", [_response("dashscope", "qwen")])
    gateway, candidates = _gateway(primary, alternate)

    async def cancelled_sleep(delay: float) -> None:
        raise asyncio.CancelledError

    policy = ModelFailurePolicy(
        config=ModelFailurePolicyConfig(
            max_attempts_per_candidate=3,
            max_total_attempts=4,
            base_backoff_seconds=1.0,
            max_backoff_seconds=1.0,
            jitter_ratio=0.0,
            circuit_failure_threshold=20,
        ),
        circuit_store=InMemoryCircuitStore(),
        sleep=cancelled_sleep,
    )

    with pytest.raises(asyncio.CancelledError):
        await policy.invoke(gateway, _request(), candidates=candidates)

    assert primary.invoke_count == 1
    assert alternate.invoke_count == 0


@pytest.mark.asyncio
async def test_deadline_bounds_attempts() -> None:
    clock = _Clock()
    primary = _ScriptedAdapter("openai", [ModelGatewayError(ModelErrorCategory.CONNECTION, "down")])
    gateway, candidates = _gateway(primary)

    async def advance(delay: float) -> None:
        clock.value += delay

    policy = ModelFailurePolicy(
        config=ModelFailurePolicyConfig(
            max_attempts_per_candidate=5,
            max_total_attempts=5,
            total_deadline_seconds=0.5,
            base_backoff_seconds=0.4,
            max_backoff_seconds=0.4,
            jitter_ratio=0.0,
            circuit_failure_threshold=20,
        ),
        circuit_store=InMemoryCircuitStore(),
        clock=clock,
        sleep=advance,
    )

    with pytest.raises(ModelGatewayError) as exc_info:
        await policy.invoke(gateway, _request(), candidates=candidates)

    assert exc_info.value.category is ModelErrorCategory.TIMEOUT
    assert primary.invoke_count <= 2


@pytest.mark.asyncio
async def test_stream_failure_before_visible_delta_can_fallback() -> None:
    primary = _ScriptedAdapter(
        "openai",
        [_response("openai", "openai-model")],
        streams=[[ModelGatewayError(ModelErrorCategory.CONNECTION, "down")]],
    )
    alternate = _ScriptedAdapter(
        "dashscope",
        [_response("dashscope", "qwen")],
        streams=[[_event("dashscope", "qwen", "answer"), _completed("dashscope", "qwen")]],
    )
    gateway, candidates = _gateway(primary, alternate)

    events = [
        event
        async for event in _policy().stream(gateway, _request(stream=True), candidates=candidates)
    ]

    assert "".join(event.text_delta for event in events) == "answer"
    assert alternate.stream_count == 1


@pytest.mark.asyncio
async def test_stream_failure_after_visible_delta_never_falls_back() -> None:
    primary = _ScriptedAdapter(
        "openai",
        [_response("openai", "openai-model")],
        streams=[
            [
                _event("openai", "openai-model", "partial"),
                ModelGatewayError(ModelErrorCategory.CONNECTION, "broken"),
            ]
        ],
    )
    alternate = _ScriptedAdapter(
        "dashscope",
        [_response("dashscope", "qwen")],
        streams=[[_event("dashscope", "qwen", "duplicate"), _completed("dashscope", "qwen")]],
    )
    gateway, candidates = _gateway(primary, alternate)

    events: list[ModelStreamEvent] = []
    with pytest.raises(ModelGatewayError):
        async for event in _policy().stream(gateway, _request(stream=True), candidates=candidates):
            events.append(event)

    assert "".join(event.text_delta for event in events) == "partial"
    assert alternate.stream_count == 0


@pytest.mark.asyncio
async def test_circuit_opens_and_is_shared_by_two_policy_instances() -> None:
    store = InMemoryCircuitStore(
        ModelFailurePolicyConfig(
            max_attempts_per_candidate=1,
            max_total_attempts=1,
            circuit_failure_threshold=1,
            circuit_open_seconds=30.0,
        )
    )
    primary = _ScriptedAdapter(
        "openai", [ModelGatewayError(ModelErrorCategory.PROVIDER_UNAVAILABLE, "down")]
    )
    alternate = _ScriptedAdapter("dashscope", [_response("dashscope", "qwen")])
    gateway, candidates = _gateway(primary, alternate)
    first = _policy(store=store, max_attempts_per_candidate=1, max_total_attempts=1)
    second = _policy(store=store, max_attempts_per_candidate=1, max_total_attempts=1)

    with pytest.raises(ModelGatewayError):
        await first.invoke(gateway, _request(), candidates=(candidates[0],))
    assert await store.get_state(candidate_circuit_key(candidates[0])) is CircuitState.OPEN

    result = await second.invoke(gateway, _request(), candidates=candidates)

    assert result.provider == "dashscope"
    assert primary.invoke_count == 1


@pytest.mark.asyncio
async def test_safe_static_degradation_is_explicit_and_marked() -> None:
    primary = _ScriptedAdapter(
        "openai", [ModelGatewayError(ModelErrorCategory.PROVIDER_UNAVAILABLE, "down")]
    )
    gateway, candidates = _gateway(primary)
    policy = _policy(
        degradation_mode=DegradationMode.SAFE_STATIC_RESPONSE,
        safe_static_response="暂时无法处理，请稍后重试。",
    )

    result = await policy.invoke(gateway, _request(), candidates=candidates)

    assert result.content == "暂时无法处理，请稍后重试。"
    assert result.degraded is True
    assert result.provider == "degraded"


@pytest.mark.asyncio
async def test_gateway_chat_model_routes_production_calls_through_t14_policy() -> None:
    primary = _ScriptedAdapter(
        "openai",
        [ModelGatewayError(ModelErrorCategory.CONNECTION, "down")],
    )
    alternate = _ScriptedAdapter("dashscope", [_response("dashscope", "qwen", "answer")])
    gateway, _ = _gateway(primary, alternate)
    model = GatewayChatModel(
        gateway=gateway,
        route="chat",
        failure_policy=_policy(max_attempts_per_candidate=1),
    )

    response = await model.ainvoke([HumanMessage(content="hello")])

    assert response.content == "answer"
    assert response.response_metadata["provider"] == "dashscope"
    assert response.response_metadata["model"] == "qwen"
    assert primary.invoke_count == 1
    assert alternate.invoke_count == 1


def test_backoff_is_bounded_and_jitter_is_injectable() -> None:
    config = ModelFailurePolicyConfig(
        base_backoff_seconds=2.0,
        max_backoff_seconds=3.0,
        jitter_ratio=0.5,
        retry_after_max_seconds=1.0,
    )
    error = ModelGatewayError(
        ModelErrorCategory.RATE_LIMIT,
        "limited",
        retry_after_seconds=99.0,
    )

    low_policy = ModelFailurePolicy(
        config=config,
        random_source=lambda: 0.0,
    )
    high_policy = ModelFailurePolicy(
        config=config,
        random_source=lambda: 1.0,
    )

    assert low_policy._backoff_delay(error, 1) == 1.0
    assert high_policy._backoff_delay(error, 1) == 3.0
    assert low_policy._backoff_delay(error, 2) == 1.5
    assert high_policy._backoff_delay(error, 2) == 3.0


def test_retry_after_is_clamped_before_backoff_cap() -> None:
    config = ModelFailurePolicyConfig(
        base_backoff_seconds=0.25,
        max_backoff_seconds=10.0,
        jitter_ratio=0.0,
        retry_after_max_seconds=3.0,
    )
    policy = ModelFailurePolicy(config=config, random_source=lambda: 0.5)
    error = ModelGatewayError(
        ModelErrorCategory.RATE_LIMIT,
        "limited",
        retry_after_seconds=90.0,
    )

    assert policy._backoff_delay(error, 1) == 3.0


@pytest.mark.asyncio
async def test_primary_success_never_calls_alternate() -> None:
    primary = _ScriptedAdapter("openai", [_response("openai", "gpt")])
    alternate = _ScriptedAdapter("dashscope", [_response("dashscope", "qwen")])
    gateway, candidates = _gateway(primary, alternate)

    result = await _policy().invoke(gateway, _request(), candidates=candidates)

    assert result.provider == "openai"
    assert primary.invoke_count == 1
    assert alternate.invoke_count == 0


@pytest.mark.asyncio
async def test_capability_incompatible_candidate_is_not_invoked() -> None:
    primary = _ScriptedAdapter("openai", [_response("openai", "gpt")])
    alternate = _ScriptedAdapter("dashscope", [_response("dashscope", "qwen")])
    primary_candidate = ModelCandidate(
        provider="openai",
        model="gpt",
        capabilities=frozenset({ModelCapability.CHAT}),
        timeout_seconds=1.0,
    )
    alternate_candidate = ModelCandidate(
        provider="dashscope",
        model="qwen",
        capabilities=_CAPABILITIES,
        timeout_seconds=1.0,
    )
    gateway = ModelGateway(
        adapters=[primary, alternate],
        routes=[
            ModelRoute(
                name="chat",
                candidates=(primary_candidate, alternate_candidate),
            )
        ],
    )
    request = ModelRequest(
        route="chat",
        messages=(
            # The tool request makes the first candidate structurally ineligible.
            # The policy must skip it before ModelGateway/provider invocation.
            _request().messages[0],
        ),
        tools=(ModelTool(name="lookup", input_schema={}),),
    )

    result = await _policy().invoke(
        gateway,
        request,
        candidates=(primary_candidate, alternate_candidate),
    )

    assert result.provider == "dashscope"
    assert primary.invoke_count == 0
    assert alternate.invoke_count == 1


@pytest.mark.asyncio
async def test_all_candidates_fail_with_one_normalized_terminal_error() -> None:
    primary = _ScriptedAdapter(
        "openai",
        [ModelGatewayError(ModelErrorCategory.PROVIDER_UNAVAILABLE, "down")],
    )
    alternate = _ScriptedAdapter(
        "dashscope",
        [ModelGatewayError(ModelErrorCategory.CONNECTION, "also down")],
    )
    gateway, candidates = _gateway(primary, alternate)
    policy = _policy(max_attempts_per_candidate=1, max_total_attempts=2)

    with pytest.raises(ModelGatewayError) as exc_info:
        await policy.invoke(gateway, _request(), candidates=candidates)

    assert exc_info.value.category is ModelErrorCategory.CONNECTION
    assert primary.invoke_count == 1
    assert alternate.invoke_count == 1


@pytest.mark.asyncio
async def test_half_open_allows_one_probe_and_success_closes_circuit() -> None:
    store = InMemoryCircuitStore(failure_threshold=1, open_seconds=10.0)
    key = "openai-gpt"

    initial = await store.acquire(key, now=0.0)
    assert initial.state is CircuitState.CLOSED
    await store.record_failure(key, initial, now=0.0)
    assert await store.get_state(key, now=1.0) is CircuitState.OPEN

    blocked = await store.acquire(key, now=1.0)
    assert blocked.allowed is False
    probe = await store.acquire(key, now=10.0)
    second_probe = await store.acquire(key, now=10.0)
    assert probe.allowed is True
    assert probe.state is CircuitState.HALF_OPEN
    assert second_probe.allowed is False
    assert second_probe.state is CircuitState.HALF_OPEN

    assert await store.record_success(key, probe, now=10.0) is CircuitState.CLOSED
    assert await store.get_state(key) is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_failed_half_open_probe_reopens_circuit() -> None:
    store = InMemoryCircuitStore(failure_threshold=1, open_seconds=10.0)
    key = "dashscope-qwen"
    initial = await store.acquire(key, now=0.0)
    await store.record_failure(key, initial, now=0.0)
    probe = await store.acquire(key, now=10.0)

    assert await store.record_failure(key, probe, now=10.0) is CircuitState.OPEN
    assert await store.get_state(key, now=10.1) is CircuitState.OPEN


@pytest.mark.asyncio
async def test_half_open_probe_admission_is_bounded_under_concurrency() -> None:
    store = InMemoryCircuitStore(failure_threshold=1, open_seconds=1.0)
    key = "openai-concurrency"
    initial = await store.acquire(key, now=0.0)
    await store.record_failure(key, initial, now=0.0)

    permits = await asyncio.gather(*(store.acquire(key, now=1.0) for _ in range(12)))

    assert sum(permit.allowed for permit in permits) == 1
    assert all(permit.state is CircuitState.HALF_OPEN for permit in permits)


@pytest.mark.asyncio
async def test_redis_circuit_store_shares_state_and_half_open_probe() -> None:
    redis = _FakeRedis()
    config = ModelFailurePolicyConfig(
        circuit_failure_threshold=1,
        circuit_open_seconds=10.0,
        circuit_half_open_probe_seconds=5.0,
    )
    first_store = RedisCircuitStore(cast(aioredis.Redis, redis), config)
    second_store = RedisCircuitStore(cast(aioredis.Redis, redis), config)
    key = "shared-openai-gpt"

    permit = await first_store.acquire(key, now=0.0)
    assert await first_store.record_failure(key, permit, now=0.0) is CircuitState.OPEN
    assert redis.expiries[first_store._state_key(key)] == 15
    assert (await second_store.acquire(key, now=1.0)).allowed is False

    probe = await first_store.acquire(key, now=10.0)
    competing_probe = await second_store.acquire(key, now=10.0)
    assert probe.allowed is True
    assert competing_probe.allowed is False
    assert await first_store.record_success(key, probe, now=10.0) is CircuitState.CLOSED
    assert await second_store.get_state(key) is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_bad_request_does_not_trip_circuit() -> None:
    store = InMemoryCircuitStore(failure_threshold=1)
    primary = _ScriptedAdapter(
        "openai",
        [ModelGatewayError(ModelErrorCategory.BAD_REQUEST, "invalid")],
    )
    gateway, candidates = _gateway(primary)

    with pytest.raises(ModelGatewayError):
        await _policy(store=store, max_attempts_per_candidate=3).invoke(
            gateway,
            _request(),
            candidates=candidates,
        )

    assert await store.get_state(candidate_circuit_key(candidates[0])) is CircuitState.CLOSED
    assert primary.invoke_count == 1


@pytest.mark.asyncio
async def test_bad_request_releases_half_open_probe_without_tripping_circuit() -> None:
    store = InMemoryCircuitStore(failure_threshold=1, open_seconds=5.0)
    primary = _ScriptedAdapter(
        "openai",
        [ModelGatewayError(ModelErrorCategory.BAD_REQUEST, "invalid")],
    )
    gateway, candidates = _gateway(primary)
    key = candidate_circuit_key(candidates[0])
    initial = await store.acquire(key, now=0.0)
    await store.record_failure(key, initial, now=0.0)
    clock = _Clock(value=5.0)
    config = ModelFailurePolicyConfig(
        max_attempts_per_candidate=1,
        max_total_attempts=1,
        base_backoff_seconds=0.0,
        max_backoff_seconds=0.0,
        circuit_failure_threshold=1,
        circuit_open_seconds=5.0,
    )
    policy = ModelFailurePolicy(config=config, circuit_store=store, clock=clock)

    with pytest.raises(ModelGatewayError):
        await policy.invoke(gateway, _request(), candidates=candidates)

    assert await store.get_state(key) is CircuitState.CLOSED


@pytest.mark.asyncio
async def test_safe_static_degradation_does_not_satisfy_tool_request() -> None:
    primary = _ScriptedAdapter(
        "openai",
        [ModelGatewayError(ModelErrorCategory.PROVIDER_UNAVAILABLE, "down")],
    )
    gateway, candidates = _gateway(primary)
    request = ModelRequest(
        route="chat",
        messages=(_request().messages[0],),
        tools=(ModelTool(name="lookup", input_schema={}),),
    )
    policy = _policy(degradation_mode=DegradationMode.SAFE_STATIC_RESPONSE)

    with pytest.raises(ModelGatewayError) as exc_info:
        await policy.invoke(gateway, request, candidates=candidates)

    assert exc_info.value.category is ModelErrorCategory.PROVIDER_UNAVAILABLE


@pytest.mark.asyncio
async def test_gateway_configuration_error_is_not_normalized_as_provider_failure() -> None:
    primary = _ScriptedAdapter("openai", [_response("openai", "gpt")])
    gateway, _ = _gateway(primary)
    unknown_candidate = ModelCandidate(
        provider="missing",
        model="unknown",
        capabilities=_CAPABILITIES,
        timeout_seconds=1.0,
    )

    with pytest.raises(ModelConfigurationError):
        await _policy().invoke(gateway, _request(), candidates=(unknown_candidate,))
