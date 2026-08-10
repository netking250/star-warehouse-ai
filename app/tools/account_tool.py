"""Account tool backed exclusively by the identity port."""

from app.adapters.context import current_adapter_context
from app.adapters.errors import AdapterError
from app.adapters.local import LocalIdentityAdapter
from app.adapters.ports import IdentityPort
from app.models.state import AgentState
from app.tools.base import BaseTool, ToolResult

_MEMBERSHIP_LEVELS = ["普通会员", "银卡", "金卡", "钻石"]


class AccountTool(BaseTool):
    """Query customer account information through an identity adapter."""

    name = "account"
    description = "查询用户账户信息、会员等级、优惠券"

    def __init__(self, identity_port: IdentityPort | None = None) -> None:
        self._identity = identity_port

    async def execute(self, state: AgentState, session=None, **kwargs) -> ToolResult:
        """Return the trusted account projection for the current user."""
        del kwargs
        user_id = state.get("user_id")
        if user_id is None:
            return ToolResult(output={"error": "无法识别用户身份，请重新登录。"})
        port = self._identity or LocalIdentityAdapter(session)
        try:
            account = await port.get_account(current_adapter_context(user_id))
        except AdapterError:
            return ToolResult(output={"error": "账户服务暂时不可用，请稍后重试。"})
        if account is None:
            return ToolResult(output={"error": f"未找到用户 ID {user_id} 的账户信息。"})
        output = account.model_dump(mode="json")
        output["account_balance"] = float(account.account_balance)
        return ToolResult(output=output, source="account_tool")
