import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select

from app.core.database import async_session_maker
from app.core.tenancy import tenant_scope
from app.models.order import Order, OrderStatus
from app.models.outbox import OutboxEvent, OutboxStatus
from app.models.refund import RefundApplication
from app.models.user import User
from app.services.order_service import OrderService


@pytest.fixture
def order_service() -> OrderService:
    return OrderService()


async def _create_test_user(session, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@test.com",
        full_name="Test User",
        password_hash=User.hash_password("testpass"),
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _create_test_order(
    session,
    user_id: int,
    order_sn: str,
    status: OrderStatus = OrderStatus.DELIVERED,
    total_amount: Decimal = Decimal("199.0"),
    created_at: datetime | None = None,
    items: list | None = None,
) -> Order:
    order = Order(
        order_sn=order_sn,
        user_id=user_id,
        status=status,
        total_amount=total_amount,
        shipping_address="Test Address",
        created_at=created_at or datetime.now(UTC),
        items=items if items is not None else [],
    )
    session.add(order)
    await session.flush()
    await session.refresh(order)
    return order


@pytest.mark.asyncio
async def test_get_order_for_user_with_order_sn(order_service: OrderService, db_session):
    """通过订单号查询订单"""
    user = await _create_test_user(db_session, "order_user_sn")
    assert user.id is not None
    await _create_test_order(db_session, user.id, "SN20240001", status=OrderStatus.SHIPPED)

    result = await order_service.get_order_for_user("SN20240001", user.id, session=db_session)

    assert result is not None
    assert result["order_sn"] == "SN20240001"
    assert result["status"] == OrderStatus.SHIPPED
    assert result["total_amount"] == 199.0


@pytest.mark.asyncio
async def test_get_order_for_user_without_order_sn(order_service: OrderService, db_session):
    """不传入订单号时返回用户最新订单"""
    user = await _create_test_user(db_session, "order_user_latest")
    assert user.id is not None
    await _create_test_order(db_session, user.id, "SN20240002", status=OrderStatus.DELIVERED)

    result = await order_service.get_order_for_user(None, user.id, session=db_session)

    assert result is not None
    assert result["order_sn"] == "SN20240002"
    assert result["status"] == OrderStatus.DELIVERED
    assert result["total_amount"] == 199.0


@pytest.mark.asyncio
async def test_handle_refund_request_success(order_service: OrderService, db_session):
    """退款申请成功路径（使用低金额避免触发风控审计/Celery）"""
    user = await _create_test_user(db_session, "refund_success_user")
    assert user.id is not None
    await _create_test_order(
        db_session,
        user.id,
        "SN20240001",
        status=OrderStatus.DELIVERED,
        total_amount=Decimal("199.0"),
        created_at=datetime.now(UTC) - timedelta(days=1),
    )

    result = await order_service.handle_refund_request(
        "我要退货，订单号 SN20240001，质量问题",
        user_id=user.id,
        thread_id="thread-1",
        session=db_session,
    )

    assert isinstance(result, dict)
    assert result["updated_state"] is not None
    assert "✅" in result["response"]
    assert result["updated_state"]["refund_flow_active"] is True
    assert result["updated_state"]["order_data"]["order_sn"] == "SN20240001"
    assert result["updated_state"]["refund_data"]["refund_id"] is not None
    assert result["updated_state"]["refund_data"]["amount"] == 199.0


@pytest.mark.asyncio
async def test_handle_refund_request_does_not_cross_user_order(
    order_service: OrderService, db_session
):
    owner = await _create_test_user(db_session, "refund_owner")
    requester = await _create_test_user(db_session, "refund_requester")
    assert owner.id is not None
    assert requester.id is not None
    await _create_test_order(
        db_session,
        owner.id,
        "SN20240003",
        status=OrderStatus.DELIVERED,
        total_amount=Decimal("1888.0"),
        created_at=datetime.now(UTC) - timedelta(days=1),
    )

    result = await order_service.handle_refund_request(
        "Refund order SN20240003",
        user_id=requester.id,
        session=db_session,
    )

    assert result["updated_state"]["refund_flow_active"] is False
    refunds = list((await db_session.exec(select(RefundApplication))).all())
    assert refunds == []


@pytest.mark.asyncio
async def test_handle_refund_request_commits_a_sanitized_pending_audit_event(
    order_service: OrderService, db_session
) -> None:
    """Persist the high-risk review intent atomically without request PII."""
    tenant_id = "tenant-refund-outbox"
    raw_phone = "13800138000"
    raw_email = "buyer@example.com"
    with tenant_scope(tenant_id):
        user = await _create_test_user(db_session, "refund_outbox_user")
        assert user.id is not None
        await _create_test_order(
            db_session,
            user.id,
            "SN20249991",
            status=OrderStatus.DELIVERED,
            total_amount=Decimal("12000.0"),
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
        result = await order_service.handle_refund_request(
            f"Order SN20249991 refund; phone {raw_phone}; email {raw_email}",
            user_id=user.id,
            thread_id="thread-outbox",
            session=db_session,
            tenant_id=tenant_id,
            correlation_id="corr-refund-outbox",
        )

        assert result["updated_state"]["refund_flow_active"] is True
        events = list(
            (
                await db_session.exec(
                    select(OutboxEvent).where(OutboxEvent.event_type == "refund.audit_requested")
                )
            ).all()
        )
    assert len(events) == 1
    event = events[0]
    serialized = json.dumps(event.envelope)
    assert event.status == OutboxStatus.PENDING
    assert event.tenant_id == tenant_id
    assert event.idempotency_key
    assert event.envelope["task_context"]["tenant_id"] == tenant_id
    assert event.envelope["task_context"]["correlation_id"] == "corr-refund-outbox"
    assert raw_phone not in serialized
    assert raw_email not in serialized


@pytest.mark.asyncio
async def test_handle_refund_request_commit_failure_rolls_back_business_and_outbox(
    order_service: OrderService, monkeypatch
) -> None:
    """Lose neither half of the refund and asynchronous-intent transaction."""
    tenant_id = "tenant-refund-rollback"
    with tenant_scope(tenant_id):
        async with async_session_maker() as setup_session:
            user = await _create_test_user(setup_session, "refund_rollback_user")
            assert user.id is not None
            order = await _create_test_order(
                setup_session,
                user.id,
                "SN20249992",
                status=OrderStatus.DELIVERED,
                total_amount=Decimal("12000.0"),
                created_at=datetime.now(UTC) - timedelta(days=1),
            )
            assert order.id is not None
            user_id = user.id
            order_id = order.id
            await setup_session.commit()

        async with async_session_maker() as business_session:
            monkeypatch.setattr(
                business_session,
                "commit",
                AsyncMock(side_effect=SQLAlchemyError("forced commit failure")),
            )
            with pytest.raises(SQLAlchemyError, match="forced commit failure"):
                await order_service.handle_refund_request(
                    "Refund order SN20249992",
                    user_id=user_id,
                    thread_id="thread-rollback",
                    session=business_session,
                    tenant_id=tenant_id,
                    correlation_id="corr-refund-rollback",
                )
            await business_session.rollback()

        async with async_session_maker() as verification_session:
            refund = (
                await verification_session.exec(
                    select(RefundApplication).where(RefundApplication.order_id == order_id)
                )
            ).one_or_none()
            outbox_events = list(
                (
                    await verification_session.exec(
                        select(OutboxEvent).where(OutboxEvent.tenant_id == tenant_id)
                    )
                ).all()
            )

    assert refund is None
    assert outbox_events == []


@pytest.mark.asyncio
async def test_handle_refund_request_missing_order_sn(order_service: OrderService):
    """未提供订单号时返回提示"""
    result = await order_service.handle_refund_request("我要退货", user_id=1)

    assert isinstance(result, dict)
    assert result["updated_state"] is not None
    assert "请提供订单号" in result["response"]
    assert result["updated_state"]["refund_flow_active"] is False


@pytest.mark.asyncio
async def test_handle_refund_request_order_not_found(order_service: OrderService, db_session):
    """订单不存在时返回错误"""
    user = await _create_test_user(db_session, "refund_notfound_user")
    assert user.id is not None

    result = await order_service.handle_refund_request(
        "我要退货，订单号 SN99999999",
        user_id=user.id,
        session=db_session,
    )

    assert isinstance(result, dict)
    assert result["updated_state"] is not None
    assert "未找到订单" in result["response"]
    assert result["updated_state"]["refund_flow_active"] is False


# 注：以下防御分支不再进行单元测试，因为在真实 PostgreSQL 中，
# 持久化行的主键永远不会为 NULL。该分支属于防御性代码，保留在
# 生产代码中，但按照 no-mock 基础设施策略不进行测试。
#
# @pytest.mark.asyncio
# async def test_handle_refund_request_order_id_none(...):
#     ...


@pytest.mark.asyncio
async def test_handle_refund_request_refund_failed(order_service: OrderService, db_session):
    """process_refund_for_order 返回失败时返回错误消息"""
    user = await _create_test_user(db_session, "refund_failed_user")
    assert user.id is not None
    await _create_test_order(
        db_session,
        user.id,
        "SN20240001",
        status=OrderStatus.PENDING,
        total_amount=Decimal("199.0"),
        created_at=datetime.now(UTC) - timedelta(days=1),
    )

    result = await order_service.handle_refund_request(
        "我要退货，订单号 SN20240001",
        user_id=user.id,
        session=db_session,
    )

    assert isinstance(result, dict)
    assert result["updated_state"] is not None
    assert "不符合退货条件" in result["response"]
    assert result["updated_state"]["refund_flow_active"] is False
    assert result["updated_state"]["order_data"]["order_sn"] == "SN20240001"
