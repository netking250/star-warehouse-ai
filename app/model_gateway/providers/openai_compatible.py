"""OpenAI-compatible provider implementation shared by real adapters."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Mapping
from typing import cast
from urllib.parse import urlsplit

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    OpenAIError,
    RateLimitError,
)
from openai.types.chat import (
    ChatCompletionMessageFunctionToolCall,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCallUnion,
)
from openai.types.chat.completion_create_params import (
    CompletionCreateParamsNonStreaming,
    CompletionCreateParamsStreaming,
)

from app.model_gateway.contracts import (
    ModelCandidate,
    ModelCapability,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelToolCall,
    ModelToolCallDelta,
    ModelUsage,
)
from app.model_gateway.errors import ModelErrorCategory, ModelGatewayError


class OpenAICompatibleProviderAdapter:
    """Perform one bounded OpenAI-compatible chat-completions attempt."""

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
        provider_name: str,
        client: AsyncOpenAI | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        default_timeout_seconds: float = 30.0,
    ) -> None:
        if default_timeout_seconds <= 0:
            raise ValueError("Provider timeout must be positive")
        if base_url is not None:
            parsed_url = urlsplit(base_url)
            if (
                parsed_url.scheme not in {"http", "https"}
                or not parsed_url.hostname
                or parsed_url.username is not None
                or parsed_url.password is not None
                or parsed_url.query
                or parsed_url.fragment
            ):
                raise ValueError("Provider base URL must be a trusted HTTP(S) origin/path")
        self._provider_name = provider_name
        self._client = client
        self._api_key = api_key
        self._base_url = base_url
        self._default_timeout_seconds = default_timeout_seconds

    @property
    def name(self) -> str:
        """Return the stable configured provider identity."""
        return self._provider_name

    async def invoke(self, candidate: ModelCandidate, request: ModelRequest) -> ModelResponse:
        """Translate and normalize one non-streaming provider call."""
        client = self._get_client(candidate)
        params = self._non_streaming_params(candidate, request)
        started = time.perf_counter()
        try:
            async with asyncio.timeout(self._timeout(candidate, request)):
                response = await client.chat.completions.create(**params)
        except asyncio.CancelledError:
            raise
        except TimeoutError as exc:
            raise self._error(
                ModelErrorCategory.TIMEOUT, candidate, "Provider call timed out"
            ) from exc
        except OpenAIError as exc:
            raise self._normalize_sdk_error(exc, candidate) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        if not response.choices:
            raise self._error(
                ModelErrorCategory.INVALID_RESPONSE,
                candidate,
                "Provider response did not contain a choice",
                request_id=response.id,
            )
        choice = response.choices[0]
        tool_calls = self._normalize_tool_calls(choice.message.tool_calls, candidate, response.id)
        content = choice.message.content or ""
        if not content and not tool_calls:
            raise self._error(
                ModelErrorCategory.INVALID_RESPONSE,
                candidate,
                "Provider response contained neither text nor tool calls",
                request_id=response.id,
            )
        structured_output = self._parse_structured_output(content, request, candidate, response.id)
        return ModelResponse(
            content=content,
            finish_reason=choice.finish_reason,
            provider=self.name,
            model=response.model or candidate.model,
            usage=self._usage(response.usage),
            provider_request_id=response.id,
            latency_ms=latency_ms,
            tool_calls=tool_calls,
            structured_output=structured_output,
        )

    async def stream(
        self, candidate: ModelCandidate, request: ModelRequest
    ) -> AsyncIterator[ModelStreamEvent]:
        """Translate provider chunks into stable text/tool/terminal events."""
        client = self._get_client(candidate)
        params = self._streaming_params(candidate, request)
        started = time.perf_counter()
        finish_reason: str | None = None
        usage: ModelUsage | None = None
        request_id: str | None = None
        actual_model = candidate.model
        try:
            async with asyncio.timeout(self._timeout(candidate, request)):
                stream = await client.chat.completions.create(**params)
                async for chunk in stream:
                    request_id = chunk.id or request_id
                    actual_model = chunk.model or actual_model
                    usage = self._usage(chunk.usage) or usage
                    for choice in chunk.choices:
                        finish_reason = choice.finish_reason or finish_reason
                        if choice.delta.content:
                            yield ModelStreamEvent(
                                event_type=ModelStreamEventType.TEXT_DELTA,
                                provider=self.name,
                                model=actual_model,
                                text_delta=choice.delta.content,
                                provider_request_id=request_id,
                            )
                        for tool_delta in choice.delta.tool_calls or []:
                            function = tool_delta.function
                            yield ModelStreamEvent(
                                event_type=ModelStreamEventType.TOOL_CALL_DELTA,
                                provider=self.name,
                                model=actual_model,
                                tool_call_delta=ModelToolCallDelta(
                                    index=tool_delta.index,
                                    id=tool_delta.id,
                                    name=function.name if function is not None else None,
                                    arguments_delta=(
                                        function.arguments
                                        if function is not None and function.arguments is not None
                                        else ""
                                    ),
                                ),
                                provider_request_id=request_id,
                            )
        except asyncio.CancelledError:
            raise
        except TimeoutError as exc:
            raise self._error(
                ModelErrorCategory.TIMEOUT, candidate, "Provider stream timed out"
            ) from exc
        except OpenAIError as exc:
            raise self._normalize_sdk_error(exc, candidate) from exc

        yield ModelStreamEvent(
            event_type=ModelStreamEventType.COMPLETED,
            provider=self.name,
            model=actual_model,
            finish_reason=finish_reason,
            usage=usage,
            provider_request_id=request_id,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    async def aclose(self) -> None:
        """Close the lazily created or injected provider client."""
        if self._client is not None:
            await self._client.close()

    def _get_client(self, candidate: ModelCandidate) -> AsyncOpenAI:
        if self._client is not None:
            return self._client
        if not self._api_key or not self._base_url:
            raise self._error(
                ModelErrorCategory.AUTHENTICATION,
                candidate,
                "Provider credentials are not configured",
            )
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._default_timeout_seconds,
            max_retries=0,
        )
        return self._client

    def _non_streaming_params(
        self, candidate: ModelCandidate, request: ModelRequest
    ) -> CompletionCreateParamsNonStreaming:
        params: dict[str, object] = self._base_params(candidate, request)
        return cast(CompletionCreateParamsNonStreaming, params)

    def _streaming_params(
        self, candidate: ModelCandidate, request: ModelRequest
    ) -> CompletionCreateParamsStreaming:
        params: dict[str, object] = self._base_params(candidate, request)
        params["stream"] = True
        params["stream_options"] = {"include_usage": True}
        return cast(CompletionCreateParamsStreaming, params)

    def _base_params(self, candidate: ModelCandidate, request: ModelRequest) -> dict[str, object]:
        params: dict[str, object] = {
            "model": candidate.model,
            "messages": self._messages(request.messages),
        }
        if request.temperature is not None:
            params["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            params["max_tokens"] = request.max_output_tokens
        if request.tools:
            params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": dict(tool.input_schema),
                    },
                }
                for tool in request.tools
            ]
        if request.tool_choice is not None:
            params["tool_choice"] = self._tool_choice(
                request.tool_choice.mode, request.tool_choice.name
            )
        if request.structured_output is not None:
            params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.structured_output.name,
                    "schema": dict(request.structured_output.schema),
                    "strict": request.structured_output.strict,
                },
            }
        return params

    @staticmethod
    def _messages(messages: tuple[ModelMessage, ...]) -> list[ChatCompletionMessageParam]:
        result: list[ChatCompletionMessageParam] = []
        for message in messages:
            payload: dict[str, object] = {"role": message.role, "content": message.content}
            if message.name is not None:
                payload["name"] = message.name
            if message.tool_call_id is not None:
                payload["tool_call_id"] = message.tool_call_id
            if message.tool_calls:
                payload["tool_calls"] = [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": json.dumps(tool_call.arguments),
                        },
                    }
                    for tool_call in message.tool_calls
                ]
            result.append(cast(ChatCompletionMessageParam, payload))
        return result

    @staticmethod
    def _tool_choice(mode: str, name: str | None) -> object:
        if name is not None:
            return {"type": "function", "function": {"name": name}}
        if mode == "any":
            return "required"
        return mode

    def _normalize_tool_calls(
        self,
        raw_tool_calls: list[ChatCompletionMessageToolCallUnion] | None,
        candidate: ModelCandidate,
        request_id: str | None,
    ) -> tuple[ModelToolCall, ...]:
        if not raw_tool_calls:
            return ()
        normalized: list[ModelToolCall] = []
        for tool_call in raw_tool_calls:
            if not isinstance(tool_call, ChatCompletionMessageFunctionToolCall):
                raise self._error(
                    ModelErrorCategory.INVALID_RESPONSE,
                    candidate,
                    "Provider returned an unsupported tool-call type",
                    request_id=request_id,
                )
            try:
                arguments = json.loads(tool_call.function.arguments)
            except (json.JSONDecodeError, TypeError) as exc:
                raise self._error(
                    ModelErrorCategory.INVALID_RESPONSE,
                    candidate,
                    "Provider returned invalid tool arguments",
                    request_id=request_id,
                ) from exc
            if not isinstance(arguments, dict):
                raise self._error(
                    ModelErrorCategory.INVALID_RESPONSE,
                    candidate,
                    "Provider returned non-object tool arguments",
                    request_id=request_id,
                )
            normalized.append(
                ModelToolCall(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=arguments,
                )
            )
        return tuple(normalized)

    def _parse_structured_output(
        self,
        content: str,
        request: ModelRequest,
        candidate: ModelCandidate,
        request_id: str | None,
    ) -> Mapping[str, object] | None:
        if request.structured_output is None:
            return None
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise self._error(
                ModelErrorCategory.INVALID_RESPONSE,
                candidate,
                "Provider returned invalid structured JSON",
                request_id=request_id,
            ) from exc
        if not isinstance(parsed, dict):
            raise self._error(
                ModelErrorCategory.INVALID_RESPONSE,
                candidate,
                "Provider structured output was not an object",
                request_id=request_id,
            )
        return parsed

    @staticmethod
    def _usage(raw_usage: object) -> ModelUsage | None:
        if raw_usage is None:
            return None
        return ModelUsage(
            input_tokens=getattr(raw_usage, "prompt_tokens", None),
            output_tokens=getattr(raw_usage, "completion_tokens", None),
            total_tokens=getattr(raw_usage, "total_tokens", None),
        )

    def _normalize_sdk_error(
        self, error: OpenAIError, candidate: ModelCandidate
    ) -> ModelGatewayError:
        if isinstance(error, AuthenticationError):
            category = ModelErrorCategory.AUTHENTICATION
        elif isinstance(error, RateLimitError):
            category = ModelErrorCategory.RATE_LIMIT
        elif isinstance(error, APITimeoutError):
            category = ModelErrorCategory.TIMEOUT
        elif isinstance(error, APIConnectionError):
            category = ModelErrorCategory.CONNECTION
        elif isinstance(error, BadRequestError):
            category = ModelErrorCategory.BAD_REQUEST
        elif isinstance(error, InternalServerError) or (
            isinstance(error, APIStatusError) and error.status_code >= 500
        ):
            category = ModelErrorCategory.PROVIDER_UNAVAILABLE
        else:
            category = ModelErrorCategory.UNKNOWN
        request_id = getattr(error, "request_id", None)
        return self._error(category, candidate, "Provider request failed", request_id=request_id)

    def _error(
        self,
        category: ModelErrorCategory,
        candidate: ModelCandidate,
        message: str,
        *,
        request_id: str | None = None,
    ) -> ModelGatewayError:
        return ModelGatewayError(
            category,
            message,
            provider=self.name,
            model=candidate.model,
            provider_request_id=request_id,
        )

    @staticmethod
    def _timeout(candidate: ModelCandidate, request: ModelRequest) -> float:
        return request.timeout_seconds or candidate.timeout_seconds
