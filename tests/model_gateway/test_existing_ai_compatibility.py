"""Representative production AI paths exercised through ModelGateway."""

from __future__ import annotations

from typing import TypedDict

import pytest
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from app.agents.base import BaseAgent
from app.graph.nodes import build_synthesis_node
from app.intent.classifier import IntentClassifier
from app.intent.models import IntentAction, IntentCategory, IntentResult
from app.intent.multi_intent import MultiIntentProcessor
from app.memory.extractor import FactExtractor
from app.memory.summarizer import SessionSummarizer
from app.model_gateway.contracts import (
    ModelCandidate,
    ModelCapability,
    ModelRoute,
    ModelToolCall,
)
from app.model_gateway.gateway import ModelGateway
from app.model_gateway.langchain import GatewayChatModel
from app.model_gateway.providers.mock import MockProviderAdapter
from app.models.state import AgentProcessResult, AgentState, make_agent_state
from app.retrieval.rewriter import QueryRewriter


class _SummaryState(TypedDict, total=False):
    question: str
    summary: str


@pytest.fixture(autouse=True)
def _disable_hosted_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep compatibility tests independent of developer tracing credentials."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")


def _client(adapter: MockProviderAdapter, route: str) -> GatewayChatModel:
    candidate = ModelCandidate(
        provider="mock",
        model=f"mock-{route}",
        capabilities=adapter.capabilities,
        timeout_seconds=1.0,
    )
    gateway = ModelGateway(
        adapters=[adapter],
        routes=[ModelRoute(name=route, candidates=(candidate,))],
    )
    return GatewayChatModel(gateway=gateway, route=route)


@pytest.mark.asyncio
async def test_intent_classifier_uses_gateway_tool_call() -> None:
    adapter = MockProviderAdapter(
        content="",
        tool_calls=(
            ModelToolCall(
                id="intent-1",
                name="classify_intent",
                arguments={
                    "primary_intent": "ORDER",
                    "secondary_intent": "QUERY",
                    "confidence": 0.95,
                    "slots": {"order_sn": "SN-1"},
                },
            ),
        ),
    )

    result = await IntentClassifier(_client(adapter, "intent")).classify("unmatched request text")

    assert result.primary_intent is IntentCategory.ORDER
    assert result.secondary_intent is IntentAction.QUERY
    assert adapter.attempt_count == 1


@pytest.mark.asyncio
async def test_multi_intent_structured_check_uses_gateway() -> None:
    adapter = MockProviderAdapter(
        content="",
        tool_calls=(
            ModelToolCall(
                id="independence-1",
                name="IndependenceCheck",
                arguments={"are_independent": True, "reason": "separate domains"},
            ),
        ),
    )
    processor = MultiIntentProcessor(
        classifier=IntentClassifier(_client(adapter, "intent")),
        llm=_client(adapter, "intent"),
    )
    intents = [
        IntentResult(
            primary_intent=IntentCategory.ORDER,
            secondary_intent=IntentAction.QUERY,
            confidence=0.9,
            slots={},
            raw_query="order",
        ),
        IntentResult(
            primary_intent=IntentCategory.POLICY,
            secondary_intent=IntentAction.CONSULT,
            confidence=0.9,
            slots={},
            raw_query="policy",
        ),
    ]

    result = await processor._llm_independence_check("order and policy", intents)

    assert result.are_independent is True
    assert result.reason == "separate domains"


@pytest.mark.asyncio
async def test_rag_rewriter_and_memory_services_use_gateway() -> None:
    rewrite_adapter = MockProviderAdapter(content="normalized query")
    rewriter = QueryRewriter(_client(rewrite_adapter, "rewrite"))
    summary_adapter = MockProviderAdapter(content="short summary")
    summarizer = SessionSummarizer(_client(summary_adapter, "summarization"))
    fact_adapter = MockProviderAdapter(
        content='[{"fact_type":"preference","content":"likes blue","confidence":0.9}]'
    )
    extractor = FactExtractor(_client(fact_adapter, "structured"))

    rewritten = await rewriter.rewrite("casual query")
    summary = await summarizer.summarize_thread([{"role": "user", "content": "hello"}])
    facts = await extractor.extract_facts(
        user_id=1,
        thread_id="thread-1",
        history=[],
        question="What color do I like?",
        answer="You like blue.",
    )

    assert rewritten == "normalized query"
    assert summary == "short summary"
    assert facts == [{"fact_type": "preference", "content": "likes blue", "confidence": 0.9}]


@pytest.mark.asyncio
async def test_summarizer_ainvoke_inside_graph_event_stream_uses_chat_only_candidate() -> None:
    adapter = MockProviderAdapter(content="short summary")
    candidate = ModelCandidate(
        provider="mock",
        model="mock-summarization-chat-only",
        capabilities=frozenset({ModelCapability.CHAT}),
        timeout_seconds=1.0,
    )
    gateway = ModelGateway(
        adapters=[adapter],
        routes=[ModelRoute(name="summarization", candidates=(candidate,))],
    )
    summarizer = SessionSummarizer(GatewayChatModel(gateway=gateway, route="summarization"))
    summaries: list[str] = []

    async def summarize_node(state: _SummaryState) -> dict[str, str]:
        summary = await summarizer.summarize_thread(
            [{"role": "user", "content": state["question"]}]
        )
        summaries.append(summary)
        return {"summary": summary}

    # LangGraph 1.0.10's bound is not recognized by ty for valid TypedDict state.
    builder = StateGraph(_SummaryState)  # ty: ignore[invalid-argument-type]
    builder.add_node("summarize", summarize_node)
    builder.add_edge(START, "summarize")
    builder.add_edge("summarize", END)
    graph = builder.compile()

    async for _event in graph.astream_events({"question": "Aurora"}, version="v2"):
        pass

    assert summaries == ["short summary"]
    assert adapter.attempt_count == 1


class _GatewayAgent(BaseAgent):
    async def process(self, state: AgentState) -> AgentProcessResult:
        metadata = self._extract_tracing_metadata(state)
        response = await self._call_llm(
            [HumanMessage(content=state["question"])],
            metadata=metadata,
        )
        return {"response": response, "updated_state": metadata}


@pytest.mark.asyncio
async def test_domain_agent_and_synthesis_publish_normalized_identity() -> None:
    agent_adapter = MockProviderAdapter(content="answer")
    agent = _GatewayAgent("compat_agent", _client(agent_adapter, "default_chat"))
    agent_result = await agent.process(make_agent_state(question="hello"))

    synthesis_adapter = MockProviderAdapter(content="merged")
    synthesis = build_synthesis_node(_client(synthesis_adapter, "default_chat"))
    synthesis_result = await synthesis(
        make_agent_state(
            question="combine",
            execution_mode="parallel",
            pending_agent_results=["order_agent", "policy_agent"],
            sub_answers=[
                {"agent": "order_agent", "response": "one", "iteration": 0},
                {"agent": "policy_agent", "response": "two", "iteration": 0},
            ],
        )
    )

    assert agent_result["response"] == "answer"
    assert agent_result["updated_state"]["model_provider"] == "mock"
    assert agent_result["updated_state"]["model_name"] == "mock-default_chat"
    synthesis_update = synthesis_result.update
    assert synthesis_update is not None
    assert synthesis_update["answer"] == "merged"
    assert synthesis_update["model_provider"] == "mock"
    assert synthesis_update["model_name"] == "mock-default_chat"
