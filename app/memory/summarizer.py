import json
import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.tracing import build_llm_config
from app.memory.consistency import build_memory_vector_task_context
from app.memory.structured_manager import StructuredMemoryManager
from app.model_gateway.factory import create_model_client
from app.models.memory import InteractionSummary
from app.models.state import AgentState

logger = logging.getLogger(__name__)


class SessionSummarizer:
    """Summarizes conversation threads and persists interaction summaries."""

    def __init__(self, llm: BaseChatModel | None = None):
        self.llm = llm or create_model_client("summarization")
        self.memory_manager = StructuredMemoryManager()

    def should_summarize(
        self,
        state: AgentState,
        utilization: float | None = None,
        threshold: float | None = None,
    ) -> bool:
        """Return True if the conversation should be summarized.

        Summarize threads that either exceed 20 messages, exceed the
        configured compaction token-utilization threshold, or naturally end
        (no human transfer, not awaiting clarification, and at least one exchange).

        Args:
            state: The current agent state.
            utilization: Optional token utilization ratio (0.0-1.0). If provided
                and exceeds the threshold, summarization is triggered.
            threshold: Optional threshold to override ``settings.COMPACTION_THRESHOLD``.
        """
        history = state.get("history", [])
        if len(history) > 20:
            return True
        effective_threshold = (
            threshold if threshold is not None else getattr(settings, "COMPACTION_THRESHOLD", 0.75)
        )
        if utilization is not None and utilization > effective_threshold:
            return True
        needs_human = state.get("needs_human_transfer")
        awaiting = state.get("awaiting_clarification")
        return not needs_human and not awaiting and len(history) >= 2

    async def summarize_thread(self, messages: list[dict]) -> str:
        """Ask the LLM to summarize a conversation thread."""
        system_prompt = (
            "You are a helpful assistant. Summarize the following conversation thread "
            "in 2-3 concise sentences, capturing the key topics and outcomes."
        )
        user_prompt = (
            f"Conversation messages:\n{json.dumps(messages, ensure_ascii=False, indent=2)}"
        )
        llm_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        config = build_llm_config(
            agent_name="session_summarizer",
            tags=["internal", "memory_summarization"],
        )
        response = await self.llm.ainvoke(llm_messages, config=config)
        summary = str(response.content).strip()
        logger.info("Generated conversation summary (length=%d)", len(summary))
        return summary

    async def run(
        self,
        state: AgentState,
        session: AsyncSession,
        utilization: float | None = None,
        threshold: float | None = None,
    ) -> InteractionSummary | None:
        """Summarize and persist if conditions are met."""
        if not self.should_summarize(state, utilization=utilization, threshold=threshold):
            return None

        history = state.get("history", [])
        if not history:
            logger.debug("No history to summarize.")
            return None

        user_id = state.get("user_id")
        thread_id = state.get("thread_id")
        tenant_id = state.get("tenant_id")
        correlation_id = state.get("correlation_id")
        resolved_intent = state.get("current_intent")

        if user_id is None or thread_id is None or tenant_id is None or correlation_id is None:
            logger.warning("Missing explicit memory command context; cannot persist summary.")
            return None

        existing = await session.exec(
            select(InteractionSummary).where(
                InteractionSummary.thread_id == thread_id,
                col(InteractionSummary.is_deleted).is_(False),
            )
        )
        if existing.one_or_none():
            logger.info("Summary already exists for thread_id=%s; skipping.", thread_id)
            return None

        summary_text = await self.summarize_thread(history)

        task_context = build_memory_vector_task_context(
            tenant_id=tenant_id,
            user_id=user_id,
            thread_id=thread_id,
            correlation_id=correlation_id,
            trace_id=state.get("trace_id"),
            operation_id=f"summary:{thread_id}:v1:upsert",
        )
        try:
            record = await self.memory_manager.save_interaction_summary(
                session=session,
                task_context=task_context,
                user_id=user_id,
                thread_id=thread_id,
                summary=summary_text,
                resolved_intent=resolved_intent,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        logger.info(
            "Committed interaction summary and vector intent for memory_id=%s thread_id=%s",
            record.id,
            thread_id,
        )

        return record
