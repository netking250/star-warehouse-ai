import logging
from typing import Any

from app.core.database import async_session_maker
from app.intent.models import IntentAction, IntentCategory, IntentResult
from app.models.complaint import (
    ComplaintCategory,
    ComplaintStatus,
    ComplaintTicket,
    ComplaintUrgency,
    ExpectedResolution,
)
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

COMPLAINT_TICKET_NOT_CREATED_RESPONSE = (
    "\u5f53\u524d\u662f\u54a8\u8be2\u573a\u666f\uff0c\u6682\u672a\u521b\u5efa\u6295\u8bc9\u5de5\u5355\uff1b"
    "\u5982\u679c\u60a8\u5e0c\u671b\u6b63\u5f0f\u6295\u8bc9\u6216\u8f6c\u4eba\u5de5\uff0c"
    "\u8bf7\u660e\u786e\u8bf4\u660e\u201c\u6211\u8981\u6295\u8bc9\u201d\u6216\u201c\u8f6c\u4eba\u5de5\u201d\u3002"
)

_EXPLICIT_COMPLAINT_MARKERS = (
    "我要投诉",
    "我想投诉",
    "帮我投诉",
    "请帮我投诉",
    "提交投诉",
    "创建投诉",
    "投诉工单",
    "正式投诉",
    "转人工",
    "人工客服",
    "升级投诉",
)
_EXPLICIT_COMPLAINT_ENGLISH_MARKERS = (
    "i want to complain",
    "i'd like to complain",
    "file a complaint",
    "submit a complaint",
    "open a complaint",
    "create a complaint",
    "escalate this complaint",
    "contact human support",
    "transfer me to a human",
)


def _intent_field(
    intent_result: IntentResult | dict[str, object] | None,
    field_name: str,
) -> object | None:
    if isinstance(intent_result, dict):
        return intent_result.get(field_name)
    if intent_result is None:
        return None
    return getattr(intent_result, field_name, None)


def _intent_value(value: object | None) -> str | None:
    if isinstance(value, str):
        return value.upper()
    enum_value = getattr(value, "value", None)
    return enum_value.upper() if isinstance(enum_value, str) else None


def is_explicit_complaint_request(
    question: str,
    intent_result: IntentResult | dict[str, object] | None,
) -> bool:
    """Return whether the current turn authorizes complaint-ticket creation."""
    primary_intent = _intent_value(_intent_field(intent_result, "primary_intent"))
    secondary_intent = _intent_value(_intent_field(intent_result, "secondary_intent"))
    if primary_intent != IntentCategory.COMPLAINT.value:
        return False
    if secondary_intent not in {IntentAction.QUERY.value, IntentAction.APPLY.value}:
        return False

    normalized_question = " ".join(question.casefold().split())
    return any(marker in question for marker in _EXPLICIT_COMPLAINT_MARKERS) or any(
        marker in normalized_question for marker in _EXPLICIT_COMPLAINT_ENGLISH_MARKERS
    )


class ComplaintTool(BaseTool):
    name = "complaint"
    description = "Handle user complaints and create complaint tickets."

    async def execute(self, state: Any, **kwargs) -> ToolResult:
        _ = state
        _ = kwargs
        logger.debug("ComplaintTool.execute called")
        return ToolResult(output={"success": True})

    async def create_ticket(
        self,
        user_id: int,
        thread_id: str,
        category: str,
        urgency: str,
        description: str,
        expected_resolution: str,
        order_sn: str | None = None,
        question: str = "",
        intent_result: IntentResult | dict[str, object] | None = None,
    ) -> dict[str, Any]:
        if not is_explicit_complaint_request(question, intent_result):
            logger.warning(
                "Rejected complaint ticket creation without explicit customer request",
                extra={"user_id": user_id, "thread_id": thread_id},
            )
            return {
                "created": False,
                "authorized": False,
                "reason": "explicit_complaint_request_required",
            }

        category = category.lower().strip()
        urgency = urgency.lower().strip()
        expected_resolution = expected_resolution.lower().strip()
        category = category.lower().strip()
        urgency = urgency.lower().strip()
        expected_resolution = expected_resolution.lower().strip()

        if category not in {c.value for c in ComplaintCategory}:
            category = ComplaintCategory.OTHER.value
        if urgency not in {u.value for u in ComplaintUrgency}:
            urgency = ComplaintUrgency.MEDIUM.value
        if expected_resolution not in {e.value for e in ExpectedResolution}:
            expected_resolution = ExpectedResolution.APOLOGY.value

        async with async_session_maker() as session:
            ticket = ComplaintTicket(
                user_id=user_id,
                thread_id=thread_id,
                category=category,
                urgency=urgency,
                description=description,
                expected_resolution=expected_resolution,
                order_sn=order_sn,
                status=ComplaintStatus.OPEN.value,
            )
            session.add(ticket)
            await session.commit()
            await session.refresh(ticket)
            logger.info("Created complaint ticket id=%s for user_id=%s", ticket.id, user_id)
            return {
                "created": True,
                "authorized": True,
                "ticket_id": ticket.id,
                "user_id": ticket.user_id,
                "thread_id": ticket.thread_id,
                "status": ticket.status,
            }
