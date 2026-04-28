"""Tenant context middleware.

Resolves the tenant from one of three sources, in order:
1. ``X-Awaaz-Api-Key`` header (machine clients) → looks up ``api_keys``.
2. Better Auth session cookie → looks up active membership(s).
3. Webhook routes that match a per-source resolver (e.g. Meta phone-number
   ID) — those routers set ``request.state.store_id`` directly and we just
   honour it.

The middleware does NOT short-circuit — auth is enforced inside each router
via ``Depends(...)``.  This middleware's only job is to populate
``request.state.tenant`` so that the dependency layer can use it.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


@dataclass(frozen=True, slots=True)
class TenantContext:
    org_id: UUID | None
    store_id: UUID | None
    user_id: UUID | None
    actor: str  # 'user' | 'api_key' | 'webhook' | 'anonymous'
    bypass_rls: bool = False


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # We don't resolve here — routers do, then they store the resolved
        # context on request.state.tenant.  This keeps the path explicit and
        # auditable and avoids a DB round-trip on health/static/webhook
        # endpoints that don't need it.
        if not hasattr(request.state, "tenant"):
            request.state.tenant = TenantContext(
                org_id=None,
                store_id=None,
                user_id=None,
                actor="anonymous",
            )
        return await call_next(request)
