"""HTTP middleware stack — installed in order in ``main.create_app``."""

from __future__ import annotations

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .request_context import RequestContextMiddleware
from .ratelimit import RateLimitMiddleware, get_limiter
from .tenant import TenantContextMiddleware
from .pii_redact import PIIRedactionMiddleware


def install_middleware(app: FastAPI) -> None:
    """Order matters: outer-most installed last."""

    # Innermost: PII-strip outbound JSON.
    app.add_middleware(PIIRedactionMiddleware)
    # Tenant context resolution (after auth, sets RLS GUCs).
    app.add_middleware(TenantContextMiddleware)
    # Per-tenant rate-limiting using slowapi.
    app.state.limiter = get_limiter()
    app.add_middleware(RateLimitMiddleware)
    # Outer-most: stamp request id, trace id, structured log binder.
    app.add_middleware(RequestContextMiddleware)


def rate_limit_handler(request, exc):  # type: ignore[no-untyped-def]
    return _rate_limit_exceeded_handler(request, exc)


__all__ = [
    "install_middleware",
    "rate_limit_handler",
    "RateLimitExceeded",
]
