import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from pydantic import JsonValue
from sqlmodel import select

from app.models.audit import AuditAction, AuditLog, AuditTriggerType, RiskLevel
from app.models.message import MessageCard, MessageType
from app.models.order import Order, OrderStatus
from app.models.refund import RefundApplication, RefundStatus
from app.models.task_receipt import TaskExecutionReceipt, TaskReceiptStatus
from app.models.user import User
from app.task_runtime.context import build_task_context
from app.task_runtime.envelope import TaskEnvelope
from app.tasks.refund_tasks import (
    notify_admin_audit,
    process_refund_payment,
    send_refund_sms,
)


def _envelope(
    payload: dict[str, JsonValue], *, thread_id: str = "refund-test"
) -> dict[str, object]:
    context = build_task_context(
        task_name="tests.refund",
        tenant_id="default",
        user_id=1,
        correlation_id=f"refund-test:{thread_id}",
        thread_id=thread_id,
    )
    return TaskEnvelope(task_context=context, payload=payload).to_message()


class TestSendRefundSms:
    def test_send_refund_sms_resolves_recipient_without_payload_pii(self, db_sync_session):
        user = User(
            username=f"sms_user_{uuid.uuid4().hex[:8]}",
            password_hash=User.hash_password("testpass"),
            email=f"{uuid.uuid4().hex[:8]}@test.com",
            phone="13800138000",
            full_name="SMS User",
        )
        db_sync_session.add(user)
        db_sync_session.commit()
        db_sync_session.refresh(user)
        assert user.id is not None
        order = Order(
            order_sn=f"SMS{uuid.uuid4().hex[:12].upper()}",
            user_id=user.id,
            status=OrderStatus.DELIVERED,
            total_amount=Decimal("99.9"),
            shipping_address="Test Address",
        )
        db_sync_session.add(order)
        db_sync_session.commit()
        db_sync_session.refresh(order)
        assert order.id is not None
        refund = RefundApplication(
            order_id=order.id,
            user_id=user.id,
            status=RefundStatus.APPROVED,
            reason_detail="Test refund",
            refund_amount=Decimal("99.9"),
        )
        db_sync_session.add(refund)
        db_sync_session.commit()
        db_sync_session.refresh(refund)
        assert refund.id is not None

        envelope = _envelope({"refund_id": refund.id})
        assert user.phone is not None
        assert user.phone not in str(envelope)
        result = send_refund_sms.run(
            envelope,
            session=db_sync_session,
        )
        assert result["status"] == "success"
        assert result["refund_id"] == refund.id
        assert "phone" not in result


