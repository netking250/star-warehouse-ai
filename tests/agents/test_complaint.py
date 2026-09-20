from unittest.mock import AsyncMock, patch

import pytest

from app.agents.complaint import ComplaintAgent
from app.models.state import make_agent_state
from tests._llm import DeterministicChatModel


@pytest.fixture
def agent(deterministic_llm):
    return ComplaintAgent(llm=deterministic_llm)


@pytest.mark.asyncio
async def test_complaint_agent_creates_ticket(agent):
    llm_response = (
        '{"category": "product_defect", "urgency": "high", '
        '"summary": "商品有瑕疵", "expected_resolution": "refund", '
        '"empathetic_response": "非常抱歉，已为您创建工单 {ticket_id}"}'
    )
    agent.llm = DeterministicChatModel(responses=[(["投诉"], llm_response)])

    with (
        patch(
            "app.agents.config_loader.get_effective_system_prompt", new=AsyncMock(return_value=None)
        ),
        patch.object(
            agent._tool,
            "create_ticket",
            new=AsyncMock(return_value={"created": True, "ticket_id": 42}),
        ),
    ):
        state = make_agent_state(
            question="我要投诉商品有瑕疵",
            intent_result={"primary_intent": "COMPLAINT", "secondary_intent": "QUERY"},
        )
        result = await agent.process(state)

    assert "42" in result["response"]
    assert "非常抱歉" in result["response"]
    assert result["updated_state"]["answer"] == result["response"]


@pytest.mark.asyncio
async def test_complaint_agent_ticket_creation_fails(agent):
    llm_response = (
        '{"category": "service", "urgency": "medium", '
        '"summary": "服务态度差", "expected_resolution": "apology", '
        '"empathetic_response": "已记录您的问题 {ticket_id}"}'
    )
    agent.llm = DeterministicChatModel(responses=[(["态度"], llm_response)])

    with (
        patch(
            "app.agents.config_loader.get_effective_system_prompt", new=AsyncMock(return_value=None)
        ),
        patch.object(agent._tool, "create_ticket", side_effect=RuntimeError("DB down")),
    ):
        state = make_agent_state(
            question="我要投诉客服态度太差了",
            intent_result={"primary_intent": "COMPLAINT", "secondary_intent": "QUERY"},
        )
        result = await agent.process(state)

    assert "投诉请求未能提交" in result["response"]
    assert "联系您" not in result["response"]


@pytest.mark.asyncio
async def test_complaint_agent_parses_markdown_json(agent):
    llm_response = (
        "```json\n"
        '{"category": "logistics", "urgency": "high", '
        '"summary": "物流太慢", "expected_resolution": "compensation", '
        '"empathetic_response": "工单 {ticket_id} 已创建"}'
        "\n```"
    )
    agent.llm = DeterministicChatModel(responses=[(["海外"], llm_response)])

    with (
        patch(
            "app.agents.config_loader.get_effective_system_prompt", new=AsyncMock(return_value=None)
        ),
        patch.object(
            agent._tool,
            "create_ticket",
            new=AsyncMock(return_value={"created": True, "ticket_id": 7}),
        ),
    ):
        state = make_agent_state(
            question="我要投诉海外订单无法追踪",
            intent_result={"primary_intent": "COMPLAINT", "secondary_intent": "APPLY"},
        )
        result = await agent.process(state)

    assert "7" in result["response"]
    assert "已创建" in result["response"]


@pytest.mark.asyncio
async def test_complaint_agent_parse_fallback(agent):
    agent.llm = DeterministicChatModel(responses=[(["无法"], "不是有效JSON")])

    with (
        patch(
            "app.agents.config_loader.get_effective_system_prompt", new=AsyncMock(return_value=None)
        ),
        patch.object(
            agent._tool,
            "create_ticket",
            new=AsyncMock(return_value={"created": True, "ticket_id": 1}),
        ),
    ):
        state = make_agent_state(
            question="我要投诉无法使用购买的优惠券",
            intent_result={"primary_intent": "COMPLAINT", "secondary_intent": "APPLY"},
        )
        result = await agent.process(state)

    assert "#1" in result["response"]
    assert "已记录并提交处理" in result["response"]
    assert "不是有效JSON" not in result["response"]


@pytest.fixture
def real_complaint_agent(real_llm):
    return ComplaintAgent(llm=real_llm)


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_complaint_agent(real_complaint_agent):
    with (
        patch(
            "app.agents.config_loader.get_effective_system_prompt", new=AsyncMock(return_value=None)
        ),
        patch.object(
            real_complaint_agent._tool,
            "create_ticket",
            new=AsyncMock(return_value={"created": True, "ticket_id": 42}),
        ),
    ):
        state = make_agent_state(
            question="我要投诉商品有瑕疵",
            intent_result={"primary_intent": "COMPLAINT", "secondary_intent": "APPLY"},
        )
        result = await real_complaint_agent.process(state)
        assert isinstance(result["response"], str)
        assert len(result["response"]) > 0


@pytest.mark.parametrize(
    "question",
    [
        "If the Aurora Chair has a verified defect, who pays the return shipping?",
        "不是产品坏了，就是我自己不喜欢，退的话运费谁出？",
        "Aurora Chair有质量问题，退货运费谁出？",
    ],
)
@pytest.mark.asyncio
async def test_complaint_agent_does_not_create_ticket_for_policy_consultation(agent, question):
    with (
        patch(
            "app.agents.config_loader.get_effective_system_prompt", new=AsyncMock(return_value=None)
        ),
        patch.object(
            agent._tool,
            "create_ticket",
            new=AsyncMock(return_value={"created": True, "ticket_id": 99}),
        ) as create_ticket,
    ):
        state = make_agent_state(
            question=question,
            intent_result={"primary_intent": "COMPLAINT", "secondary_intent": "QUERY"},
        )
        result = await agent.process(state)

    create_ticket.assert_not_awaited()
    assert "未创建投诉工单" in result["response"]
    assert "99" not in result["response"]


@pytest.mark.asyncio
async def test_complaint_agent_reports_only_confirmed_ticket_facts(agent):
    with (
        patch(
            "app.agents.config_loader.get_effective_system_prompt", new=AsyncMock(return_value=None)
        ),
        patch.object(
            agent._tool,
            "create_ticket",
            new=AsyncMock(return_value={"created": True, "ticket_id": 73, "status": "open"}),
        ),
    ):
        state = make_agent_state(
            question="我收到的商品有质量问题，我想投诉并转人工客服。",
            intent_result={"primary_intent": "COMPLAINT", "secondary_intent": "APPLY"},
        )
        result = await agent.process(state)

    response = result["response"]
    assert "73" in response
    assert "open" in response
    assert "24小时" not in response
    assert "退款" not in response
    assert "换货" not in response
    assert "赔偿" not in response
    assert "联系您" not in response
