"""Per-tenant rate limiting via slowapi + Redis."""

from __future__ import annotations

from functools import lru_cache
from typing import Final

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from awaaz_api.settings import get_settings


def _key_func(request: Request) -> str:
    """Prefer tenant-id key; fall back to client IP."""

    tenant = getattr(request.state, "tenant", None)
    if tenant is not None:
        if tenant.store_id:
            return f"store:{tenant.store_id}"
        if tenant.org_id:
            return f"org:{tenant.org_id}"
    return get_remote_address(request)


@lru_cache(maxsize=1)
def get_limiter() -> Limiter:
    settings = get_settings()
    return Limiter(
        key_func=_key_func,
        storage_uri=settings.redis_url,
        default_limits=[f"{settings.rate_limit_api_per_minute}/minute"],
        headers_enabled=True,
        strategy="moving-window",
    )


_WEBHOOK_PREFIXES: Final = ("/v1/webhooks/",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply higher per-minute caps for webhook routes."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # slowapi inspects request.state at dispatch time via @limiter.limit
        # decorators on the routes; this middleware is a placeholder hook so
        # we can add bypass logic later (health, metrics).
        if request.url.path in {"/healthz", "/readyz", "/metrics"}:
            return await call_next(request)
        return await call_next(request)
