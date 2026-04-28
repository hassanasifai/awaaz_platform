"""Conversation read API + manual operator actions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text

from awaaz_api.deps import CurrentUserDep, DbDep
from awaaz_api.schemas.conversation import ConversationOut

router = APIRouter(
    prefix="/v1/orgs/{org_id}/stores/{store_id}/conversations",
    tags=["conversations"],
)


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    org_id: UUID,
    store_id: UUID,
    user: CurrentUserDep,
    db: DbDep,
    cursor: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    channel: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
) -> list[ConversationOut]:
    if user.org_id != org_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "wrong org")
    where = ["store_id = :sid"]
    params: dict[str, object] = {"sid": store_id, "lim": limit}
    if cursor:
        where.append("opened_at < :cursor")
        params["cursor"] = cursor
    if channel:
        where.append("channel = :ch")
        params["ch"] = channel
    if outcome:
        where.append("outcome = :oc")
        params["oc"] = outcome
    rows = (
        await db.execute(
            text(
                f"""
                SELECT id, channel, state, outcome, outcome_reason, cost_usd::float,
                       tokens_input, tokens_output, opened_at, closed_at,
                       last_inbound_at, last_outbound_at
                FROM conversations
                WHERE {' AND '.join(where)}
                ORDER BY opened_at DESC
                LIMIT :lim
                """
            ),
            params,
        )
    ).all()
    return [ConversationOut(**r._mapping) for r in rows]


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    org_id: UUID,
    store_id: UUID,
    conversation_id: UUID,
    db: DbDep,
) -> ConversationOut:
    row = (
        await db.execute(
            text(
                """
                SELECT id, channel, state, outcome, outcome_reason, cost_usd::float,
                       tokens_input, tokens_output, opened_at, closed_at,
                       last_inbound_at, last_outbound_at
                FROM conversations
                WHERE id = :cid AND store_id = :sid
                """
            ),
            {"cid": conversation_id, "sid": store_id},
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return ConversationOut(**row._mapping)


class CloseRequest(BaseModel):
    reason: str
    outcome: str = "escalated"


@router.post("/{conversation_id}/close", status_code=status.HTTP_204_NO_CONTENT)
async def close_conversation(
    org_id: UUID,
    store_id: UUID,
    conversation_id: UUID,
    body: CloseRequest,
    user: CurrentUserDep,
    db: DbDep,
) -> None:
    """Operator-initiated close (escalation handoff or manual disposition)."""

    await db.execute(
        text(
            """
            UPDATE conversations
            SET state = 'closing',
                outcome = :oc,
                outcome_reason = :r,
                closed_at = now()
            WHERE id = :cid AND store_id = :sid AND closed_at IS NULL
            """
        ),
        {"cid": conversation_id, "sid": store_id, "oc": body.outcome, "r": body.reason},
    )
