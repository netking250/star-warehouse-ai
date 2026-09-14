"""Provider-neutral contracts for model routing and invocation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType


class ModelCapability(StrEnum):
    """Capabilities that application model routes may require."""

    CHAT = "chat"
    STREAMING = "streaming"
    TOOLS = "tools"
    STRUCTURED_OUTPUT = "structured_output"


@dataclass(frozen=True, slots=True)
class ModelMessage:
    """One provider-neutral chat message."""

    role: str
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[ModelToolCall, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelTool:
    """Provider-neutral function tool definition."""

    name: str
    input_schema: Mapping[str, object]
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ModelToolChoice:
    """Provider-neutral tool selection instruction."""

    mode: str
    name: str | None = None


@dataclass(frozen=True, slots=True)
class ModelToolCall:
    """Normalized completed model tool call."""

    id: str
    name: str
    arguments: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class StructuredOutput:
    """Provider-neutral JSON-schema response request."""

    name: str
    schema: Mapping[str, object]
    strict: bool = True


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """A bounded provider-neutral model request."""

    route: str
    messages: tuple[ModelMessage, ...]
    stream: bool = False
    temperature: float | None = None
    max_output_tokens: int | None = None
    timeout_seconds: float | None = None
    tools: tuple[ModelTool, ...] = ()
    tool_choice: ModelToolChoice | None = None
    structured_output: StructuredOutput | None = None
    runtime_context: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        """Reject locally knowable request errors before provider I/O."""
        if not self.route.strip():
            raise ValueError("Model route cannot be blank")
        if not self.messages:
            raise ValueError("Model request requires at least one message")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("Model request timeout must be positive")
        if self.max_output_tokens is not None and self.max_output_tokens <= 0:
            raise ValueError("Model max output tokens must be positive")

    @property
    def required_capabilities(self) -> frozenset[ModelCapability]:
        """Return capabilities required without silently weakening semantics."""
        capabilities = {ModelCapability.CHAT}
        if self.stream:
            capabilities.add(ModelCapability.STREAMING)
        if self.tools:
            capabilities.add(ModelCapability.TOOLS)
        if self.structured_output is not None:
            capabilities.add(ModelCapability.STRUCTURED_OUTPUT)
        return frozenset(capabilities)


@dataclass(frozen=True, slots=True)
class ModelUsage:
    """Token usage reported by a provider without fabricated values."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """Normalized result of one selected provider candidate."""

    content: str
    finish_reason: str | None
    provider: str
    model: str
    usage: ModelUsage | None = None
    provider_request_id: str | None = None
    latency_ms: int | None = None
    tool_calls: tuple[ModelToolCall, ...] = ()
    structured_output: Mapping[str, object] | None = None


class ModelStreamEventType(StrEnum):
    """Kinds of provider-neutral streaming output."""

    TEXT_DELTA = "text_delta"
    TOOL_CALL_DELTA = "tool_call_delta"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class ModelToolCallDelta:
    """One partial tool call emitted by a streaming provider."""

    index: int
    id: str | None = None
    name: str | None = None
    arguments_delta: str = ""


@dataclass(frozen=True, slots=True)
class ModelStreamEvent:
    """A provider-neutral streaming delta or terminal metadata event."""

    event_type: ModelStreamEventType
    provider: str
    model: str
    text_delta: str = ""
    tool_call_delta: ModelToolCallDelta | None = None
    finish_reason: str | None = None
    usage: ModelUsage | None = None
    provider_request_id: str | None = None
    latency_ms: int | None = None


@dataclass(frozen=True, slots=True)
class ModelCandidate:
    """One explicitly selectable provider/model combination."""

    provider: str
    model: str
    capabilities: frozenset[ModelCapability]
    timeout_seconds: float


@dataclass(frozen=True, slots=True)
class ModelRoute:
    """Ordered candidates for one application use case."""

    name: str
    candidates: tuple[ModelCandidate, ...]
