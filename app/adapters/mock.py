"""Programmable mock adapter for service and Agent tests."""

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
from app.adapters.sandbox import SandboxBusinessAdapter


class MockBusinessAdapter(SandboxBusinessAdapter):
    """Sandbox adapter with call recording and injectable failures."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.failures: dict[str, Exception] = {}

    def _record(self, operation: str, *args: object) -> None:
        self.calls.append((operation, args))
        failure = self.failures.get(operation)
        if failure is not None:
            raise failure

    async def get_account(self, context: AdapterContext) -> AccountDTO | None:
        self._record("get_account", context)
        return await super().get_account(context)

    async def search(self, query: ProductQuery, context: AdapterContext) -> list[ProductDTO]:
        self._record("search", query, context)
        return await super().search(query, context)

    async def get_inventory(self, sku: str, context: AdapterContext) -> InventoryDTO | None:
        self._record("get_inventory", sku, context)
        return await super().get_inventory(sku, context)

    async def get_order(self, order_sn: str | None, context: AdapterContext) -> OrderDTO | None:
        self._record("get_order", order_sn, context)
        return await super().get_order(order_sn, context)

    async def get_payment(self, order_sn: str, context: AdapterContext) -> PaymentDTO | None:
        self._record("get_payment", order_sn, context)
        return await super().get_payment(order_sn, context)

    async def get_invoice(self, order_sn: str, context: AdapterContext) -> InvoiceDTO | None:
        self._record("get_invoice", order_sn, context)
        return await super().get_invoice(order_sn, context)

    async def get_tracking(self, order_sn: str, context: AdapterContext) -> LogisticsDTO | None:
        self._record("get_tracking", order_sn, context)
        return await super().get_tracking(order_sn, context)

    async def get_cart(self, context: AdapterContext) -> CartDTO:
        self._record("get_cart", context)
        return await super().get_cart(context)

    async def add_item(self, item: CartItemDTO, context: AdapterContext) -> CartDTO:
        self._record("add_item", item, context)
        return await super().add_item(item, context)

    async def remove_item(self, item_key: str, context: AdapterContext) -> CartDTO:
        self._record("remove_item", item_key, context)
        return await super().remove_item(item_key, context)

    async def update_quantity(
        self, item_key: str, quantity: int, context: AdapterContext
    ) -> CartDTO:
        self._record("update_quantity", item_key, quantity, context)
        return await super().update_quantity(item_key, quantity, context)

    async def list_refunds(
        self, order_id: int | str | None, context: AdapterContext
    ) -> list[RefundDTO]:
        self._record("list_refunds", order_id, context)
        return await super().list_refunds(order_id, context)

    async def send(self, command: NotificationCommand, context: AdapterContext) -> str:
        self._record("send", command, context)
        return await super().send(command, context)
