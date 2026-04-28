"""Organization CRUD + invite flow."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from awaaz_api.deps import CurrentUserDep, DbDep, RoleChecker

router = APIRouter(prefix="/v1/orgs", tags=["orgs"])


class OrgOut(BaseModel):
    id: UUID
    slug: str
    name: str
    country_code: str
    timezone: str
    status: str
    created_at: datetime


class OrgCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(..., min_length=1, max_length=200)
    country_code: str = "PK"
    timezone: str = "Asia/Karachi"


@router.get("", response_model=list[OrgOut])
async def list_orgs(user: CurrentUserDep, db: DbDep) -> list[OrgOut]:
    rows = (
        await db.execute(
            text(
                """
                SELECT o.id, o.slug, o.name, o.country_code, o.timezone, o.status, o.created_at
                FROM organizations o
                JOIN memberships m ON m.org_id = o.id
                WHERE m.user_id = :uid AND o.status != 'deleted'
                ORDER BY o.name
                """
            ),
            {"uid": user.id},
        )
    ).all()
    return [OrgOut(**r._mapping) for r in rows]


@router.post("", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
async def create_org(payload: OrgCreate, user: CurrentUserDep, db: DbDep) -> OrgOut:
    existing = (
        await db.execute(
            text("SELECT 1 FROM organizations WHERE slug = :s"),
            {"s": payload.slug},
        )
    ).scalar()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "slug already in use")

    org = (
        await db.execute(
            text(
                """
                INSERT INTO organizations (slug, name, country_code, timezone)
                VALUES (:slug, :name, :cc, :tz)
                RETURNING id, slug, name, country_code, timezone, status, created_at
                """
            ),
            payload.model_dump(),
        )
    ).one()
    await db.execute(
        text(
            "INSERT INTO memberships (org_id, user_id, role, accepted_at) "
            "VALUES (:org, :uid, 'owner', now())"
        ),
        {"org": org.id, "uid": user.id},
    )
    return OrgOut(**org._mapping)


class InviteCreate(BaseModel):
    email: str
    role: Literal["admin", "operator", "viewer"]


@router.post("/{org_id}/invitations", status_code=status.HTTP_201_CREATED)
async def invite(
    org_id: UUID,
    payload: InviteCreate,
    user: CurrentUserDep = Depends(RoleChecker(("owner", "admin"))),
    db: DbDep = None,  # type: ignore[assignment]
) -> dict[str, str]:
    if user.org_id != org_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "wrong org")
    # Persist a pending verification token; email send is the dashboard's job.
    token = (
        await db.execute(
            text(
                """
                INSERT INTO auth_verification_tokens (id, identifier, value, expires_at)
                VALUES (gen_random_uuid()::text, :id, :v, now() + interval '7 days')
                RETURNING id
                """
            ),
            {"id": payload.email, "v": f"invite:{org_id}:{payload.role}"},
        )
    ).scalar_one()
    return {"invitation_token": token}
