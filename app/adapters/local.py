"""Local development adapters backed by PostgreSQL, Redis, and Qdrant."""

import logging
import uuid
from contextlib import nullcontext
from datetime import datetime
from decimal import Decimal
from typing import Any

import redis.asyncio as aioredis
from qdrant_client import AsyncQdrantClient, models
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

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
from app.adapters.errors import AdapterError, AdapterErrorCode
from app.core.config import settings
from app.core.database import async_session_maker
from app.core.tenancy import namespaced_collection, namespaced_key
from app.models.order import Order, OrderStatus
from app.models.refund import RefundApplication
from app.models.user import User

logger = logging.getLogger(__name__)
_MEMBERSHIP_LEVELS = ["普通会员", "银卡", "金卡", "钻石"]


def _status_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _order_dto(order: Order) -> OrderDTO:
    if order.id is None:
        raise ValueError("Persisted order is missing its ID")
    return OrderDTO(
        order_id=order.id,
        order_sn=order.order_sn,
        user_id=order.user_id,
        status=_status_value(order.status),
        total_amount=order.total_amount,
        items=order.items,
        tracking_number=order.tracking_number,
        created_at=order.created_at,
    )


class LocalIdentityAdapter:
    """Read customer accounts from the local development database."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def get_account(self, context: AdapterContext) -> AccountDTO | None:
        session_cm = (
            nullcontext(self._session) if self._session is not None else async_session_maker()
        )
        async with session_cm as session:
            result = await session.exec(select(User).where(User.id == context.user_id))
            user = result.one_or_none()
        if user is None or user.id is None:
            return None
        year = datetime.now().year + 1
        coupons = [{"name": "满100减10", "expiry": f"{year}-12-31"}]
        if user.id % 2 == 0:
            coupons.append({"name": "免运费券", "expiry": f"{year}-11-30"})
        return AccountDTO(
            user_id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            membership_level=_MEMBERSHIP_LEVELS[user.id % len(_MEMBERSHIP_LEVELS)],
            account_balance=Decimal("128.50") + Decimal(user.id) * Decimal("10.25"),
            coupons=coupons,
        )


class LocalOrderAdapter:
    """Read user-owned orders from the local development database."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def get_order(self, order_sn: str | None, context: AdapterContext) -> OrderDTO | None:
        stmt = select(Order).where(Order.user_id == context.user_id)
        if order_sn:
            stmt = stmt.where(Order.order_sn == order_sn.strip().upper())
        else:
            stmt = stmt.order_by(desc(Order.created_at)).limit(1)
        session_cm = (
            nullcontext(self._session) if self._session is not None else async_session_maker()
        )
        async with session_cm as session:
            result = await session.exec(stmt)
            order = result.first()
        return _order_dto(order) if order else None


class LocalPaymentAdapter:
    """Project payment state from local order state."""

    def __init__(self, order_port: LocalOrderAdapter) -> None:
        self._orders = order_port

    async def get_payment(self, order_sn: str, context: AdapterContext) -> PaymentDTO | None:
        order = await self._orders.get_order(order_sn, context)
        if order is None:
            return None
        paid = order.status in {
            OrderStatus.PAID.value,
            OrderStatus.SHIPPED.value,
            OrderStatus.DELIVERED.value,
        }
        return PaymentDTO(
            order_sn=order.order_sn,
            status="已支付" if paid else order.status,
            amount=order.total_amount,
        )


class LocalInvoiceAdapter:
    """Project invoice state for local development orders."""

    def __init__(self, order_port: LocalOrderAdapter) -> None:
        self._orders = order_port

    async def get_invoice(self, order_sn: str, context: AdapterContext) -> InvoiceDTO | None:
        order = await self._orders.get_order(order_sn, context)
        return InvoiceDTO(order_sn=order_sn, status="已开票") if order else None


class LocalLogisticsAdapter:
    """Project logistics data from local orders."""

    def __init__(self, order_port: LocalOrderAdapter) -> None:
        self._orders = order_port

    async def get_tracking(self, order_sn: str, context: AdapterContext) -> LogisticsDTO | None:
        order = await self._orders.get_order(order_sn, context)
        if order is None:
            return None
        return LogisticsDTO(
            order_sn=order.order_sn,
            tracking_number=order.tracking_number or "暂无",
            carrier="顺丰速运",
            status="运输中",
            latest_update="快件已到达【北京顺义集散中心】",
            estimated_delivery="2024-01-20",
        )


