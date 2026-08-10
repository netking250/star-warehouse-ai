"""Adapter dependency container and local-mode composition."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import redis.asyncio as aioredis

from app.adapters.http import ProductionBusinessHTTPAdapter
from app.adapters.local import (
    LocalIdentityAdapter,
    LocalInventoryAdapter,
    LocalInvoiceAdapter,
    LocalLogisticsAdapter,
    LocalOrderAdapter,
    LocalPaymentAdapter,
    LocalRefundAdapter,
    LoggingNotificationAdapter,
    QdrantProductAdapter,
    RedisCartAdapter,
)
from app.adapters.ports import (
    CartPort,
    IdentityPort,
    InventoryPort,
    InvoicePort,
    LogisticsPort,
    NotificationPort,
    OrderPort,
    PaymentPort,
    ProductPort,
    RefundPort,
)
from app.adapters.sandbox import SandboxBusinessAdapter
from app.core.config import settings


@dataclass(frozen=True, slots=True)
class AdapterContainer:
    """One immutable set of business-system dependencies."""

    identity: IdentityPort
    product: ProductPort
    inventory: InventoryPort
    order: OrderPort
    payment: PaymentPort
    invoice: InvoicePort
    logistics: LogisticsPort
    cart: CartPort
    refund: RefundPort
    notification: NotificationPort
    _closers: tuple[Callable[[], Awaitable[None]], ...] = field(
        default=(), repr=False, compare=False
    )

    async def aclose(self) -> None:
        """Close resources owned by adapter implementations."""
        for close in self._closers:
            await close()


def build_local_adapters(redis: aioredis.Redis, *, rewriter=None) -> AdapterContainer:
    """Build adapters for local development and automated integration tests."""
    orders = LocalOrderAdapter()
    products = QdrantProductAdapter(rewriter=rewriter)
    return AdapterContainer(
        identity=LocalIdentityAdapter(),
        product=products,
        inventory=LocalInventoryAdapter(products),
        order=orders,
        payment=LocalPaymentAdapter(orders),
        invoice=LocalInvoiceAdapter(orders),
        logistics=LocalLogisticsAdapter(orders),
        cart=RedisCartAdapter(redis),
        refund=LocalRefundAdapter(),
        notification=LoggingNotificationAdapter(),
        _closers=(products.aclose,),
    )


def build_adapters(redis: aioredis.Redis, *, rewriter=None) -> AdapterContainer:
    """Build the configured adapter set without exposing mode checks to Agents."""
    mode = settings.BUSINESS_ADAPTER_MODE.lower()
    if mode == "local":
        return build_local_adapters(redis, rewriter=rewriter)
    if mode == "sandbox":
        sandbox = SandboxBusinessAdapter()
        return AdapterContainer(
            identity=sandbox,
            product=sandbox,
            inventory=sandbox,
            order=sandbox,
            payment=sandbox,
            invoice=sandbox,
            logistics=sandbox,
            cart=sandbox,
            refund=sandbox,
            notification=sandbox,
        )
    if mode == "production":
        if not settings.BUSINESS_API_BASE_URL:
            raise RuntimeError("BUSINESS_API_BASE_URL is required in production adapter mode")
        production = ProductionBusinessHTTPAdapter(
            settings.BUSINESS_API_BASE_URL,
            token=settings.BUSINESS_API_TOKEN.get_secret_value(),
        )
        return AdapterContainer(
            identity=production,
            product=production,
            inventory=production,
            order=production,
            payment=production,
            invoice=production,
            logistics=production,
            cart=production,
            refund=production,
            notification=production,
        )
    raise RuntimeError(f"Unsupported BUSINESS_ADAPTER_MODE: {settings.BUSINESS_ADAPTER_MODE}")
