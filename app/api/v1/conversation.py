"""Authenticated durable conversation runtime control routes."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.conversation.composition import build_conversation_runtime
from app.conversation.contracts import ConversationIdentity
from app.conversation.runtime import ConversationNotFoundError
from app.core.security import AuthContext, get_authorized_auth_context
from app.core.utils import build_thread_id

router = APIRouter(prefix="/conversations")


def _identity(auth_context: AuthContext) -> ConversationIdentity:
    return ConversationIdentity(
        tenant_id=auth_context.tenant_id,
        user_id=auth_context.user_id,
        correlation_id=auth_context.correlation_id,
        trace_id=None,
    )


def _not_found(error: ConversationNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Conversation run was not found",
    )


@router.get("/{conversation_id}/runs/{run_id}")
async def get_conversation_run(
    conversation_id: str,
    run_id: str,
    request: Request,
    auth_context: AuthContext = Depends(get_authorized_auth_context),
) -> dict[str, object]:
    """Return the durable status and final result of one owned run."""
    canonical_id = build_thread_id(auth_context.user_id, conversation_id)
    try:
        snapshot = await build_conversation_runtime(request.app.state).get_run(
            identity=_identity(auth_context),
            conversation_id=canonical_id,
            run_id=run_id,
        )
    except ConversationNotFoundError as error:
        raise _not_found(error) from error
    return asdict(snapshot)


@router.get("/{conversation_id}/runs/{run_id}/events")
async def replay_conversation_run_events(
    conversation_id: str,
    run_id: str,
    request: Request,
    after_sequence: int = Query(default=0, ge=0),
    auth_context: AuthContext = Depends(get_authorized_auth_context),
) -> dict[str, object]:
    """Replay durable ordered events without starting a new execution."""
    canonical_id = build_thread_id(auth_context.user_id, conversation_id)
    try:
        events = await build_conversation_runtime(request.app.state).replay_events(
            identity=_identity(auth_context),
            conversation_id=canonical_id,
            run_id=run_id,
            after_sequence=after_sequence,
        )
    except ConversationNotFoundError as error:
        raise _not_found(error) from error
    return {"events": [asdict(event) for event in events]}


@router.post("/{conversation_id}/runs/{run_id}/cancel")
async def cancel_conversation_run(
    conversation_id: str,
    run_id: str,
    request: Request,
    auth_context: AuthContext = Depends(get_authorized_auth_context),
) -> dict[str, object]:
    """Logically cancel an owned active run through an idempotent boundary."""
    canonical_id = build_thread_id(auth_context.user_id, conversation_id)
    try:
        result = await build_conversation_runtime(request.app.state).cancel_run(
            identity=_identity(auth_context),
            conversation_id=canonical_id,
            run_id=run_id,
        )
    except ConversationNotFoundError as error:
        raise _not_found(error) from error
    return {"outcome": result.outcome, "run": asdict(result.run)}
