"""Database access layer.

Convention: every repository takes a ``store_id`` (or ``org_id``) for
defense-in-depth filtering on top of Postgres RLS.  No repository ever issues
a query without one of those tenant scopes — there is a CI grep that fails the
build if any ``select(...)`` is missing a tenant predicate.
"""

from __future__ import annotations

from .db import (
    AsyncSessionLocal,
    bypass_rls,
    db_session,
    engine,
    get_session,
    set_tenant_context,
)
from .encryption import (
    PIIVault,
    encrypt_pii,
    hash_phone,
    normalize_phone,
)

__all__ = [
    "AsyncSessionLocal",
    "engine",
    "db_session",
    "get_session",
    "set_tenant_context",
    "bypass_rls",
    "encrypt_pii",
    "hash_phone",
    "normalize_phone",
    "PIIVault",
]
