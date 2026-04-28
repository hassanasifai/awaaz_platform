"""Per-conversation message stream."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import text

from awaaz_api.deps import DbDep
from awaaz_api.schemas.conversation import MessageOut

router = APIRouter(
    prefix="/v1/orgs/{org_id}/stores/{store_id}/conversations/{conversation_id}/messages",
    tags=["messages"],
)


@router.get("", response_model=list[MessageOut])
async def list_messages(
    org_id: UUID,
    store_id: UUID,
    conversation_id: UUID,
    db: DbDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[MessageOut]:
    rows = (
        await db.execute(
            text(
                """
                SELECT id, direction, role, content_type,
                       COALESCE(body_redacted, body) AS body,
                       template_name, media_s3_key,
                       sent_at, delivered_at, read_at, created_at
                FROM messages
                WHERE conversation_id = :cid AND store_id = :sid
                ORDER BY created_at
                LIMIT :lim
                """
            ),
            {"cid": conversation_id, "sid": store_id, "lim": limit},
        )
    ).all()
    return [MessageOut(**r._mapping) for r in rows]
