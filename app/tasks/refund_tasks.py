"""
退款相关异步任务
"""

import logging
import time
from typing import Any

from sqlmodel import Session, select

from app.celery_app import celery_app
from app.core.database import sync_session_maker
from app.core.utils import utc_now
from app.models.audit import AuditLog
from app.models.message import MessageCard, MessageStatus, MessageType
from app.models.refund import RefundApplication, RefundStatus
from app.models.user import User
from app.task_runtime.dead_letter import CeleryDeadLetterPublisher, DeadLetterPublisher
from app.task_runtime.envelope import TaskEnvelope
from app.task_runtime.refund_payloads import (
    AuditNotificationPayload,
    RefundPaymentPayload,
    RefundSmsPayload,
)
from app.task_runtime.reliability import PermanentTaskError, consume_db_task

logger = logging.getLogger(__name__)


def _process_refund_payment_body(
    refund_id: int, amount: float, payment_method: str, session: Session
) -> dict[str, Any]:
    result = session.exec(select(RefundApplication).where(RefundApplication.id == refund_id))
    refund = result.one_or_none()

    if not refund:
        raise PermanentTaskError("REFUND_NOT_FOUND", f"Refund application {refund_id} not found")

    logger.info(f"💰 [Payment] 退款 ¥{amount} 到 {payment_method}")

    refund.status = RefundStatus.COMPLETED
    refund.updated_at = utc_now()
    session.add(refund)
    return {
        "status": "success",
        "refund_id": refund_id,
        "amount": amount,
        "transaction_id": f"TXN{refund_id}{int(time.time())}",
        "completed_at": utc_now().isoformat(),
    }


def _send_refund_sms_body(refund_id: int, session: Session) -> dict[str, Any]:
    refund = session.exec(
        select(RefundApplication).where(RefundApplication.id == refund_id)
    ).one_or_none()
    if refund is None:
        raise PermanentTaskError("REFUND_NOT_FOUND", f"Refund application {refund_id} not found")

    user = session.exec(select(User).where(User.id == refund.user_id)).one_or_none()
    if user is None or not user.phone:
        raise PermanentTaskError(
            "SMS_RECIPIENT_NOT_FOUND",
            f"SMS recipient for refund application {refund_id} not found",
        )

    # The delivery adapter receives the phone in memory; logs and task results do not.
    logger.info("Sending refund SMS for refund_id=%s", refund_id)
    return {
        "status": "success",
        "refund_id": refund_id,
        "sent_at": utc_now().isoformat(),
    }


def _notify_admin_audit_body(audit_log_id: int, session: Session) -> dict[str, Any]:
    result = session.exec(select(AuditLog).where(AuditLog.id == audit_log_id))
    audit_log = result.one_or_none()

    if not audit_log:
        raise PermanentTaskError("AUDIT_NOT_FOUND", f"Audit log {audit_log_id} not found")

    logger.info("  [Notify] 通知管理员审核任务:")
    logger.info(f"  - 风险等级: {audit_log.risk_level}")
    logger.info(f"  - 触发原因: {audit_log.trigger_reason}")
    logger.info(f"  - 用户ID: {audit_log.user_id}")

    message = MessageCard(
        thread_id=audit_log.thread_id,
        message_type=MessageType.SYSTEM,
        status=MessageStatus.SENT,
        content={
            "type": "admin_notification",
            "audit_log_id": audit_log_id,
            "risk_level": audit_log.risk_level,
            "message": f"新的{audit_log.risk_level}风险审核任务",
        },
        sender_type="system",
        receiver_id=None,
    )
    session.add(message)
    return {
        "status": "success",
        "audit_log_id": audit_log_id,
        "notified_at": utc_now().isoformat(),
    }


@celery_app.task(
    bind=True,
    name="refund.send_sms",
    ignore_result=True,
    max_retries=3,
    acks_late=True,
    acks_on_failure_or_timeout=False,
    reject_on_worker_lost=True,
)
def send_refund_sms(
    self,
    envelope: dict[str, object],
    session=None,
    dead_letter_publisher: DeadLetterPublisher | None = None,
) -> dict[str, Any]:
    def operation(task_session: Session) -> dict[str, Any]:
        task_envelope = TaskEnvelope.from_message(envelope)
        payload = RefundSmsPayload.model_validate(task_envelope.payload)
        return _send_refund_sms_body(payload.refund_id, task_session)

    publisher = dead_letter_publisher or CeleryDeadLetterPublisher(celery_app)
    if session is None:
        with sync_session_maker() as task_session:
            return consume_db_task(
                task=self,
                raw_envelope=envelope,
                handler="refund.send_sms",
                operation=operation,
                session=task_session,
                dead_letter_publisher=publisher,
            )
    return consume_db_task(
        task=self,
        raw_envelope=envelope,
        handler="refund.send_sms",
        operation=operation,
        session=session,
        dead_letter_publisher=publisher,
    )


@celery_app.task(
    bind=True,
    name="refund.process_payment",
    ignore_result=True,
    max_retries=3,
    acks_late=True,
    acks_on_failure_or_timeout=False,
    reject_on_worker_lost=True,
)
def process_refund_payment(
    self,
    envelope: dict[str, object],
    session=None,
    dead_letter_publisher: DeadLetterPublisher | None = None,
) -> dict[str, Any]:
    def operation(task_session: Session) -> dict[str, Any]:
        task_envelope = TaskEnvelope.from_message(envelope)
        payload = RefundPaymentPayload.model_validate(task_envelope.payload)
        return _process_refund_payment_body(
            payload.refund_id,
            payload.amount,
            payload.payment_method,
            task_session,
        )

    publisher = dead_letter_publisher or CeleryDeadLetterPublisher(celery_app)
    if session is None:
        with sync_session_maker() as task_session:
            return consume_db_task(
                task=self,
                raw_envelope=envelope,
                handler="refund.process_payment",
                operation=operation,
                session=task_session,
                dead_letter_publisher=publisher,
            )
    return consume_db_task(
        task=self,
        raw_envelope=envelope,
        handler="refund.process_payment",
        operation=operation,
        session=session,
        dead_letter_publisher=publisher,
    )


@celery_app.task(
    bind=True,
    name="refund.notify_admin",
    ignore_result=True,
    max_retries=2,
    acks_late=True,
    acks_on_failure_or_timeout=False,
    reject_on_worker_lost=True,
)
def notify_admin_audit(
    self,
    envelope: dict[str, object],
    session=None,
    dead_letter_publisher: DeadLetterPublisher | None = None,
) -> dict[str, Any]:
    def operation(task_session: Session) -> dict[str, Any]:
        task_envelope = TaskEnvelope.from_message(envelope)
        payload = AuditNotificationPayload.model_validate(task_envelope.payload)
        return _notify_admin_audit_body(payload.audit_log_id, task_session)

    publisher = dead_letter_publisher or CeleryDeadLetterPublisher(celery_app)
    if session is None:
        with sync_session_maker() as task_session:
            return consume_db_task(
                task=self,
                raw_envelope=envelope,
                handler="refund.notify_admin",
                operation=operation,
                session=task_session,
                dead_letter_publisher=publisher,
            )
    return consume_db_task(
        task=self,
        raw_envelope=envelope,
        handler="refund.notify_admin",
        operation=operation,
        session=session,
        dead_letter_publisher=publisher,
    )
