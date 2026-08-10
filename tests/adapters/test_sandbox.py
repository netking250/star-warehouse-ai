"""Tests for deterministic sandbox and programmable mock adapters."""

from decimal import Decimal

import pytest

from app.adapters.contracts import AdapterContext, CartItemDTO
from app.adapters.errors import AdapterError, AdapterErrorCode
from app.adapters.mock import MockBusinessAdapter
from app.adapters.sandbox import SandboxBusinessAdapter


@pytest.mark.asyncio
async def test_sandbox_cart_isolated_by_tenant_and_user() -> None:
    adapter = SandboxBusinessAdapter()
    first = AdapterContext(tenant_id="tenant-a", user_id=9)
    second = AdapterContext(tenant_id="tenant-b", user_id=9)
    item = CartItemDTO(
        sku="SKU-1",
        name="星仓耳机",
        quantity=2,
        price=Decimal("99.50"),
        subtotal=Decimal("199.00"),
    )

    await adapter.add_item(item, first)

    assert len((await adapter.get_cart(first)).items) == 1
    assert (await adapter.get_cart(second)).items == []


@pytest.mark.asyncio
async def test_mock_adapter_records_calls_and_injects_failures() -> None:
    adapter = MockBusinessAdapter()
    context = AdapterContext(tenant_id="tenant-a", user_id=3)
    adapter.failures["get_account"] = AdapterError(
        AdapterErrorCode.UNAVAILABLE,
        "offline",
        service="identity",
        retryable=True,
    )

    with pytest.raises(AdapterError):
        await adapter.get_account(context)

    assert adapter.calls == [("get_account", (context,))]
