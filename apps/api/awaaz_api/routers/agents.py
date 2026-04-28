"""Agents — versioned per-store conversation agents."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from awaaz_api.deps import CurrentUserDep, DbDep, RoleChecker

router = APIRouter(prefix="/v1/orgs/{org_id}/stores/{store_id}/agents", tags=["agents"])


class AgentOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: str
    current_version_id: UUID | None
    created_at: datetime


class AgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    config: dict[str, Any] = Field(default_factory=dict)


class AgentVersionOut(BaseModel):
    id: UUID
    version: int
    config: dict[str, Any]
    prompt_overrides: dict[str, Any]
    published_at: datetime | None
    created_at: datetime


class AgentVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: dict[str, Any]
    prompt_overrides: dict[str, Any] = Field(default_factory=dict)
    publish: bool = False


@router.get("", response_model=list[AgentOut])
async def list_agents(org_id: UUID, store_id: UUID, db: DbDep) -> list[AgentOut]:
    rows = (
        await db.execute(
            text(
                "SELECT id, name, description, status, current_version_id, created_at "
                "FROM agents WHERE store_id = :sid AND status != 'archived' ORDER BY created_at"
            ),
            {"sid": store_id},
        )
    ).all()
    return [AgentOut(**r._mapping) for r in rows]


@router.post(
    "",
    response_model=AgentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(("owner", "admin")))],
)
async def create_agent(
    org_id: UUID,
    store_id: UUID,
    payload: AgentCreate,
    user: CurrentUserDep,
    db: DbDep,
) -> AgentOut:
    row = (
        await db.execute(
            text(
                """
                INSERT INTO agents (org_id, store_id, name, description, status)
                VALUES (:org, :sid, :name, :desc, 'draft')
                RETURNING id, name, description, status, current_version_id, created_at
                """
            ),
            {
                "org": org_id,
                "sid": store_id,
                "name": payload.name,
                "desc": payload.description,
            },
        )
    ).one()
    # First version
    await db.execute(
        text(
            """
            INSERT INTO agent_versions (org_id, store_id, agent_id, version, config)
            VALUES (:org, :sid, :aid, 1, :cfg)
            """
        ),
        {"org": org_id, "sid": store_id, "aid": row.id, "cfg": payload.config or {}},
    )
    return AgentOut(**row._mapping)


@router.post(
    "/{agent_id}/versions",
    response_model=AgentVersionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(("owner", "admin")))],
)
async def create_agent_version(
    org_id: UUID,
    store_id: UUID,
    agent_id: UUID,
    payload: AgentVersionCreate,
    user: CurrentUserDep,
    db: DbDep,
) -> AgentVersionOut:
    next_version = (
        await db.execute(
            text(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM agent_versions WHERE agent_id = :aid"
            ),
            {"aid": agent_id},
        )
    ).scalar_one()
    row = (
        await db.execute(
            text(
                """
                INSERT INTO agent_versions
                    (org_id, store_id, agent_id, version, config, prompt_overrides,
                     published_at, published_by)
                VALUES (:org, :sid, :aid, :v, :cfg, :po,
                        CASE WHEN :pub THEN now() END,
                        CASE WHEN :pub THEN :uid END)
                RETURNING id, version, config, prompt_overrides, published_at, created_at
                """
            ),
            {
                "org": org_id,
                "sid": store_id,
                "aid": agent_id,
                "v": next_version,
                "cfg": payload.config,
                "po": payload.prompt_overrides,
                "pub": payload.publish,
                "uid": user.id,
            },
        )
    ).one()
    if payload.publish:
        await db.execute(
            text("UPDATE agents SET current_version_id = :vid, status = 'active' WHERE id = :aid"),
            {"vid": row.id, "aid": agent_id},
        )
    return AgentVersionOut(**row._mapping)
