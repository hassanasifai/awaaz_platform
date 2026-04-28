"""FastAPI dependencies.

These are the building blocks the routers compose: ``current_user``,
``current_tenant``, ``db_for_tenant``, ``store_scope``, ``api_key_auth``.

Every router that needs the database goes through ``db_for_tenant`` so that
RLS GUCs are set before the first query runs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from awaaz_api.middleware.tenant import TenantContext
from awaaz_api.persistence import AsyncSessionLocal, set_tenant_context
from awaaz_api.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: UUID
    org_id: UUID
    role: str


def settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_dep)]


def get_tenant(request: Request) -> TenantContext:
    return request.state.tenant  # populated by middleware/router auth


TenantDep = Annotated[TenantContext, Depends(get_tenant)]


async def require_user(request: Request) -> CurrentUser:
    """Raise 401 if no authenticated user is present.

    Most user-facing routes go through this.  CVE-2025-29927 mitigation: this
    must be invoked inside the route handler, not only in middleware — the
    dashboard equivalent re-checks in Server Components.
    """

    tenant: TenantContext = request.state.tenant
    if tenant.actor != "user" or tenant.user_id is None or tenant.org_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    membership_role = getattr(request.state, "membership_role", None)
    if membership_role is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no organization membership")
    return CurrentUser(id=tenant.user_id, org_id=tenant.org_id, role=membership_role)


CurrentUserDep = Annotated[CurrentUser, Depends(require_user)]


async def require_role(*allowed: str) -> "RoleChecker":
    return RoleChecker(allowed)


class RoleChecker:
    """Use ``Depends(RoleChecker(("owner","admin")))`` on a route to gate it."""

    def __init__(self, allowed: tuple[str, ...]) -> None:
        self.allowed = set(allowed)

    def __call__(self, current: CurrentUser = Depends(require_user)) -> CurrentUser:  # type: ignore[assignment]
        if current.role not in self.allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"role {current.role!r} not allowed (need one of {sorted(self.allowed)})",
            )
        return current


async def db_for_tenant(
    request: Request,
) -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession with RLS GUCs already populated."""

    tenant: TenantContext = request.state.tenant
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_context(
                session,
                org_id=tenant.org_id,
                store_id=tenant.store_id,
                user_id=tenant.user_id,
                bypass=tenant.bypass_rls,
            )
            yield session


DbDep = Annotated[AsyncSession, Depends(db_for_tenant)]


async def db_admin() -> AsyncIterator[AsyncSession]:
    """Bypass RLS — only for cross-tenant maintenance routes."""

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(text("SET LOCAL app.bypass_rls = 'on'"))
            yield session


DbAdminDep = Annotated[AsyncSession, Depends(db_admin)]
