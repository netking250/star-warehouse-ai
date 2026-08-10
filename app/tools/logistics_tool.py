"""Logistics tool backed exclusively by the logistics port."""

from app.adapters.context import current_adapter_context
from app.adapters.errors import AdapterError
from app.adapters.local import LocalLogisticsAdapter, LocalOrderAdapter
from app.adapters.ports import LogisticsPort
from app.models.state import AgentState
from app.tools.base import BaseTool, ToolResult


class LogisticsTool(BaseTool):
    name = "logistics"
    description = "查询订单物流状态"

    def __init__(self, logistics_port: LogisticsPort | None = None) -> None:
        self._logistics = logistics_port

    async def execute(self, state: AgentState, session=None, **kwargs) -> ToolResult:
        """Query user-owned tracking data through the configured adapter."""
        slots = state.get("slots") or {}
        order_sn = slots.get("order_sn") or kwargs.get("order_sn")
        user_id = state.get("user_id")
        if user_id is None or not order_sn:
            return ToolResult(output={"status": "未找到订单"})
        port = self._logistics or LocalLogisticsAdapter(LocalOrderAdapter(session))
        try:
            tracking = await port.get_tracking(str(order_sn), current_adapter_context(user_id))
        except AdapterError:
            return ToolResult(output={"status": "物流服务暂时不可用，请稍后重试"})
        return ToolResult(
            output=tracking.model_dump(mode="json") if tracking else {"status": "未找到订单"}
        )
