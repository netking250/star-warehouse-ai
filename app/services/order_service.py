from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.adapters.context import current_adapter_context
from app.adapters.errors import AdapterError
from app.adapters.local import LocalOrderAdapter
from app.adapters.ports import OrderPort
from app.core.database import async_session_maker
from app.core.logging import get_correlation_id
from app.core.tenancy import get_current_tenant_id
from app.models.state import AgentProcessResult
from app.outbox import enqueue_task
from app.services.refund_service import (
    RefundRiskService,
    get_order_by_sn,
    process_refund_for_order,
)
from app.task_runtime.context import build_task_context
from app.utils.order_utils import classify_refund_reason, extract_order_sn

logger = logging.getLogger(__name__)


class OrderService:
    """订单服务层：封装订单查询与退款申请的数据库交互和副作用"""

    def __init__(self, order_port: OrderPort | None = None) -> None:
        self._order_port = order_port

    async def _get_order_for_user_body(
        self, order_sn: str | None, user_id: int, session: AsyncSession | None
    ) -> dict | None:
        port = self._order_port or LocalOrderAdapter(session)
        order = await port.get_order(order_sn, current_adapter_context(user_id))
        return order.model_dump() if order else None

    async def get_order_for_user(
        self, order_sn: str | None, user_id: int, session: AsyncSession | None = None
    ) -> dict | None:
        """查询用户订单，返回序列化后的字典或 None。"""
        try:
            if self._order_port is not None:
                return await self._get_order_for_user_body(order_sn, user_id, None)
            if session is None:
                async with async_session_maker() as session:
                    return await self._get_order_for_user_body(order_sn, user_id, session)
            return await self._get_order_for_user_body(order_sn, user_id, session)
        except SQLAlchemyError:
            logger.exception("[OrderService] Database error querying order")
            raise
        except AdapterError as error:
            logger.warning(
                "[OrderService] Adapter error querying order service=%s code=%s",
                error.service,
                error.code,
            )
            raise

    async def _handle_refund_request_body(
        self,
        question: str,
        user_id: int,
        thread_id: str,
        session: AsyncSession,
        tenant_id: str | None,
        correlation_id: str | None,
        trace_id: str | None,
    ) -> AgentProcessResult:
        order_sn = extract_order_sn(question)

        if not order_sn:
            return {
                "response": "请提供订单号以便处理退货申请。例如：我要退货，订单号 SN20240001",
                "updated_state": {"refund_flow_active": False},
            }

        reason_category = classify_refund_reason(question)
        reason_detail = question

        order = await get_order_by_sn(order_sn, user_id, session)
        if not order:
            return {
                "response": f"未找到订单 {order_sn}，请确认订单号是否正确。",
                "updated_state": {"refund_flow_active": False},
            }

        if order.id is None:
            return {
                "response": "订单数据异常，请稍后重试。",
                "updated_state": {"refund_flow_active": False},
            }

        success, message, refund_data, refund_app = await process_refund_for_order(
            order_sn=order_sn,
            user_id=user_id,
            reason_detail=reason_detail,
            reason_category=reason_category,
            session=session,
            order=order,
        )

        if not success:
            return {
                "response": message,
                "updated_state": {
                    "order_data": order.model_dump(),
                    "refund_flow_active": False,
                },
            }

        audit = None
        if refund_app is not None:
            audit = await RefundRiskService.assess_and_create_audit(
                session, refund_app, order, user_id, thread_id
            )

        updated_state: dict[str, Any] = {
            "order_data": order.model_dump(),
            "refund_flow_active": True,
        }
        if refund_data is not None:
            updated_state["refund_data"] = {
                "refund_id": refund_data["refund_id"],
                "amount": refund_data["amount"],
            }

        # The business transaction owns both the refund audit and its outbox intent.
        if audit is not None:
            if audit.id is None:
                raise RuntimeError("Audit ID is missing after persistence")
            effective_correlation = correlation_id or get_correlation_id()
            if effective_correlation == "-":
                effective_correlation = f"refund-audit:{audit.id}:{user_id}"
            task_context = build_task_context(
                task_name="refund.notify_admin",
                tenant_id=tenant_id or get_current_tenant_id(),
                user_id=user_id,
                correlation_id=effective_correlation,
                trace_id=trace_id,
                thread_id=thread_id or audit.thread_id,
                operation_id=f"audit:{audit.id}:notify",
            )
            await enqueue_task(
                session=session,
                task_name="refund.notify_admin",
                task_context=task_context,
                payload={"audit_log_id": audit.id},
                event_type="refund.audit_requested",
                aggregate_type="audit_log",
                aggregate_id=str(audit.id),
            )

        await session.commit()

        return {"response": f"✅ {message}", "updated_state": updated_state}

    async def handle_refund_request(
        self,
        question: str,
        user_id: int,
        thread_id: str = "",
        session: AsyncSession | None = None,
        *,
        tenant_id: str | None = None,
        correlation_id: str | None = None,
        trace_id: str | None = None,
    ) -> AgentProcessResult:
        """处理退货申请，封装数据库事务与 Celery 副作用。"""
        try:
            if session is None:
                async with async_session_maker() as session:
                    return await self._handle_refund_request_body(
                        question,
                        user_id,
                        thread_id,
                        session,
                        tenant_id,
                        correlation_id,
                        trace_id,
                    )
            return await self._handle_refund_request_body(
                question,
                user_id,
                thread_id,
                session,
                tenant_id,
                correlation_id,
                trace_id,
            )
        except SQLAlchemyError:
            logger.exception("[OrderService] Database error handling refund request")
            raise
