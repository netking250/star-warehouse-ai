"""LangChain-compatible client backed by the provider-neutral model gateway."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from typing import Any, cast

from langchain_core.exceptions import LangChainException
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    UsageMetadata,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ConfigDict, Field

from app.model_gateway.contracts import (
    ModelCandidate,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelStreamEventType,
    ModelTool,
    ModelToolCall,
    ModelToolChoice,
)
from app.model_gateway.errors import ModelGatewayError
from app.model_gateway.failure_policy import ModelFailurePolicy
from app.model_gateway.gateway import ModelGateway


class GatewayChatModelError(LangChainException):
    """Expose a safe LangChain error while retaining normalized gateway diagnostics."""

    def __init__(self, gateway_error: ModelGatewayError) -> None:
        super().__init__(str(gateway_error))
        self.gateway_error = gateway_error


class GatewayChatModel(BaseChatModel):
    """Preserve existing LangGraph interfaces while routing through ModelGateway."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    gateway: ModelGateway = Field(exclude=True)
    route: str
    candidate: ModelCandidate | None = None
    temperature: float | None = 0.0
    timeout_seconds: float | None = None
    max_output_tokens: int | None = None
    failure_policy: ModelFailurePolicy = Field(default_factory=ModelFailurePolicy, exclude=True)

    @property
    def _llm_type(self) -> str:
        return "model_gateway"

    @property
    def _identifying_params(self) -> dict[str, object]:
        candidate = self.candidate
        return {
            "route": self.route,
            "provider": candidate.provider if candidate is not None else "route_primary",
            "model": candidate.model if candidate is not None else "route_primary",
        }

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        """Bind provider-neutral tools for existing LangChain structured/tool callers."""
        if kwargs:
            unsupported = set(kwargs) - {
                "strict",
                "parallel_tool_calls",
                "ls_structured_output_format",
            }
            if unsupported:
                raise ValueError(f"Unsupported model tool arguments: {sorted(unsupported)}")
        normalized = tuple(self._model_tool(tool) for tool in tools)
        return self.bind(
            tools=normalized,
            tool_choice=self._model_tool_choice(tool_choice),
        )

    async def ainvoke(
        self,
        input: LanguageModelInput,
        config: RunnableConfig | None = None,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> AIMessage:
        """Execute non-streaming generation even under streaming event callbacks."""
        kwargs["stream"] = False
        return await super().ainvoke(input, config=config, stop=stop, **kwargs)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: object = None,
        **kwargs: object,
    ) -> ChatResult:
        raise RuntimeError("GatewayChatModel is async-only; use ainvoke")

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: object = None,
        **kwargs: object,
    ) -> ChatResult:
        request = self._request(messages, stream=False, kwargs=kwargs)
        try:
            response = await self.failure_policy.invoke(
                self.gateway,
                request,
                candidates=(self.candidate,) if self.candidate is not None else None,
            )
        except ModelGatewayError as exc:
            raise GatewayChatModelError(exc) from exc
        message = self._message(response)
        return ChatResult(generations=[ChatGeneration(message=message, text=response.content)])

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: object = None,
        **kwargs: object,
    ) -> AsyncIterator[ChatGenerationChunk]:
        request = self._request(messages, stream=True, kwargs=kwargs)
        try:
            async for event in self.failure_policy.stream(
                self.gateway,
                request,
                candidates=(self.candidate,) if self.candidate is not None else None,
            ):
                if event.event_type is ModelStreamEventType.TEXT_DELTA:
                    yield ChatGenerationChunk(
                        message=AIMessageChunk(
                            content=event.text_delta,
                            response_metadata={
                                "provider": event.provider,
                                "model": event.model,
                                "degraded": event.degraded,
                            },
                        )
                    )
                elif (
                    event.event_type is ModelStreamEventType.TOOL_CALL_DELTA
                    and event.tool_call_delta is not None
                ):
                    delta = event.tool_call_delta
                    yield ChatGenerationChunk(
                        message=AIMessageChunk(
                            content="",
                            tool_call_chunks=[
                                {
                                    "name": delta.name,
                                    "args": delta.arguments_delta,
                                    "id": delta.id,
                                    "index": delta.index,
                                    "type": "tool_call_chunk",
                                }
                            ],
                        )
                    )
                else:
                    yield ChatGenerationChunk(
                        message=AIMessageChunk(
                            content="",
                            response_metadata={
                                "provider": event.provider,
                                "model": event.model,
                                "finish_reason": event.finish_reason,
                                "provider_request_id": event.provider_request_id,
                                "latency_ms": event.latency_ms,
                                "degraded": event.degraded,
                            },
                            usage_metadata=self._usage_metadata(event.usage),
                        )
                    )
        except ModelGatewayError as exc:
            raise GatewayChatModelError(exc) from exc

    def _request(
        self,
        messages: list[BaseMessage],
        *,
        stream: bool,
        kwargs: Mapping[str, object],
    ) -> ModelRequest:
        raw_temperature = kwargs.get("temperature", self.temperature)
        raw_max_output_tokens = kwargs.get(
            "max_output_tokens", kwargs.get("max_tokens", self.max_output_tokens)
        )
        raw_timeout_seconds = kwargs.get("timeout", self.timeout_seconds)
        tools = kwargs.get("tools", ())
        tool_choice = kwargs.get("tool_choice")
        temperature = (
            float(raw_temperature) if isinstance(raw_temperature, (int, float, str)) else None
        )
        max_output_tokens = (
            int(raw_max_output_tokens)
            if isinstance(raw_max_output_tokens, (int, float, str))
            else None
        )
        timeout_seconds = (
            float(raw_timeout_seconds)
            if isinstance(raw_timeout_seconds, (int, float, str))
            else None
        )
        return ModelRequest(
            route=self.route,
            messages=tuple(self._model_message(message) for message in messages),
            stream=stream,
            tools=cast(tuple[ModelTool, ...], tools),
            tool_choice=cast(ModelToolChoice | None, tool_choice),
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
        )

    @staticmethod
    def _model_message(message: BaseMessage) -> ModelMessage:
        role = "user"
        tool_call_id: str | None = None
        tool_calls: tuple[ModelToolCall, ...] = ()
        if isinstance(message, SystemMessage):
            role = "system"
        elif isinstance(message, AIMessage):
            role = "assistant"
            tool_calls = tuple(
                ModelToolCall(
                    id=str(tool_call.get("id") or ""),
                    name=str(tool_call.get("name") or ""),
                    arguments=cast(dict[str, object], tool_call.get("args") or {}),
                )
                for tool_call in message.tool_calls
            )
        elif isinstance(message, ToolMessage):
            role = "tool"
            tool_call_id = message.tool_call_id
        elif not isinstance(message, HumanMessage):
            role = str(message.type)
        return ModelMessage(
            role=role,
            content=GatewayChatModel._content_text(message.content),
            name=getattr(message, "name", None),
            tool_call_id=tool_call_id,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _content_text(content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    mapping = cast(dict[str, object], block)
                    if mapping.get("type") == "text":
                        parts.append(str(mapping.get("text", "")))
            return "".join(parts)
        return str(content)

    @staticmethod
    def _model_tool(tool: dict[str, Any] | type | Callable | BaseTool) -> ModelTool:
        converted = convert_to_openai_tool(tool)
        function = cast(dict[str, object], converted["function"])
        parameters = function.get("parameters", {"type": "object"})
        return ModelTool(
            name=str(function["name"]),
            description=str(function.get("description") or ""),
            input_schema=cast(dict[str, object], parameters),
        )

    @staticmethod
    def _model_tool_choice(tool_choice: object) -> ModelToolChoice | None:
        if tool_choice is None:
            return None
        if isinstance(tool_choice, str):
            if tool_choice in {"auto", "none", "required", "any"}:
                return ModelToolChoice(mode=tool_choice)
            return ModelToolChoice(mode="required", name=tool_choice)
        if isinstance(tool_choice, dict):
            choice_mapping = cast(dict[str, object], tool_choice)
            function = choice_mapping.get("function")
            if isinstance(function, dict):
                function_mapping = cast(dict[str, object], function)
                if function_mapping.get("name"):
                    return ModelToolChoice(mode="required", name=str(function_mapping["name"]))
        raise ValueError("Unsupported provider-specific tool choice")

    @staticmethod
    def _message(response: ModelResponse) -> AIMessage:
        return AIMessage(
            content=response.content,
            tool_calls=[
                {
                    "name": tool_call.name,
                    "args": dict(tool_call.arguments),
                    "id": tool_call.id,
                    "type": "tool_call",
                }
                for tool_call in response.tool_calls
            ],
            response_metadata={
                "provider": response.provider,
                "model": response.model,
                "finish_reason": response.finish_reason,
                "provider_request_id": response.provider_request_id,
                "latency_ms": response.latency_ms,
                "degraded": response.degraded,
            },
            usage_metadata=GatewayChatModel._usage_metadata(response.usage),
        )

    @staticmethod
    def _usage_metadata(usage: object) -> UsageMetadata | None:
        if usage is None:
            return None
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)
        if input_tokens is None or output_tokens is None or total_tokens is None:
            return None
        return UsageMetadata(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
