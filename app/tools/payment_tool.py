"""Payment tool backed by payment, invoice, order, and refund ports."""

from app.adapters.context import current_adapter_context
from app.adapters.errors import AdapterError
from app.adapters.local import (
    LocalInvoiceAdapter,
    LocalOrderAdapter,
    LocalPaymentAdapter,
    LocalRefundAdapter,
)
from app.adapters.ports import InvoicePort, OrderPort, PaymentPort, RefundPort
from app.models.state import AgentState
from app.tools.base import BaseTool, ToolResult


class PaymentTool(BaseTool):
    name = "payment"
    description = "查询支付状态、发票信息、退款记录"

    def __init__(
        self,
        payment_port: PaymentPort | None = None,
        invoice_port: InvoicePort | None = None,
        order_port: OrderPort | None = None,
        refund_port: RefundPort | None = None,
    ) -> None:
        self._payment = payment_port
        self._invoice = invoice_port
        self._orders = order_port
        self._refunds = refund_port

    async def execute(self, state: AgentState, session=None, **kwargs) -> ToolResult:
        """Aggregate payment projections without direct database access."""
        user_id = state.get("user_id")
        if user_id is None:
            return ToolResult(output={"message": "未查询到相关支付/退款记录"})
        slots = state.get("slots") or {}
        order_sn = slots.get("order_sn") or kwargs.get("order_sn")
        context = current_adapter_context(user_id)
        local_orders = LocalOrderAdapter(session)
        orders = self._orders or local_orders
        payment_port = self._payment or LocalPaymentAdapter(local_orders)
        invoice_port = self._invoice or LocalInvoiceAdapter(local_orders)
        refund_port = self._refunds or LocalRefundAdapter(session)

        try:
            order = await orders.get_order(str(order_sn), context) if order_sn else None
            resolved_order_sn = str(order_sn or "")
            payment = (
                await payment_port.get_payment(resolved_order_sn, context)
                if resolved_order_sn
                else None
            )
            invoice = (
                await invoice_port.get_invoice(resolved_order_sn, context)
                if resolved_order_sn
                else None
            )
            refunds = await refund_port.list_refunds(order.order_id if order else None, context)
        except AdapterError:
            return ToolResult(output={"message": "支付服务暂时不可用，请稍后重试"})
        records = []
        for refund in refunds:
            record = refund.model_dump(mode="json")
            record["amount"] = float(refund.amount)
            records.append(record)
        output = {
            "payment_status": payment.status if payment else "未知",
            "invoice_status": invoice.status if invoice else "未查询到发票信息",
            "refund_records": records,
        }
        if not records and payment is None:
            output["message"] = "未查询到相关支付/退款记录"
        return ToolResult(output=output)
