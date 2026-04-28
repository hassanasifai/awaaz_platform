"""Async SQLAlchemy engine + session helpers with tenant-context wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from awaaz_api.settings import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    pool_size=_settings.database_pool_size,
    max_overflow=_settings.database_max_overflow,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)

AsyncSessionLocal: Final[async_sessionmaker[AsyncSession]] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Connection-level keys used as Postgres GUCs by RLS predicates and pgcrypto
# helpers.  The encryption keys are set on every checkout so they're always
# available; tenant scope is set per request via ``set_tenant_context``.
# ---------------------------------------------------------------------------
@event.listens_for(engine.sync_engine, "connect")
def _set_default_keys(dbapi_conn, _connection_record) -> None:  # type: ignore[no-untyped-def]
    pii_key = get_settings().pii_encryption_key.get_secret_value()
    phone_key = get_settings().phone_hash_key.get_secret_value()
    cur = dbapi_conn.cursor()
    try:
        # SET ... is session-scoped; safe across pool checkouts.
        cur.execute("SET app.pii_key = %s", (pii_key,))
        cur.execute("SET app.phone_hash_key = %s", (phone_key,))
    finally:
        cur.close()


async def set_tenant_context(
    session: AsyncSession,
    *,
    org_id: UUID | None = None,
    store_id: UUID | None = None,
    user_id: UUID | None = None,
    bypass: bool = False,
) -> None:
    """Apply the multi-tenant GUCs on the current session.

    Postgres ``SET LOCAL`` scopes the change to the current transaction, so
    we always do this inside an explicit ``BEGIN`` (which SQLAlchemy starts on
    first SQL execution).
    """

    await session.execute(
        text(
            "SELECT "
            "set_config('app.current_org', :org, true), "
            "set_config('app.current_store', :store, true), "
            "set_config('app.current_user', :user, true), "
            "set_config('app.bypass_rls', :bypass, true)"
        ),
        {
            "org": str(org_id) if org_id else "",
            "store": str(store_id) if store_id else "",
            "user": str(user_id) if user_id else "",
            "bypass": "on" if bypass else "off",
        },
    )


@asynccontextmanager
async def db_session(
    *,
    org_id: UUID | None = None,
    store_id: UUID | None = None,
    user_id: UUID | None = None,
    bypass: bool = False,
) -> AsyncIterator[AsyncSession]:
    """Open a session with tenant context already set."""

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_context(
                session,
                org_id=org_id,
                store_id=store_id,
                user_id=user_id,
                bypass=bypass,
            )
            yield session


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an unbound session.

    The tenant middleware sets context after this dependency is resolved, in
    a request-scoped middleware so every query inside the handler runs under
    the right RLS predicates.
    """

    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def bypass_rls() -> AsyncIterator[AsyncSession]:
    """Admin-only escape hatch for cross-tenant maintenance jobs."""

    async with db_session(bypass=True) as session:
        yield session
