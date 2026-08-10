"""Deterministic in-memory sandbox implementation of every business port."""

from decimal import Decimal

from app.adapters.contracts import (
    AccountDTO,
    AdapterContext,
    CartDTO,
    CartItemDTO,
    InventoryDTO,
    InvoiceDTO,
    LogisticsDTO,
    NotificationCommand,
    OrderDTO,
    PaymentDTO,
    ProductDTO,
    ProductQuery,
    RefundDTO,
)


class SandboxBusinessAdapter:
    """Seeded adapter used for demos without PostgreSQL or upstream APIs."""

    def __init__(self) -> None:
        self.products = [
            ProductDTO(
                product_id="sandbox-product-1",
                sku="SANDBOX-001",
                name="星仓智能耳机",
                description="用于 Sandbox 演示的降噪耳机",
                price=Decimal("399.00"),
                category="数码",
                in_stock=True,
                available_quantity=20,
            )
        ]
        self.orders: dict[tuple[str, int], OrderDTO] = {}
        self.carts: dict[tuple[str, int], CartDTO] = {}
        self.refunds: dict[tuple[str, int], list[RefundDTO]] = {}
        self.notifications: dict[str, NotificationCommand] = {}

    async def get_account(self, context: AdapterContext) -> AccountDTO | None:
        return AccountDTO(
            user_id=context.user_id,
            username=f"sandbox_{context.user_id}",
            email=f"sandbox_{context.user_id}@example.com",
            full_name="Sandbox User",
        )

    async def search(self, query: ProductQuery, context: AdapterContext) -> list[ProductDTO]:
        del context
        needle = query.query.lower()
        return [
            product
            for product in self.products
            if needle in product.name.lower() or needle in product.sku.lower()
        ][: query.limit]

    async def get_inventory(self, sku: str, context: AdapterContext) -> InventoryDTO | None:
        del context
        product = next((item for item in self.products if item.sku == sku), None)
        if product is None:
            return None
        return InventoryDTO(
            sku=sku,
            available_quantity=product.available_quantity or 0,
            warehouse="sandbox",
        )

    async def get_order(self, order_sn: str | None, context: AdapterContext) -> OrderDTO | None:
        order = self.orders.get((context.tenant_id, context.user_id))
        if order_sn and order and order.order_sn != order_sn:
            return None
        return order

    async def get_payment(self, order_sn: str, context: AdapterContext) -> PaymentDTO | None:
        order = await self.get_order(order_sn, context)
        return (
            PaymentDTO(order_sn=order_sn, status="已支付", amount=order.total_amount)
            if order
            else None
        )

    async def get_invoice(self, order_sn: str, context: AdapterContext) -> InvoiceDTO | None:
        order = await self.get_order(order_sn, context)
        return InvoiceDTO(order_sn=order_sn, status="已开票") if order else None

    async def get_tracking(self, order_sn: str, context: AdapterContext) -> LogisticsDTO | None:
        order = await self.get_order(order_sn, context)
        return (
            LogisticsDTO(order_sn=order_sn, status="运输中", carrier="Sandbox Express")
            if order
            else None
        )

    async def get_cart(self, context: AdapterContext) -> CartDTO:
        return self.carts.setdefault(
            (context.tenant_id, context.user_id), CartDTO(user_id=context.user_id)
        )

    async def add_item(self, item: CartItemDTO, context: AdapterContext) -> CartDTO:
        cart = await self.get_cart(context)
        cart.items.append(item)
        return self._total(cart)

    async def remove_item(self, item_key: str, context: AdapterContext) -> CartDTO:
        cart = await self.get_cart(context)
        cart.items = [
            item for item in cart.items if item.sku != item_key and item.product_id != item_key
        ]
        return self._total(cart)

    async def update_quantity(
        self, item_key: str, quantity: int, context: AdapterContext
    ) -> CartDTO:
        cart = await self.get_cart(context)
        for item in cart.items:
            if item.sku == item_key or item.product_id == item_key:
                item.quantity = quantity
                item.subtotal = item.price * quantity
        return self._total(cart)

    async def list_refunds(
        self, order_id: int | str | None, context: AdapterContext
    ) -> list[RefundDTO]:
        refunds = self.refunds.get((context.tenant_id, context.user_id), [])
        return [item for item in refunds if order_id is None or item.order_id == order_id]

    async def send(self, command: NotificationCommand, context: AdapterContext) -> str:
        del context
        self.notifications.setdefault(command.idempotency_key, command)
        return command.idempotency_key

    @staticmethod
    def _total(cart: CartDTO) -> CartDTO:
        cart.total = sum((item.subtotal for item in cart.items), Decimal("0"))
        return cart