class LocalRefundAdapter:
    """Read refund projections from the local database."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def list_refunds(
        self, order_id: int | str | None, context: AdapterContext
    ) -> list[RefundDTO]:
        stmt = select(RefundApplication).where(RefundApplication.user_id == context.user_id)
        if isinstance(order_id, int):
            stmt = stmt.where(RefundApplication.order_id == order_id)
        session_cm = (
            nullcontext(self._session) if self._session is not None else async_session_maker()
        )
        async with session_cm as session:
            result = await session.exec(stmt)
            refunds = list(result.all())
        return [
            RefundDTO(
                refund_id=refund.id or 0,
                order_id=refund.order_id,
                amount=refund.refund_amount,
                status=_status_value(refund.status),
                created_at=refund.created_at,
            )
            for refund in refunds
        ]


class RedisCartAdapter:
    """Low-risk cart adapter backed by tenant-scoped Redis."""

    def __init__(self, redis: aioredis.Redis, *, key_prefix: str = "") -> None:
        self._redis = redis
        self._key_prefix = key_prefix

    def _key(self, context: AdapterContext) -> str:
        return f"{self._key_prefix}{namespaced_key(f'cart:{context.user_id}', context.tenant_id)}"

    async def get_cart(self, context: AdapterContext) -> CartDTO:
        data = await self._redis.get(self._key(context))
        return CartDTO.model_validate_json(data) if data else CartDTO(user_id=context.user_id)

    async def add_item(self, item: CartItemDTO, context: AdapterContext) -> CartDTO:
        cart = await self.get_cart(context)
        cart.items.append(item)
        return await self._save(cart, context)

    async def remove_item(self, item_key: str, context: AdapterContext) -> CartDTO:
        cart = await self.get_cart(context)
        cart.items = [
            item for item in cart.items if item.sku != item_key and item.product_id != item_key
        ]
        return await self._save(cart, context)

    async def update_quantity(
        self, item_key: str, quantity: int, context: AdapterContext
    ) -> CartDTO:
        cart = await self.get_cart(context)
        for item in cart.items:
            if item.sku == item_key or item.product_id == item_key:
                item.quantity = quantity
                item.subtotal = item.price * quantity
                return await self._save(cart, context)
        return cart

    async def _save(self, cart: CartDTO, context: AdapterContext) -> CartDTO:
        cart.total = sum((item.subtotal for item in cart.items), Decimal("0"))
        await self._redis.setex(self._key(context), 86400, cart.model_dump_json())
        return cart


class QdrantProductAdapter:
    """Product catalog adapter backed by tenant-filtered Qdrant search."""

    def __init__(
        self,
        *,
        client: AsyncQdrantClient | None = None,
        embedder: Any | None = None,
        rewriter: Any | None = None,
        collection_name: str | None = None,
    ) -> None:
        self._client = client
        self._embedder = embedder
        self._rewriter = rewriter
        self.collection_name = collection_name or namespaced_collection("product_catalog")

    async def search(self, query: ProductQuery, context: AdapterContext) -> list[ProductDTO]:
        client = await self._get_client()
        if not await client.collection_exists(self.collection_name):
            raise AdapterError(
                AdapterErrorCode.NOT_FOUND,
                "商品目录尚未初始化",
                service="product_catalog",
            )
        text = query.query
        if self._rewriter is not None:
            text = await self._rewriter.rewrite(
                text,
                conversation_history=query.conversation_history,
            )
        conditions: list[Any] = [
            models.FieldCondition(key="tenant_id", match=models.MatchValue(value=context.tenant_id))
        ]
        if query.category is not None:
            conditions.append(
                models.FieldCondition(key="category", match=models.MatchValue(value=query.category))
            )
        if query.in_stock is not None:
            conditions.append(
                models.FieldCondition(key="in_stock", match=models.MatchValue(value=query.in_stock))
            )
        if query.min_price is not None or query.max_price is not None:
            conditions.append(
                models.FieldCondition(
                    key="price",
                    range=models.Range(
                        gte=float(query.min_price) if query.min_price is not None else None,
                        lte=float(query.max_price) if query.max_price is not None else None,
                    ),
                )
            )
        response = await client.query_points(
            collection_name=self.collection_name,
            query=await self._embed(text),
            using="dense",
            limit=query.limit,
            with_payload=True,
            with_vectors=False,
            query_filter=models.Filter(must=conditions),
        )
        products: list[ProductDTO] = []
        for point in response.points:
            payload = point.payload or {}
            products.append(
                ProductDTO(
                    product_id=str(point.id),
                    sku=str(payload.get("sku", "")),
                    name=str(payload.get("name", "")),
                    description=str(payload.get("description", "")),
                    price=payload.get("price"),
                    category=str(payload.get("category", "")),
                    in_stock=bool(payload.get("in_stock", False)),
                    available_quantity=payload.get("available_quantity"),
                    attributes=payload.get("attributes", {}),
                    score=point.score,
                )
            )
        return products

    async def _get_client(self) -> AsyncQdrantClient:
        if self._client is None:
            self._client = AsyncQdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY.get_secret_value() or None,
                timeout=settings.QDRANT_TIMEOUT,
            )
        return self._client

    async def aclose(self) -> None:
        """Close the lazily created Qdrant client owned by this adapter."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def _embed(self, text: str) -> list[float]:
        if self._embedder is not None:
            return await self._embedder.aembed_query(text)
        from app.retrieval.embeddings import create_embedding_model

        return await create_embedding_model().aembed_query(text)


class LocalInventoryAdapter:
    """Inventory projection over the local product catalog."""

    def __init__(self, products: QdrantProductAdapter) -> None:
        self._products = products

    async def get_inventory(self, sku: str, context: AdapterContext) -> InventoryDTO | None:
        results = await self._products.search(ProductQuery(query=sku, limit=10), context)
        product = next((item for item in results if item.sku == sku), None)
        if product is None:
            return None
        quantity = product.available_quantity if product.available_quantity is not None else 0
        return InventoryDTO(sku=sku, available_quantity=quantity)


class LoggingNotificationAdapter:
    """Safe local notification adapter that emits an auditable message ID."""

    async def send(self, command: NotificationCommand, context: AdapterContext) -> str:
        message_id = str(uuid.uuid5(uuid.NAMESPACE_URL, command.idempotency_key))
        logger.info(
            "notification_dispatched tenant=%s user=%s channel=%s message_id=%s",
            context.tenant_id,
            context.user_id,
            command.channel,
            message_id,
        )
        return message_id
