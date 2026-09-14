"""Deterministic offline provider adapter."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping

from app.model_gateway.contracts import (
    ModelCandidate,
    ModelCapability,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelToolCall,
    ModelUsage,
)
from app.model_gateway.errors import ModelErrorCategory, ModelGatewayError


class MockProviderAdapter:
    """Return deterministic responses through the production provider seam."""

    name = "mock"
    capabilities = frozenset(
        {
            ModelCapability.CHAT,
            ModelCapability.STREAMING,
            ModelCapability.TOOLS,
            ModelCapability.STRUCTURED_OUTPUT,
        }
    )

    def __init__(
        self,
        *,
        content: str = "mock response",
        stream_chunks: tuple[str, ...] | None = None,
        tool_calls: tuple[ModelToolCall, ...] = (),
        structured_output: Mapping[str, object] | None = None,
        latency_seconds: float = 0,
        error_category: ModelErrorCategory | None = None,
        simulate_timeout: bool = False,
        malformed_response: bool = False,
    ) -> None:
        self._content = content
        self._stream_chunks = stream_chunks or (content,)
        self._tool_calls = tool_calls
        self._structured_output = structured_output
        self._latency_seconds = latency_seconds
        self._error_category = error_category
        self._simulate_timeout = simulate_timeout
        self._malformed_response = malformed_response
        self.attempt_count = 0

    async def invoke(self, candidate: ModelCandidate, request: ModelRequest) -> ModelResponse:
        """Return the configured deterministic response."""
        self.attempt_count += 1
        if self._latency_seconds:
            await asyncio.sleep(self._latency_seconds)
        if self._simulate_timeout:
            raise ModelGatewayError(
                ModelErrorCategory.TIMEOUT,
                "Mock provider timed out",
                provider=self.name,
                model=candidate.model,
            )
        if self._error_category is not None:
            raise ModelGatewayError(
                self._error_category,
                "Injected mock provider failure",
                provider=self.name,
                model=candidate.model,
            )
        if self._malformed_response:
            raise ModelGatewayError(
                ModelErrorCategory.INVALID_RESPONSE,
                "Mock provider returned an invalid response",
                provider=self.name,
                model=candidate.model,
            )
        return ModelResponse(
            content=self._content,
            finish_reason="stop",
            provider=self.name,
            model=candidate.model,
            usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
            tool_calls=self._tool_calls,
            structured_output=self._structured_output,
        )

    async def stream(
        self, candidate: ModelCandidate, request: ModelRequest
    ) -> AsyncIterator[ModelStreamEvent]:
        """Yield deterministic text deltas and one terminal metadata event."""
        self.attempt_count += 1
        if self._simulate_timeout:
            raise ModelGatewayError(
                ModelErrorCategory.TIMEOUT,
                "Mock provider timed out",
                provider=self.name,
                model=candidate.model,
            )
        if self._error_category is not None:
            raise ModelGatewayError(
                self._error_category,
                "Injected mock provider failure",
                provider=self.name,
                model=candidate.model,
            )
        for chunk in self._stream_chunks:
            if self._latency_seconds:
                await asyncio.sleep(self._latency_seconds)
            yield ModelStreamEvent(
                event_type=ModelStreamEventType.TEXT_DELTA,
                provider=self.name,
                model=candidate.model,
                text_delta=chunk,
            )
        if self._malformed_response:
            raise ModelGatewayError(
                ModelErrorCategory.INVALID_RESPONSE,
                "Mock provider returned malformed streaming output",
                provider=self.name,
                model=candidate.model,
            )
        yield ModelStreamEvent(
            event_type=ModelStreamEventType.COMPLETED,
            provider=self.name,
            model=candidate.model,
            finish_reason="stop",
            usage=ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2),
        )
