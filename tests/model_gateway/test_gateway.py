"""Behavior tests for the provider-neutral model gateway."""

import pytest

from app.model_gateway.config import default_model_routes
from app.model_gateway.contracts import (
    ModelCandidate,
    ModelCapability,
    ModelMessage,
    ModelRequest,
    ModelRoute,
    ModelTool,
    ModelToolCall,
)
from app.model_gateway.errors import (
    ModelConfigurationError,
    ModelErrorCategory,
    ModelGatewayError,
)
from app.model_gateway.gateway import ModelGateway
from app.model_gateway.providers.mock import MockProviderAdapter


@pytest.mark.asyncio
async def test_configured_route_invokes_mock_through_gateway() -> None:
    adapter = MockProviderAdapter(content="deterministic answer")
    candidate = ModelCandidate(
        provider="mock",
        model="mock-chat-v1",
        capabilities=adapter.capabilities,
        timeout_seconds=1.0,
    )
    gateway = ModelGateway(
        adapters=[adapter],
        routes=[ModelRoute(name="default_chat", candidates=(candidate,))],
    )

    resolved = gateway.resolve("default_chat")
    response = await gateway.invoke(
        resolved[0],
        ModelRequest(
            route="default_chat",
            messages=(ModelMessage(role="user", content="hello"),),
        ),
    )

    assert response.content == "deterministic answer"
    assert response.provider == "mock"
    assert response.model == "mock-chat-v1"


@pytest.mark.asyncio
async def test_unsupported_capability_is_rejected_before_provider_call() -> None:
    adapter = MockProviderAdapter(content="must not be called")
    candidate = ModelCandidate(
        provider="mock",
        model="chat-only",
        capabilities=frozenset({ModelCapability.CHAT}),
        timeout_seconds=1.0,
    )
    gateway = ModelGateway(
        adapters=[adapter],
        routes=[ModelRoute(name="intent", candidates=(candidate,))],
    )
    request = ModelRequest(
        route="intent",
        messages=(ModelMessage(role="user", content="classify"),),
        tools=(ModelTool(name="classify", input_schema={"type": "object"}),),
    )

    with pytest.raises(ModelGatewayError) as exc_info:
        await gateway.invoke(candidate, request)

    assert exc_info.value.category is ModelErrorCategory.UNSUPPORTED_CAPABILITY
    assert adapter.attempt_count == 0


def test_default_routes_order_openai_before_dashscope() -> None:
    routes = default_model_routes()

    for route in routes.values():
        assert route.candidates[0].provider == "openai"
        assert route.candidates[1].provider == "dashscope"


def test_unknown_route_is_rejected() -> None:
    gateway = ModelGateway(adapters=[MockProviderAdapter()], routes=[])

    with pytest.raises(ModelConfigurationError, match="Unknown model route"):
        gateway.resolve("missing")


def test_invalid_request_timeout_is_rejected_locally() -> None:
    with pytest.raises(ValueError, match="timeout"):
        ModelRequest(
            route="default_chat",
            messages=(ModelMessage(role="user", content="hello"),),
            timeout_seconds=0,
        )


def test_unknown_provider_is_rejected_during_registry_construction() -> None:
    candidate = ModelCandidate(
        provider="unknown",
        model="model",
        capabilities=frozenset({ModelCapability.CHAT}),
        timeout_seconds=1.0,
    )

    with pytest.raises(ModelConfigurationError, match="Unknown model provider"):
        ModelGateway(
            adapters=[MockProviderAdapter()],
            routes=[ModelRoute(name="default_chat", candidates=(candidate,))],
        )


def test_candidate_without_chat_capability_is_rejected_during_registry_construction() -> None:
    candidate = ModelCandidate(
        provider="mock",
        model="streaming-only",
        capabilities=frozenset({ModelCapability.STREAMING}),
        timeout_seconds=1.0,
    )

    with pytest.raises(ModelConfigurationError, match="lacks chat capability"):
        ModelGateway(
            adapters=[MockProviderAdapter()],
            routes=[ModelRoute(name="default_chat", candidates=(candidate,))],
        )


def test_resolution_filters_candidate_without_required_capability() -> None:
    class AlternateMockProvider(MockProviderAdapter):
        name = "alternate"

    primary_adapter = MockProviderAdapter()
    alternate_adapter = AlternateMockProvider()
    primary = ModelCandidate(
        provider="mock",
        model="tools-model",
        capabilities=frozenset({ModelCapability.CHAT, ModelCapability.TOOLS}),
        timeout_seconds=1.0,
    )
    alternate = ModelCandidate(
        provider="alternate",
        model="chat-model",
        capabilities=frozenset({ModelCapability.CHAT}),
        timeout_seconds=1.0,
    )
    gateway = ModelGateway(
        adapters=[primary_adapter, alternate_adapter],
        routes=[ModelRoute(name="intent", candidates=(primary, alternate))],
    )

    assert gateway.resolve("intent", frozenset({ModelCapability.TOOLS})) == (primary,)


@pytest.mark.asyncio
async def test_primary_failure_does_not_invoke_alternate_candidate() -> None:
    class OpenAIMockProvider(MockProviderAdapter):
        name = "openai"

    class DashScopeMockProvider(MockProviderAdapter):
        name = "dashscope"

    primary_adapter = OpenAIMockProvider(error_category=ModelErrorCategory.CONNECTION)
    alternate_adapter = DashScopeMockProvider(content="alternate")
    candidates = tuple(
        ModelCandidate(
            provider=provider,
            model=f"{provider}-model",
            capabilities=frozenset({ModelCapability.CHAT}),
            timeout_seconds=1.0,
        )
        for provider in ("openai", "dashscope")
    )
    gateway = ModelGateway(
        adapters=[primary_adapter, alternate_adapter],
        routes=[ModelRoute(name="default_chat", candidates=candidates)],
    )

    with pytest.raises(ModelGatewayError) as exc_info:
        await gateway.invoke_primary(
            ModelRequest(
                route="default_chat",
                messages=(ModelMessage(role="user", content="hello"),),
            )
        )

    assert exc_info.value.category is ModelErrorCategory.CONNECTION
    assert primary_adapter.attempt_count == 1
    assert alternate_adapter.attempt_count == 0


@pytest.mark.asyncio
async def test_mock_provider_supports_tool_and_structured_results() -> None:
    adapter = MockProviderAdapter(
        content="",
        tool_calls=(ModelToolCall(id="call-1", name="lookup", arguments={"id": 1}),),
        structured_output={"accepted": True},
    )
    candidate = ModelCandidate(
        provider="mock",
        model="mock-tools",
        capabilities=adapter.capabilities,
        timeout_seconds=1.0,
    )
    gateway = ModelGateway(
        adapters=[adapter],
        routes=[ModelRoute(name="structured", candidates=(candidate,))],
    )

    response = await gateway.invoke_primary(
        ModelRequest(
            route="structured",
            messages=(ModelMessage(role="user", content="lookup"),),
            tools=(ModelTool(name="lookup", input_schema={"type": "object"}),),
        )
    )

    assert response.tool_calls[0].arguments == {"id": 1}
    assert response.structured_output == {"accepted": True}
