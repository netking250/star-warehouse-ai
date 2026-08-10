"""Tests for the order Agent/service adapter boundary."""

from decimal import Decimal

import pytest

from app.adapters.contracts import AdapterContext, OrderDTO
from app.adapters.errors import AdapterError, AdapterErrorCode
from app.adapters.mock import MockBusinessAdapter
from app.agents.order import OrderAgent
from app.services.order_service import OrderService
from tests._llm import DeterministicChatModel


@pytest.mark.asyncio
async def test_order_service_reads_from_port_without_database_session() -> None:
    adapter = MockBusinessAdapter()
    context = AdapterContext(tenant_id="default", user_id=5)
    adapter.orders[(context.tenant_id, context.user_id)] = OrderDTO(
        order_id=10,
        order_sn="SN-PORT-1",
        user_id=5,
        status="已支付",
        total_amount=Decimal("88.00"),
    )
    service = OrderService(order_port=adapter)

    order = await service.get_order_for_user("SN-PORT-1", 5)

    assert order is not None
    assert order["order_sn"] == "SN-PORT-1"
    assert adapter.calls[0][0] == "get_order"


@pytest.mark.asyncio
async def test_order_agent_degrades_safely_when_upstream_is_unavailable() -> None:
    adapter = MockBusinessAdapter()
    adapter.failures["get_order"] = AdapterError(
        AdapterErrorCode.UNAVAILABLE,
        "internal upstream detail",
        service="oms",
        retryable=True,
    )
    agent = OrderAgent(
        order_service=OrderService(order_port=adapter),
        llm=DeterministicChatModel(),
    )

    result = await agent._handle_order_query("查询订单 SN-1", user_id=5)

    assert result["response"] == "订单服务暂时不可用，请稍后重试。"
    assert "internal upstream detail" not in result["response"]
