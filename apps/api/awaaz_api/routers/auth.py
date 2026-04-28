"""Auth endpoints invoked by Better Auth on the dashboard.

Better Auth runs server-side on the Next.js dashboard and is the source of
truth for sessions / passwords / OAuth.  This router handles a minimal token
exchange so first-party API clients (the dashboard SSR layer, mobile apps in
future) can resolve the current user against a Better Auth session.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text

from awaaz_api.deps import DbDep
from awaaz_api.observability import get_logger
from awaaz_api.middleware.tenant import TenantContext

router = APIRouter(prefix="/v1/auth", tags=["auth"])
_log = get_logger("awaaz.auth")


class ExchangeRequest(BaseModel):
    session_id: str


class ExchangeResponse(BaseModel):
    user_id: UUID
    email: str | None
    name: str | None
    organizations: list[dict[str, object]]


@router.post("/session/exchange", response_model=ExchangeResponse)
async def exchange_session(req: ExchangeRequest, request: Request, db: DbDep) -> ExchangeResponse:
    """Resolve a Better Auth session id → user + memberships."""

    row = (
        await db.execute(
            text(
                """
                SELECT s.user_id, s.expires_at, u.email, u.name
                FROM auth_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.id = :sid
                """
            ),
            {"sid": req.session_id},
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session not found")
    if row.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired")

    memberships = (
        await db.execute(
            text(
                """
                SELECT m.org_id, m.role, o.slug, o.name
                FROM memberships m
                JOIN organizations o ON o.id = m.org_id
                WHERE m.user_id = :u
                  AND o.status = 'active'
                """
            ),
            {"u": row.user_id},
        )
    ).all()

    # Surface tenant context to downstream handlers in the same request — no-op
    # here but useful when this router is re-used as a dependency.
    request.state.tenant = TenantContext(
        org_id=memberships[0].org_id if memberships else None,
        store_id=None,
        user_id=row.user_id,
        actor="user",
    )

    return ExchangeResponse(
        user_id=row.user_id,
        email=row.email,
        name=row.name,
        organizations=[
            {"id": m.org_id, "role": m.role, "slug": m.slug, "name": m.name}
            for m in memberships
        ],
    )


@router.post("/session/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(req: ExchangeRequest, db: DbDep) -> None:
    await db.execute(text("DELETE FROM auth_sessions WHERE id = :sid"), {"sid": req.session_id})
