"""Cart tool backed exclusively by the cart port."""

from decimal import Decimal

import redis.asyncio as aioredis

from app.adapters.context import current_adapter_context
from app.adapters.contracts import CartDTO, CartItemDTO
from app.adapters.errors import AdapterError
from app.adapters.local import RedisCartAdapter
from app.adapters.ports import CartPort
from app.core.config import settings
from app.models.state import AgentState
from app.tools.base import BaseTool, ToolResult


class CartTool(BaseTool):
    name = "cart"
    description = "购物车增删查改操作"

    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        key_prefix: str = "",
        cart_port: CartPort | None = None,
    ) -> None:
        self._redis = redis_client
        self._key_prefix = key_prefix
        self._cart = cart_port

    async def _port(self) -> CartPort:
        if self._cart is not None:
            return self._cart
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        self._cart = RedisCartAdapter(self._redis, key_prefix=self._key_prefix)
        return self._cart

    async def execute(self, state: AgentState, **kwargs) -> ToolResult:
        """Execute a low-risk cart command through the configured adapter."""
        slots = state.get("slots") or {}
        user_id = state.get("user_id")
        if user_id is None:
            return ToolResult(output={"status": "error", "reason": "无法识别用户身份"})
        action = str(slots.get("action") or kwargs.get("action") or "QUERY").upper()
        product_id = slots.get("product_id") or kwargs.get("product_id")
        sku = slots.get("sku") or kwargs.get("sku")
        item_key = sku or product_id
        quantity = int(slots.get("quantity", 1) or kwargs.get("quantity", 1))
        name = slots.get("product_name") or kwargs.get("product_name") or item_key
        price = Decimal(str(slots.get("price", 0) or kwargs.get("price", 0)))
        context = current_adapter_context(user_id)
        port = await self._port()

        try:
            return await self._execute_action(
                port=port,
                context=context,
                action=action,
                item_key=item_key,
                product_id=product_id,
                sku=sku,
                quantity=quantity,
                name=name,
                price=price,
                slots=slots,
                kwargs=kwargs,
            )
        except AdapterError:
            return ToolResult(
                output={"status": "error", "reason": "购物车服务暂时不可用，请稍后重试"}
            )

    async def _execute_action(
        self,
        *,
        port: CartPort,
        context,
        action: str,
        item_key,
        product_id,
        sku,
        quantity: int,
        name,
        price: Decimal,
        slots: dict,
        kwargs: dict,
    ) -> ToolResult:
        """Dispatch a validated cart action to the port."""
        if action == "QUERY":
            return ToolResult(
                output={"action": action, **self._output(await port.get_cart(context))}
            )
        if not item_key:
            return ToolResult(
                output={"status": "error", "reason": "缺少商品标识（sku 或 product_id）"}
            )
        if action == "ADD":
            cart = await port.add_item(
                CartItemDTO(
                    product_id=product_id,
                    sku=sku,
                    name=str(name),
                    quantity=quantity,
                    price=price,
                    subtotal=price * quantity,
                ),
                context,
            )
            return ToolResult(
                output={"action": action, "name": name, "quantity": quantity, **self._output(cart)}
            )
        if action not in {"REMOVE", "MODIFY"}:
            return ToolResult(output={"status": "error", "reason": f"不支持的操作: {action}"})
        current = await port.get_cart(context)
        matched_item = next(
            (
                item
                for item in current.items
                if item.sku == str(item_key) or item.product_id == str(item_key)
            ),
            None,
        )
        if matched_item is None:
            return ToolResult(output={"status": "error", "reason": "购物车中未找到该商品"})
        resolved_name = slots.get("product_name") or kwargs.get("product_name") or matched_item.name
        if action == "REMOVE":
            cart = await port.remove_item(str(item_key), context)
            return ToolResult(
                output={"action": action, "name": resolved_name, **self._output(cart)}
            )
        if action == "MODIFY":
            cart = await port.update_quantity(str(item_key), quantity, context)
            return ToolResult(
                output={
                    "action": action,
                    "name": resolved_name,
                    "quantity": quantity,
                    **self._output(cart),
                }
            )
        return ToolResult(output={"status": "error", "reason": f"不支持的操作: {action}"})

    @staticmethod
    def _output(cart: CartDTO) -> dict:
        data = cart.model_dump(mode="json")
        data["total"] = float(cart.total)
        for index, item in enumerate(cart.items):
            data["items"][index]["price"] = float(item.price)
            data["items"][index]["subtotal"] = float(item.subtotal)
        return data
