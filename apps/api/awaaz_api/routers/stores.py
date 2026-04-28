"""Store CRUD + per-store WhatsApp / agent settings."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from awaaz_api.deps import CurrentUserDep, DbDep, RoleChecker

router = APIRouter(prefix="/v1/orgs/{org_id}/stores", tags=["stores"])


class StoreOut(BaseModel):
    id: UUID
    org_id: UUID
    slug: str
    name: str
    brand_name: str
    platform: str
    timezone: str
    currency: str
    wa_provider: str
    wa_phone_number_id: str | None
    voice_enabled: bool
    voice_caller_id: str | None
    per_conversation_cost_cap_usd: float
    per_call_cost_cap_usd: float
    monthly_budget_usd: float | None
    status: str
    created_at: datetime
    agent_config: dict[str, Any]


class StoreCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(..., min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(..., min_length=1, max_length=200)
    brand_name: str = Field(..., min_length=1, max_length=200)
    platform: Literal["shopify", "woocommerce", "custom", "manual"] = "manual"
    timezone: str = "Asia/Karachi"
    currency: str = "PKR"


class StoreUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=200)
    brand_name: str | None = Field(default=None, max_length=200)
    timezone: str | None = None
    currency: str | None = None
    voice_enabled: bool | None = None
    voice_caller_id: str | None = None
    monthly_budget_usd: float | None = None
    per_conversation_cost_cap_usd: float | None = None
    per_call_cost_cap_usd: float | None = None
    agent_config: dict[str, Any] | None = None


@router.get("", response_model=list[StoreOut])
async def list_stores(
    org_id: UUID,
    user: CurrentUserDep,
    db: DbDep,
) -> list[StoreOut]:
    if user.org_id != org_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "wrong org")
    rows = (
        await db.execute(
            text(
                """
                SELECT id, org_id, slug, name, brand_name, platform, timezone,
                       currency, wa_provider, wa_phone_number_id, voice_enabled,
                       voice_caller_id, per_conversation_cost_cap_usd,
                       per_call_cost_cap_usd, monthly_budget_usd, status,
                       created_at, agent_config
                FROM stores
                WHERE org_id = :org AND status != 'deleted'
                ORDER BY name
                """
            ),
            {"org": org_id},
        )
    ).all()
    return [StoreOut(**r._mapping) for r in rows]


@router.post(
    "",
    response_model=StoreOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(("owner", "admin")))],
)
async def create_store(
    org_id: UUID,
    payload: StoreCreate,
    user: CurrentUserDep,
    db: DbDep,
) -> StoreOut:
    if user.org_id != org_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "wrong org")
    row = (
        await db.execute(
            text(
                """
                INSERT INTO stores (org_id, slug, name, brand_name, platform, timezone, currency)
                VALUES (:org, :slug, :name, :brand, :platform, :tz, :cur)
                RETURNING id, org_id, slug, name, brand_name, platform, timezone, currency,
                          wa_provider, wa_phone_number_id, voice_enabled, voice_caller_id,
                          per_conversation_cost_cap_usd, per_call_cost_cap_usd,
                          monthly_budget_usd, status, created_at, agent_config
                """
            ),
            {
                "org": org_id,
                "slug": payload.slug,
                "name": payload.name,
                "brand": payload.brand_name,
                "platform": payload.platform,
                "tz": payload.timezone,
                "cur": payload.currency,
            },
        )
    ).one()
    return StoreOut(**row._mapping)


@router.patch(
    "/{store_id}",
    response_model=StoreOut,
    dependencies=[Depends(RoleChecker(("owner", "admin")))],
)
async def update_store(
    org_id: UUID,
    store_id: UUID,
    payload: StoreUpdate,
    user: CurrentUserDep,
    db: DbDep,
) -> StoreOut:
    if user.org_id != org_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "wrong org")
    fields = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no fields to update")
    set_sql = ", ".join(f"{k} = :{k}" for k in fields)
    fields["org"] = org_id
    fields["sid"] = store_id
    row = (
        await db.execute(
            text(
                f"""
                UPDATE stores SET {set_sql}, updated_at = now()
                WHERE id = :sid AND org_id = :org AND status != 'deleted'
                RETURNING id, org_id, slug, name, brand_name, platform, timezone, currency,
                          wa_provider, wa_phone_number_id, voice_enabled, voice_caller_id,
                          per_conversation_cost_cap_usd, per_call_cost_cap_usd,
                          monthly_budget_usd, status, created_at, agent_config
                """
            ),
            fields,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "store not found")
    return StoreOut(**row._mapping)


@router.delete(
    "/{store_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RoleChecker(("owner",)))],
)
async def delete_store(org_id: UUID, store_id: UUID, user: CurrentUserDep, db: DbDep) -> None:
    if user.org_id != org_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "wrong org")
    await db.execute(
        text(
            "UPDATE stores SET status = 'deleted', updated_at = now() "
            "WHERE id = :sid AND org_id = :org"
        ),
        {"sid": store_id, "org": org_id},
    )
