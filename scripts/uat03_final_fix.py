"""Safety preflight helpers for the focused P-UAT-03 final-fix benchmark."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass

from sqlmodel import col, select

from app.core.database import async_session_maker
from app.core.tenancy import reset_current_tenant_id, set_current_tenant_id
from app.models.order import Order
from app.models.user import User

TRANSACTION_CASE_IDS = frozenset({"E2", "E3", "E4", "F1", "F2"})
TRANSACTION_ORDER_SNS = ("SN649201", "SN649202", "SN649203")


class UATPreflightError(RuntimeError):
    """Stop the scored UAT before provider calls when fixture ownership is unsafe."""


@dataclass(frozen=True, slots=True)
class BenchmarkIdentity:
    """One explicit tenant/user identity used by every transaction scenario."""

    tenant_id: str
    user_id: int


@dataclass(frozen=True, slots=True)
class OrderOwnership:
    """Ownership projection used by the preflight without exposing order contents."""

    order_sn: str
    tenant_id: str
    user_id: int


def identity_for_case(case_id: str, benchmark_identity: BenchmarkIdentity) -> BenchmarkIdentity:
    """Return the single benchmark identity for an E/F transaction case."""
    if case_id not in TRANSACTION_CASE_IDS:
        raise ValueError(f"Case {case_id!r} is not an E/F transaction scenario")
    return benchmark_identity


def browser_login_payload(*, username: str, password: str, tenant_id: str) -> dict[str, str]:
    """Build the supported tenant-aware browser-session login payload."""
    if not tenant_id.strip():
        raise ValueError("tenant_id is required for browser UAT login")
    return {"username": username, "password": password, "tenant_id": tenant_id}


def assert_transaction_ownership(
    identity: BenchmarkIdentity,
    orders: list[OrderOwnership],
    *,
    expected_order_sns: tuple[str, ...] = TRANSACTION_ORDER_SNS,
) -> None:
    """Fail before scored calls unless every synthetic order has the benchmark owner."""
    by_sn = {order.order_sn: order for order in orders}
    missing = [order_sn for order_sn in expected_order_sns if order_sn not in by_sn]
    mismatched = [
        order
        for order_sn in expected_order_sns
        if (order := by_sn.get(order_sn)) is not None
        and (order.tenant_id, order.user_id) != (identity.tenant_id, identity.user_id)
    ]
    if missing or mismatched:
        mismatch_text = ", ".join(
            f"{order.order_sn}:{order.tenant_id}/{order.user_id}" for order in mismatched
        )
        raise UATPreflightError(
            "Transaction fixture ownership preflight failed; "
            f"benchmark={identity.tenant_id}/{identity.user_id}; "
            f"missing={missing}; mismatched=[{mismatch_text}]"
        )


async def load_and_assert_transaction_ownership(
    *, tenant_id: str, user_id: int
) -> list[OrderOwnership]:
    """Read and verify the disposable fixture before any scored model request."""
    token = set_current_tenant_id(tenant_id)
    try:
        async with async_session_maker() as session:
            user = (
                await session.exec(
                    select(User).where(User.id == user_id, User.tenant_id == tenant_id)
                )
            ).one_or_none()
            if user is None:
                raise UATPreflightError(
                    f"Benchmark user {tenant_id}/{user_id} does not exist in the active tenant"
                )
            rows = (
                await session.exec(
                    select(Order).where(col(Order.order_sn).in_(TRANSACTION_ORDER_SNS))
                )
            ).all()
            ownership = [
                OrderOwnership(
                    order_sn=order.order_sn,
                    tenant_id=order.tenant_id,
                    user_id=order.user_id,
                )
                for order in rows
            ]
        assert_transaction_ownership(BenchmarkIdentity(tenant_id, user_id), ownership)
        return ownership
    finally:
        reset_current_tenant_id(token)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify P-UAT-03 E/F transaction ownership before model calls."
    )
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--user-id", required=True, type=int)
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    ownership = await load_and_assert_transaction_ownership(
        tenant_id=args.tenant_id, user_id=args.user_id
    )
    print(
        json.dumps(
            {
                "benchmark": asdict(BenchmarkIdentity(args.tenant_id, args.user_id)),
                "orders": [asdict(order) for order in ownership],
                "result": "PASS",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(_main())
