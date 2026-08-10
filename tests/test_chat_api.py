import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessageChunk
from langgraph.graph import END, START, StateGraph

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.main import app
from app.models.state import AgentState
from app.models.user import User

EXPECTED_AGENT_STATE_KEYS = set(AgentState.__annotations__.keys())


@pytest.fixture(autouse=True)
def _mock_observability_enqueue(monkeypatch):
    """Keep chat API tests isolated from the external Celery broker."""
    enqueue = MagicMock()
    monkeypatch.setattr("app.api.v1.chat.log_chat_observability.apply_async", enqueue)
    return enqueue


def _build_answer_graph(answer: str, received_state: dict):
    def _node(state: AgentState):
        received_state.update(state)
        return {"answer": answer}

    workflow = StateGraph(AgentState)  # type: ignore
    workflow.add_node(
        "policy_agent",
        _node,
        metadata={"tags": ["policy_agent", "user_visible"]},
    )
    workflow.add_edge(START, "policy_agent")
    workflow.add_edge("policy_agent", END)
    return workflow.compile()


def _build_metadata_graph(received_state: dict):
    def _node(state: AgentState):
        received_state.update(state)
        return {
            "confidence_score": 0.85,
            "confidence_signals": {"rag": {"score": 0.9}},
            "needs_human_transfer": False,
            "transfer_reason": None,
            "audit_level": "auto",
        }

    workflow = StateGraph(AgentState)  # type: ignore
    workflow.add_node(
        "decider_node",
        _node,
        metadata={"tags": ["decider_node", "internal"]},
    )
    workflow.add_edge(START, "decider_node")
    workflow.add_edge("decider_node", END)
    return workflow.compile()


def _build_error_graph(exception: BaseException, received_state: dict):
    def _node(state: AgentState):
        received_state.update(state)
        raise exception

    workflow = StateGraph(AgentState)  # type: ignore
    workflow.add_node(
        "policy_agent",
        _node,
        metadata={"tags": ["policy_agent", "user_visible"]},
    )
    workflow.add_edge(START, "policy_agent")
    workflow.add_edge("policy_agent", END)
    return workflow.compile()


def _build_slow_graph(delay_seconds: float):
    async def _node(state: AgentState):
        await asyncio.sleep(delay_seconds)
        return {"answer": "不应到达的答案"}

    workflow = StateGraph(AgentState)  # type: ignore
    workflow.add_node(
        "policy_agent",
        _node,
        metadata={"tags": ["policy_agent", "user_visible"]},
    )
    workflow.add_edge(START, "policy_agent")
    workflow.add_edge("policy_agent", END)
    return workflow.compile()


class _StreamingGraph:
    def __init__(self, *, delay_after_token: float = 0.0) -> None:
        self.delay_after_token = delay_after_token
        self.configs = []

    async def astream_events(self, _state, config, *, version):
        self.configs.append(config)
        yield {
            "event": "on_chat_model_stream",
            "metadata": {"langgraph_node": "policy_agent", "tags": ["user_visible"]},
            "tags": ["user_visible"],
            "data": {"chunk": AIMessageChunk(content="唯一答案")},
        }
        if self.delay_after_token:
            await asyncio.sleep(self.delay_after_token)
        yield {
            "event": "on_chain_end",
            "run_id": "policy-run",
            "metadata": {"langgraph_node": "policy_agent"},
            "data": {"output": {"answer": "唯一答案"}},
        }


@pytest_asyncio.fixture(scope="session")
async def auth_token():
    unique = uuid.uuid4().hex[:8]
    username = f"chat_user_{unique}"
    password = "password123"

    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password(password),
            email=f"{username}@test.com",
            full_name="Chat Test",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        token = create_access_token(user_id=user.id, is_admin=False)

    yield token


@pytest.mark.asyncio
async def test_chat_normal_streaming(client, auth_token):
    """正常流式响应：包含 answer 和 [DONE]"""

    received_state = {}
    compiled = _build_answer_graph("这是最终答案", received_state)

    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = compiled
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试问题", "thread_id": "thread-1"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.status_code == 200
    text = response.text
    assert "data: " in text
    assert "[DONE]" in text
    assert json.dumps({"token": "这是最终答案"}, ensure_ascii=False) in text
    assert set(received_state.keys()) == EXPECTED_AGENT_STATE_KEYS


@pytest.mark.asyncio
async def test_chat_metadata_streaming(client, auth_token):
    """置信度元数据在 [DONE] 前发送"""

    received_state = {}
    compiled = _build_metadata_graph(received_state)

    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = compiled
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-2"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.status_code == 200
    text = response.text
    assert '"type": "metadata"' in text
    assert '"confidence_score": 0.85' in text
    assert '"confidence_level": "high"' in text
    assert "[DONE]" in text
    metadata_pos = text.find('"type": "metadata"')
    done_pos = text.find("[DONE]")
    assert metadata_pos != -1
    assert done_pos != -1
    assert metadata_pos < done_pos
    assert set(received_state.keys()) == EXPECTED_AGENT_STATE_KEYS


