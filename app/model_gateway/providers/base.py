"""Provider adapter interface for model invocation."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from app.model_gateway.contracts import (
    ModelCandidate,
    ModelCapability,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
)


class ProviderAdapter(Protocol):
    """Translate one provider-neutral request without retry or fallback policy."""

    @property
    def name(self) -> str:
        """Return the stable provider identifier."""

        ...

    @property
    def capabilities(self) -> frozenset[ModelCapability]:
        """Return capabilities implemented and verified by this adapter."""

        ...

    async def invoke(self, candidate: ModelCandidate, request: ModelRequest) -> ModelResponse:
        """Perform exactly one non-streaming provider attempt."""

        ...

    def stream(
        self, candidate: ModelCandidate, request: ModelRequest
    ) -> AsyncIterator[ModelStreamEvent]:
        """Perform exactly one streaming provider attempt."""

        ...