class TestProcessRefundPayment:
    def test_process_refund_payment_success(self, db_sync_session):
        user = User(
            username=f"refund_user_{uuid.uuid4().hex[:8]}",
            password_hash=User.hash_password("testpass"),
            email=f"{uuid.uuid4().hex[:8]}@test.com",
            full_name="Test User",
        )
        db_sync_session.add(user)
        db_sync_session.commit()
        db_sync_session.refresh(user)
        assert user.id is not None

        order = Order(
            order_sn=f"ORD{uuid.uuid4().hex[:12].upper()}",
            user_id=user.id,
            status=OrderStatus.DELIVERED,
            total_amount=Decimal("199.99"),
            shipping_address="Test Address",
        )
        db_sync_session.add(order)
        db_sync_session.commit()
        db_sync_session.refresh(order)
        assert order.id is not None

        refund = RefundApplication(
            order_id=order.id,
            user_id=user.id,
            status=RefundStatus.PENDING,
            reason_detail="Test refund",
            refund_amount=Decimal("99.9"),
        )
        db_sync_session.add(refund)
        db_sync_session.commit()
        db_sync_session.refresh(refund)

        result = process_refund_payment.run(
            _envelope({"refund_id": refund.id, "amount": 99.9, "payment_method": "alipay"}),
            session=db_sync_session,
        )

        assert result["status"] == "success"
        assert result["refund_id"] == refund.id
        assert result["amount"] == 99.9

        updated = db_sync_session.exec(
            select(RefundApplication).where(RefundApplication.id == refund.id)
        ).one()
        assert updated.status == RefundStatus.COMPLETED
        assert updated.updated_at is not None

    def test_process_refund_payment_duplicate_envelope_applies_effect_once(
        self, db_sync_session
    ) -> None:
        """Recognize duplicate delivery through the protected task interface."""
        user = User(
            username=f"duplicate_refund_{uuid.uuid4().hex[:8]}",
            password_hash=User.hash_password("testpass"),
            email=f"{uuid.uuid4().hex[:8]}@test.com",
            full_name="Duplicate Refund User",
        )
        db_sync_session.add(user)
        db_sync_session.commit()
        db_sync_session.refresh(user)
        assert user.id is not None
        order = Order(
            order_sn=f"DUP{uuid.uuid4().hex[:12].upper()}",
            user_id=user.id,
            status=OrderStatus.DELIVERED,
            total_amount=Decimal("199.99"),
            shipping_address="Test Address",
        )
        db_sync_session.add(order)
        db_sync_session.commit()
        db_sync_session.refresh(order)
        assert order.id is not None
        refund = RefundApplication(
            order_id=order.id,
            user_id=user.id,
            status=RefundStatus.APPROVED,
            reason_detail="Duplicate-safe refund",
            refund_amount=Decimal("99.9"),
        )
        db_sync_session.add(refund)
        db_sync_session.commit()
        db_sync_session.refresh(refund)
        assert refund.id is not None
        envelope = _envelope(
            {"refund_id": refund.id, "amount": 99.9, "payment_method": "alipay"},
            thread_id=f"duplicate-{refund.id}",
        )

        first = process_refund_payment.run(envelope, session=db_sync_session)
        second = process_refund_payment.run(envelope, session=db_sync_session)

        receipts = list(
            (
                db_sync_session.exec(
                    select(TaskExecutionReceipt).where(
                        TaskExecutionReceipt.handler == "refund.process_payment"
                    )
                )
            ).all()
        )
        assert first["status"] == "success"
        assert second["status"] == "success"
        assert second["duplicate"] is True
        assert len(receipts) == 1
        assert receipts[0].status == TaskReceiptStatus.COMPLETED


def test_process_refund_payment_not_found(db_sync_session):
    dead_letters = MagicMock()
    dead_letters.publish.return_value = "dead-letter-test"
    result = process_refund_payment.run(
        _envelope({"refund_id": 999, "amount": 99.9, "payment_method": "alipay"}),
        session=db_sync_session,
        dead_letter_publisher=dead_letters,
    )
    assert result["status"] == "dead_lettered"
    assert result["failure_code"] == "REFUND_NOT_FOUND"
    dead_letters.publish.assert_called_once()


class TestNotifyAdminAudit:
    def test_notify_admin_audit_success(self, db_sync_session):
        user = User(
            username=f"audit_user_{uuid.uuid4().hex[:8]}",
            password_hash=User.hash_password("testpass"),
            email=f"{uuid.uuid4().hex[:8]}@test.com",
            full_name="Test User",
        )
        db_sync_session.add(user)
        db_sync_session.commit()
        db_sync_session.refresh(user)
        assert user.id is not None

        log = AuditLog(
            thread_id=f"thread-{uuid.uuid4().hex[:8]}",
            user_id=user.id,
            trigger_reason="金额过大",
            risk_level=RiskLevel.HIGH,
            action=AuditAction.PENDING,
            trigger_type=AuditTriggerType.RISK,
            context_snapshot={},
        )
        db_sync_session.add(log)
        db_sync_session.commit()
        db_sync_session.refresh(log)

        result = notify_admin_audit.run(
            _envelope({"audit_log_id": log.id}, thread_id=log.thread_id),
            session=db_sync_session,
        )

        assert result["status"] == "success"
        assert result["audit_log_id"] == log.id

        message = db_sync_session.exec(
            select(MessageCard).where(MessageCard.thread_id == log.thread_id)
        ).one_or_none()
        assert message is not None
        assert message.message_type == MessageType.SYSTEM
        assert message.content["type"] == "admin_notification"
        assert message.content["risk_level"] == RiskLevel.HIGH


def test_notify_admin_audit_not_found(db_sync_session):
    dead_letters = MagicMock()
    dead_letters.publish.return_value = "dead-letter-test"
    result = notify_admin_audit.run(
        _envelope({"audit_log_id": 999}),
        session=db_sync_session,
        dead_letter_publisher=dead_letters,
    )
    assert result["status"] == "dead_lettered"
    assert result["failure_code"] == "AUDIT_NOT_FOUND"
    dead_letters.publish.assert_called_once()
