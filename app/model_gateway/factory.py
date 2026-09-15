"""Trusted configuration assembly for the Dynamic Model Gateway."""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from typing import cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig

from app.core.config import Settings, settings
from app.core.redis import create_redis_client
from app.model_gateway.contracts import ModelCandidate, ModelRoute
from app.model_gateway.failure_policy import (
    ModelFailurePolicy,
    ModelFailurePolicyConfig,
    RedisCircuitStore,
)
from app.model_gateway.gateway import ModelGateway
from app.model_gateway.langchain import GatewayChatModel
from app.model_gateway.providers.dashscope import DashScopeProviderAdapter
from app.model_gateway.providers.openai import OpenAIProviderAdapter


def build_model_gateway(config: Settings) -> ModelGateway:
    """Validate routes and assemble lazy real-provider adapters without network I/O."""
    adapters = [
        OpenAIProviderAdapter(
            api_key=config.OPENAI_API_KEY.get_secret_value(),
            base_url=config.MODEL_OPENAI_BASE_URL,
            default_timeout_seconds=config.MODEL_GATEWAY_DEFAULT_TIMEOUT_SECONDS,
        ),
        DashScopeProviderAdapter(
            api_key=config.DASHSCOPE_API_KEY.get_secret_value(),
            base_url=config.MODEL_DASHSCOPE_BASE_URL,
            default_timeout_seconds=config.MODEL_GATEWAY_DEFAULT_TIMEOUT_SECONDS,
        ),
    ]
    routes = [
        ModelRoute(
            name=name,
            candidates=tuple(
                ModelCandidate(
                    provider=candidate.provider,
                    model=candidate.model,
                    capabilities=candidate.capabilities,
                    timeout_seconds=candidate.timeout_seconds,
                )
                for candidate in route.candidates
            ),
        )
        for name, route in config.MODEL_ROUTES.items()
    ]
    return ModelGateway(adapters=adapters, routes=routes)


@lru_cache(maxsize=1)
def get_model_gateway() -> ModelGateway:
    """Return the process-local gateway built from trusted restart-time settings."""
    return build_model_gateway(settings)


@lru_cache(maxsize=1)
def get_model_failure_policy() -> ModelFailurePolicy:
    """Return the process policy using Redis for cross-instance circuit coordination."""
    policy_config = ModelFailurePolicyConfig.from_settings(settings)
    return ModelFailurePolicy(
        config=policy_config,
        circuit_store=RedisCircuitStore(create_redis_client(), policy_config),
    )


def create_model_client(
    route: str = "default_chat",
    *,
    model_override: str | None = None,
    provider_override: str | None = None,
    temperature: float = 0,
    timeout: float | None = None,
    max_output_tokens: int | None = None,
    default_config: RunnableConfig | None = None,
    gateway: ModelGateway | None = None,
    failure_policy: ModelFailurePolicy | None = None,
) -> BaseChatModel:
    """Create a LangChain-compatible client for one trusted server-side route."""
    selected_gateway = gateway or get_model_gateway()
    candidates = selected_gateway.resolve(route)
    candidate: ModelCandidate | None = None
    if provider_override is not None:
        candidate = next(
            (item for item in candidates if item.provider == provider_override),
            None,
        )
        if candidate is None:
            raise ValueError(
                f"Provider {provider_override!r} is not configured for route {route!r}"
            )
    if model_override is not None:
        candidate = replace(candidate or candidates[0], model=model_override)
    model: BaseChatModel = GatewayChatModel(
        gateway=selected_gateway,
        route=route,
        candidate=candidate,
        temperature=temperature,
        timeout_seconds=timeout,
        max_output_tokens=max_output_tokens,
        failure_policy=failure_policy or get_model_failure_policy(),
    )
    if default_config is not None:
        model = cast(BaseChatModel, model.with_config(default_config))
    return model
