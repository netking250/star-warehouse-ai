"""Real DashScope OpenAI-compatible adapter for the model gateway."""

from __future__ import annotations

from openai import AsyncOpenAI

from app.model_gateway.providers.openai_compatible import OpenAICompatibleProviderAdapter


class DashScopeProviderAdapter(OpenAICompatibleProviderAdapter):
    """Use DashScope's OpenAI-compatible endpoint behind the provider interface."""

    def __init__(
        self,
        *,
        client: AsyncOpenAI | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        default_timeout_seconds: float = 30.0,
    ) -> None:
        super().__init__(
            provider_name="dashscope",
            client=client,
            api_key=api_key,
            base_url=base_url,
            default_timeout_seconds=default_timeout_seconds,
        )
