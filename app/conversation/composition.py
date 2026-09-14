"""Application composition for the durable conversation runtime."""

from collections.abc import AsyncIterator
from typing import Any

from app.conversation.contracts import ExecutionRequest, ExecutorEvent
from app.conversation.langgraph_executor import LangGraphConversationExecutor
from app.conversation.runtime import ConversationRuntime
from app.core.database import async_session_maker


class _UnavailableExecutor:
    async def execute(self, request: ExecutionRequest) -> AsyncIterator[ExecutorEvent]:
        raise RuntimeError("Conversation executor is unavailable")
        yield


def build_conversation_runtime(application_state: Any) -> ConversationRuntime:
    """Build a runtime that always supports durable read/control operations."""
    graph = getattr(application_state, "app_graph", None)
    return ConversationRuntime(
        session_factory=async_session_maker,
        executor=(
            LangGraphConversationExecutor(graph) if graph is not None else _UnavailableExecutor()
        ),
    )


def conversation_executor_is_available(application_state: Any) -> bool:
    """Return whether this process can start new graph execution."""
    return getattr(application_state, "app_graph", None) is not None
