"""Protocol definitions for authoritative business systems."""

from typing import Protocol

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


class IdentityPort(Protocol):
    async def get_account(self, context: AdapterContext) -> AccountDTO | None: ...


class ProductPort(Protocol):
    async def search(self, query: ProductQuery, context: AdapterContext) -> list[ProductDTO]: ...


class InventoryPort(Protocol):
    async def get_inventory(self, sku: str, context: AdapterContext) -> InventoryDTO | None: ...


class OrderPort(Protocol):
    async def get_order(self, order_sn: str | None, context: AdapterContext) -> OrderDTO | None: ...


class PaymentPort(Protocol):
    async def get_payment(self, order_sn: str, context: AdapterContext) -> PaymentDTO | None: ...


class InvoicePort(Protocol):
    async def get_invoice(self, order_sn: str, context: AdapterContext) -> InvoiceDTO | None: ...


class LogisticsPort(Protocol):
    async def get_tracking(self, order_sn: str, context: AdapterContext) -> LogisticsDTO | None: ...


class CartPort(Protocol):
    async def get_cart(self, context: AdapterContext) -> CartDTO: ...

    async def add_item(self, item: CartItemDTO, context: AdapterContext) -> CartDTO: ...

    async def remove_item(self, item_key: str, context: AdapterContext) -> CartDTO: ...

    async def update_quantity(
        self, item_key: str, quantity: int, context: AdapterContext
    ) -> CartDTO: ...


class RefundPort(Protocol):
    async def list_refunds(
        self, order_id: int | str | None, context: AdapterContext
    ) -> list[RefundDTO]: ...


class NotificationPort(Protocol):
    async def send(self, command: NotificationCommand, context: AdapterContext) -> str: ...
