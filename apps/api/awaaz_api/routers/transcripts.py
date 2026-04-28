"""Transcripts (full text + embedding) — read-only for the dashboard."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from awaaz_api.deps import DbDep

router = APIRouter(
    prefix="/v1/orgs/{org_id}/stores/{store_id}/transcripts",
    tags=["transcripts"],
)


class TranscriptOut(BaseModel):
    id: UUID
    conversation_id: UUID
    full_text: str
    summary: str | None
    language: str
    created_at: datetime


@router.get("/{conversation_id}", response_model=TranscriptOut)
async def get_transcript(
    org_id: UUID,
    store_id: UUID,
    conversation_id: UUID,
    db: DbDep,
) -> TranscriptOut:
    row = (
        await db.execute(
            text(
                """
                SELECT id, conversation_id, full_text, summary, language, created_at
                FROM transcripts
                WHERE conversation_id = :cid AND store_id = :sid
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"cid": conversation_id, "sid": store_id},
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return TranscriptOut(**row._mapping)
