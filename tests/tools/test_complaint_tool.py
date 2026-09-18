from unittest.mock import AsyncMock, patch

import pytest

from app.models.user import User
from app.tools.complaint_tool import ComplaintTool


@pytest.fixture
def complaint_tool() -> ComplaintTool:
    return ComplaintTool()


@pytest.mark.asyncio
async def test_execute_returns_success(complaint_tool: ComplaintTool):
    result = await complaint_tool.execute(None)
    assert result.output == {"success": True}


@pytest.mark.asyncio
async def test_create_ticket_with_defaults(complaint_tool: ComplaintTool, db_session):
    user = User(
        username="complaint_user",
        email="c@test.com",
        full_name="Test",
        password_hash=User.hash_password("pass"),
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    assert user.id is not None

    with patch("app.tools.complaint_tool.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await complaint_tool.create_ticket(
            user_id=user.id,
            thread_id="thread-1",
            category="PRODUCT_DEFECT",
            urgency="HIGH",
            description="Broken item",
            expected_resolution="REFUND",
            question="我要投诉商品损坏",
            intent_result={"primary_intent": "COMPLAINT", "secondary_intent": "APPLY"},
        )
    assert result["ticket_id"] is not None
    assert result["created"] is True
    assert result["authorized"] is True
    assert result["user_id"] == user.id
    assert result["status"] == "open"


@pytest.mark.asyncio
async def test_create_ticket_normalizes_invalid_enums(complaint_tool: ComplaintTool, db_session):
    user = User(
        username="complaint_user2",
        email="c2@test.com",
        full_name="Test",
        password_hash=User.hash_password("pass"),
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    assert user.id is not None

    with patch("app.tools.complaint_tool.async_session_maker") as mock_maker:
        mock_maker.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await complaint_tool.create_ticket(
            user_id=user.id,
            thread_id="thread-2",
            category="UNKNOWN_CATEGORY",
            urgency="UNKNOWN_URGENCY",
            description="Something",
            expected_resolution="UNKNOWN_RESOLUTION",
            order_sn="ORDER123",
            question="我要投诉商品问题",
            intent_result={"primary_intent": "COMPLAINT", "secondary_intent": "APPLY"},
        )
    assert result["status"] == "open"

    from sqlmodel import select

    from app.models.complaint import (
        ComplaintCategory,
        ComplaintTicket,
        ComplaintUrgency,
        ExpectedResolution,
    )

    ticket_result = await db_session.exec(
        select(ComplaintTicket).where(ComplaintTicket.thread_id == "thread-2")
    )
    ticket = ticket_result.one()
    assert ticket.category == ComplaintCategory.OTHER.value
    assert ticket.urgency == ComplaintUrgency.MEDIUM.value
    assert ticket.expected_resolution == ExpectedResolution.APOLOGY.value
    assert ticket.order_sn == "ORDER123"


@pytest.mark.asyncio
async def test_create_ticket_rejects_policy_consultation_before_persistence(
    complaint_tool: ComplaintTool,
):
    with patch("app.tools.complaint_tool.async_session_maker") as mock_maker:
        result = await complaint_tool.create_ticket(
            user_id=1,
            thread_id="consultation-thread",
            category="product_defect",
            urgency="medium",
            description="不是产品坏了，就是我自己不喜欢，退的话运费怎么办？",
            expected_resolution="apology",
            question="不是产品坏了，就是我自己不喜欢，退的话运费怎么办？",
            intent_result={"primary_intent": "COMPLAINT", "secondary_intent": "QUERY"},
        )

    assert result == {
        "created": False,
        "authorized": False,
        "reason": "explicit_complaint_request_required",
    }
    mock_maker.assert_not_called()
