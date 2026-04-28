"""Lightweight aggregate endpoints feeding the dashboard overview."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from awaaz_api.deps import DbDep

router = APIRouter(prefix="/v1/orgs/{org_id}/stores/{store_id}/analytics", tags=["analytics"])


class OverviewOut(BaseModel):
    window_hours: int
    conversations: int
    confirmed: int
    cancelled: int
    rescheduled: int
    escalated: int
    no_response: int
    avg_cost_usd: float
    avg_first_response_ms: int | None


@router.get("/overview", response_model=OverviewOut)
async def overview(
    org_id: UUID,
    store_id: UUID,
    db: DbDep,
    window_hours: int = Query(default=24, ge=1, le=24 * 90),
) -> OverviewOut:
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    row = (
        await db.execute(
            text(
                """
                SELECT
                    count(*) AS total,
                    count(*) FILTER (WHERE outcome = 'confirmed') AS confirmed,
                    count(*) FILTER (WHERE outcome = 'cancelled') AS cancelled,
                    count(*) FILTER (WHERE outcome = 'rescheduled') AS rescheduled,
                    count(*) FILTER (WHERE outcome = 'escalated') AS escalated,
                    count(*) FILTER (WHERE outcome = 'no_response' OR outcome IS NULL) AS no_response,
                    COALESCE(avg(cost_usd), 0)::float AS avg_cost
                FROM conversations
                WHERE store_id = :sid AND opened_at >= :since
                """
            ),
            {"sid": store_id, "since": since},
        )
    ).one()
    return OverviewOut(
        window_hours=window_hours,
        conversations=row.total,
        confirmed=row.confirmed,
        cancelled=row.cancelled,
        rescheduled=row.rescheduled,
        escalated=row.escalated,
        no_response=row.no_response,
        avg_cost_usd=row.avg_cost,
        avg_first_response_ms=None,
    )
