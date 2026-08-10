"""Canonical DTOs exchanged through business-system ports."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class AdapterContext(BaseModel):
    """Identity and trace data propagated to an upstream system."""

    tenant_id: str
    user_id: int
    correlation_id: str = "-"


class AccountDTO(BaseModel):
    """Customer account projection safe for Agent consumption."""

    user_id: int
    username: str
    email: str
    full_name: str
    phone: str | None = None
    membership_level: str = "普通会员"
    account_balance: Decimal = Decimal("0")
    coupons: list[dict[str, str]] = Field(default_factory=list)


class ProductQuery(BaseModel):
    """Normalized product search request."""

    query: str
    category: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock: bool | None = None
    limit: int = Field(default=5, ge=1, le=50)
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)


class ProductDTO(BaseModel):
    """Canonical product projection."""

    product_id: str
    sku: str
    name: str
    description: str = ""
    price: Decimal | None = None
    category: str = ""
    in_stock: bool = False
    available_quantity: int | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    score: float | None = None


class InventoryDTO(BaseModel):
    """Canonical inventory availability projection."""

    sku: str
    available_quantity: int
    reserved_quantity: int = 0
    warehouse: str | None = None


class OrderDTO(BaseModel):
    """Canonical order projection."""

    order_id: int | str
    order_sn: str
    user_id: int
    status: str
    total_amount: Decimal
    items: list[dict[str, Any]] = Field(default_factory=list)
    tracking_number: str | None = None
    created_at: datetime | None = None


class PaymentDTO(BaseModel):
    """Canonical payment projection."""

    order_sn: str
    status: str
    amount: Decimal | None = None
    payment_method: str | None = None
    paid_at: datetime | None = None


class InvoiceDTO(BaseModel):
    """Canonical invoice projection."""

    order_sn: str
    status: str
    invoice_number: str | None = None
    download_url: str | None = None


class LogisticsDTO(BaseModel):
    """Canonical logistics projection."""

    order_sn: str
    tracking_number: str | None = None
    carrier: str | None = None
    status: str
    latest_update: str | None = None
    estimated_delivery: str | None = None


class CartItemDTO(BaseModel):
    """Canonical cart line item."""

    product_id: str | None = None
    sku: str | None = None
    name: str
    quantity: int = Field(ge=1)
    price: Decimal = Decimal("0")
    subtotal: Decimal = Decimal("0")


class CartDTO(BaseModel):
    """Canonical customer cart."""

    user_id: int
    items: list[CartItemDTO] = Field(default_factory=list)
    total: Decimal = Decimal("0")


class RefundDTO(BaseModel):
    """Canonical refund projection."""

    refund_id: int | str
    order_id: int | str
    order_sn: str | None = None
    amount: Decimal
    status: str
    created_at: datetime | None = None


class NotificationCommand(BaseModel):
    """Normalized outbound notification command."""

    channel: str
    recipient: str
    template: str
    variables: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str