@pytest.mark.asyncio
async def test_chat_503_when_app_graph_none(client, auth_token):
    """app_graph 为 None 时返回 503"""
    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = None
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-3"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.status_code == 503
    assert "not fully initialized" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_connection_reset_handled_as_disconnect(client, auth_token):
    """astream_events 抛出 ConnectionResetError 时视为客户端断开，返回空流"""

    received_state = {}
    compiled = _build_error_graph(ConnectionResetError("boom"), received_state)

    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = compiled
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-4"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.status_code == 200
    assert response.text == ""
    assert set(received_state.keys()) == EXPECTED_AGENT_STATE_KEYS


@pytest.mark.asyncio
async def test_chat_cancelled_error_propagates(client, auth_token):
    """astream_events 中节点抛出 CancelledError 时，LangGraph 内部处理并正常结束流"""

    received_state = {}
    compiled = _build_error_graph(asyncio.CancelledError(), received_state)

    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = compiled
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-5"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.status_code == 200
    assert "[DONE]" in response.text
    assert set(received_state.keys()) == EXPECTED_AGENT_STATE_KEYS


@pytest.mark.asyncio
async def test_chat_generic_error_handled(client, auth_token):
    """astream_events 抛出未捕获通用异常时，SSE 流应返回错误消息并正常结束"""

    received_state = {}
    compiled = _build_error_graph(RuntimeError("模拟内部错误"), received_state)

    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = compiled
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-6"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.status_code == 200
    text = response.text
    assert '"error"' in text
    assert "[DONE]" in text
    assert set(received_state.keys()) == EXPECTED_AGENT_STATE_KEYS


@pytest.mark.asyncio
async def test_chat_type_error_returns_terminal_sse_error(client, auth_token):
    """Checkpoint incompatibilities must terminate the SSE stream cleanly."""
    received_state = {}
    compiled = _build_error_graph(TypeError("incompatible checkpoint versions"), received_state)

    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = compiled
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试", "thread_id": "thread-type-error"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.status_code == 200
    assert '"error"' in response.text
    assert "[DONE]" in response.text


@pytest.mark.asyncio
async def test_chat_global_timeout_terminates_slow_stream(client, auth_token, monkeypatch):
    """The chat endpoint must enforce its configured end-to-end timeout."""
    monkeypatch.setattr("app.api.v1.chat.settings.CHAT_STREAM_TIMEOUT_SECONDS", 0.01)
    compiled = _build_slow_graph(delay_seconds=0.2)

    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = compiled
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试超时", "thread_id": "thread-timeout"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.status_code == 200
    assert "服务响应超时" in response.text
    assert "[DONE]" in response.text


@pytest.mark.asyncio
async def test_chat_does_not_repeat_streamed_answer_at_chain_end(client, auth_token):
    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = _StreamingGraph()
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试去重", "thread_id": "thread-deduplicate"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original

    assert response.text.count(json.dumps({"token": "唯一答案"}, ensure_ascii=False)) == 1
    assert "[DONE]" in response.text


@pytest.mark.asyncio
async def test_chat_timeout_after_answer_closes_without_error(client, auth_token, monkeypatch):
    monkeypatch.setattr("app.api.v1.chat.settings.CHAT_STREAM_TIMEOUT_SECONDS", 0.01)
    original = getattr(app.state, "app_graph", None)
    original_checkpointer = getattr(app.state, "checkpointer", None)
    checkpointer = AsyncMock()
    app.state.app_graph = _StreamingGraph(delay_after_token=0.2)
    app.state.checkpointer = checkpointer
    try:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "测试答案后超时", "thread_id": "thread-post-answer-timeout"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    finally:
        app.state.app_graph = original
        app.state.checkpointer = original_checkpointer

    assert json.dumps({"token": "唯一答案"}, ensure_ascii=False) in response.text
    assert '"error"' not in response.text
    assert "[DONE]" in response.text
    checkpointer.aprune.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_isolates_checkpoint_namespace_per_request(client, auth_token):
    graph = _StreamingGraph()
    original = getattr(app.state, "app_graph", None)
    app.state.app_graph = graph
    try:
        for question in ("第一问", "第二问"):
            response = await client.post(
                "/api/v1/chat",
                json={"question": question, "thread_id": "same-thread"},
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            assert response.status_code == 200
    finally:
        app.state.app_graph = original

    namespaces = [config["configurable"]["checkpoint_ns"] for config in graph.configs]
    assert len(namespaces) == 2
    assert namespaces[0] != namespaces[1]
    assert all(namespace.startswith("v3.1:") for namespace in namespaces)
