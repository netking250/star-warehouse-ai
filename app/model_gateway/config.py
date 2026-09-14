"""Validated operator configuration models for gateway routes."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.model_gateway.contracts import ModelCapability


class ModelCandidateSettings(BaseModel):
    """Trusted configuration for one ordered route candidate."""

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    capabilities: frozenset[ModelCapability]
    timeout_seconds: float = Field(default=30.0, gt=0, le=300)

    @field_validator("provider", "model")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value cannot be blank")
        return stripped


class ModelRouteSettings(BaseModel):
    """Trusted ordered candidate list for one application use case."""

    candidates: tuple[ModelCandidateSettings, ...] = Field(min_length=1)


def _candidate(
    provider: str,
    model: str,
    capabilities: frozenset[ModelCapability],
    timeout_seconds: float,
) -> ModelCandidateSettings:
    return ModelCandidateSettings(
        provider=provider,
        model=model,
        capabilities=capabilities,
        timeout_seconds=timeout_seconds,
    )


def default_model_routes() -> dict[str, ModelRouteSettings]:
    """Return restart-on-change route defaults for current production use cases."""
    chat = frozenset({ModelCapability.CHAT})
    tools = frozenset({ModelCapability.CHAT, ModelCapability.TOOLS})
    structured = frozenset(
        {ModelCapability.CHAT, ModelCapability.TOOLS, ModelCapability.STRUCTURED_OUTPUT}
    )
    full = frozenset({*structured, ModelCapability.STREAMING})
    route_models = {
        "default_chat": ("gpt-4o-mini", "qwen-plus", full, 30.0),
        "intent": ("gpt-4o-mini", "qwen-turbo", tools, 5.0),
        "structured": ("gpt-4o-mini", "qwen-turbo", structured, 15.0),
        "evaluation": ("gpt-4o-mini", "qwen-turbo", structured, 30.0),
        "shadow": ("gpt-4o-mini", "qwen-turbo", full, 30.0),
        "rewrite": ("gpt-4o-mini", "qwen-turbo", structured, 5.0),
        "summarization": ("gpt-4o-mini", "qwen-turbo", chat, 30.0),
        "safety": ("gpt-4o-mini", "qwen-turbo", structured, 10.0),
    }
    routes: dict[str, ModelRouteSettings] = {}
    for route, (
        openai_model,
        dashscope_model,
        capabilities,
        timeout_seconds,
    ) in route_models.items():
        routes[route] = ModelRouteSettings(
            candidates=(
                _candidate("openai", openai_model, capabilities, timeout_seconds),
                _candidate("dashscope", dashscope_model, capabilities, timeout_seconds),
            )
        )
    return routes
