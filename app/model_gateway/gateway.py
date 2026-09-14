"""Capability-aware model route resolution and explicit candidate invocation."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable

from app.model_gateway.contracts import (
    ModelCandidate,
    ModelCapability,
    ModelRequest,
    ModelResponse,
    ModelRoute,
    ModelStreamEvent,
)
from app.model_gateway.errors import (
    ModelConfigurationError,
    ModelErrorCategory,
    ModelGatewayError,
)
from app.model_gateway.providers.base import ProviderAdapter


class ModelGateway:
    """Resolve configured routes and invoke only an explicitly chosen candidate."""

    def __init__(
        self,
        *,
        adapters: Iterable[ProviderAdapter],
        routes: Iterable[ModelRoute],
    ) -> None:
        adapter_list = list(adapters)
        route_list = list(routes)
        self._adapters = {adapter.name: adapter for adapter in adapter_list}
        self._routes = {route.name: route for route in route_list}
        if len(self._adapters) != len(adapter_list):
            raise ModelConfigurationError("Duplicate model provider adapter")
        if len(self._routes) != len(route_list):
            raise ModelConfigurationError("Duplicate model route")
        for route in route_list:
            self._validate_route(route)

    def resolve(
        self,
        route: str,
        required_capabilities: frozenset[ModelCapability] = frozenset(),
    ) -> tuple[ModelCandidate, ...]:
        """Return capable candidates in configured order without invoking them."""
        try:
            candidates = self._routes[route].candidates
        except KeyError as exc:
            raise ModelConfigurationError(f"Unknown model route: {route}") from exc
        resolved = tuple(
            candidate for candidate in candidates if required_capabilities <= candidate.capabilities
        )
        if required_capabilities and not resolved:
            required = ", ".join(sorted(required_capabilities))
            raise ModelGatewayError(
                ModelErrorCategory.UNSUPPORTED_CAPABILITY,
                f"No candidate for route {route!r} supports: {required}",
            )
        return resolved

    async def invoke(self, candidate: ModelCandidate, request: ModelRequest) -> ModelResponse:
        """Invoke one candidate without retrying or selecting another provider."""
        if request.stream:
            raise ModelGatewayError(
                ModelErrorCategory.BAD_REQUEST,
                "Streaming requests must use ModelGateway.stream()",
                provider=candidate.provider,
                model=candidate.model,
            )
        adapter = self._adapter(candidate)
        self._validate_request(candidate, adapter, request)
        return await adapter.invoke(candidate, request)

    async def invoke_primary(self, request: ModelRequest) -> ModelResponse:
        """Invoke only the first capable configured candidate for a request."""
        candidate = self.resolve(request.route, request.required_capabilities)[0]
        return await self.invoke(candidate, request)

    async def stream(
        self, candidate: ModelCandidate, request: ModelRequest
    ) -> AsyncIterator[ModelStreamEvent]:
        """Stream one selected candidate without retry or automatic fallback."""
        if not request.stream:
            raise ModelGatewayError(
                ModelErrorCategory.BAD_REQUEST,
                "ModelGateway.stream() requires a streaming request",
                provider=candidate.provider,
                model=candidate.model,
            )
        adapter = self._adapter(candidate)
        self._validate_request(candidate, adapter, request)
        async for event in adapter.stream(candidate, request):
            yield event

    async def aclose(self) -> None:
        """Close provider clients without making a health or network call."""
        for adapter in self._adapters.values():
            close = getattr(adapter, "aclose", None)
            if close is not None:
                await close()

    def _adapter(self, candidate: ModelCandidate) -> ProviderAdapter:
        try:
            return self._adapters[candidate.provider]
        except KeyError as exc:
            raise ModelConfigurationError(f"Unknown model provider: {candidate.provider}") from exc

    @staticmethod
    def _validate_request(
        candidate: ModelCandidate,
        adapter: ProviderAdapter,
        request: ModelRequest,
    ) -> None:
        required = request.required_capabilities
        supported = candidate.capabilities & adapter.capabilities
        missing = required - supported
        if missing:
            names = ", ".join(sorted(missing))
            raise ModelGatewayError(
                ModelErrorCategory.UNSUPPORTED_CAPABILITY,
                f"Candidate does not support required capabilities: {names}",
                provider=candidate.provider,
                model=candidate.model,
            )

    def _validate_route(self, route: ModelRoute) -> None:
        if not route.name.strip():
            raise ModelConfigurationError("Model route name cannot be empty")
        if not route.candidates:
            raise ModelConfigurationError(f"Model route {route.name!r} has no candidates")
        for candidate in route.candidates:
            adapter = self._adapter(candidate)
            if not candidate.model.strip():
                raise ModelConfigurationError(f"Model route {route.name!r} has an empty model name")
            if candidate.timeout_seconds <= 0:
                raise ModelConfigurationError(f"Model route {route.name!r} has an invalid timeout")
            if ModelCapability.CHAT not in candidate.capabilities:
                raise ModelConfigurationError(
                    f"Model route {route.name!r} candidate lacks chat capability"
                )
            unsupported = candidate.capabilities - adapter.capabilities
            if unsupported:
                names = ", ".join(sorted(unsupported))
                raise ModelConfigurationError(
                    f"Model route {route.name!r} declares unsupported capabilities: {names}"
                )
