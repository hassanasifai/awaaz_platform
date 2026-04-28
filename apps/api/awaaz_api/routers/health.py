"""Liveness + readiness."""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from awaaz_api import __version__
from awaaz_api.deps import DbAdminDep
from awaaz_api.observability import get_logger
from awaaz_api.settings import get_settings

router = APIRouter(tags=["health"])
_log = get_logger("awaaz.health")


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/readyz", include_in_schema=False)
async def readyz(db: DbAdminDep, response: Response) -> dict[str, object]:
    """Used by load balancers — true only when DB is reachable."""
    settings = get_settings()
    checks: dict[str, str] = {}
    try:
        r = await db.execute(text("SELECT 1"))
        r.scalar_one()
        checks["postgres"] = "ok"
    except Exception as exc:  # pragma: no cover
        _log.warning("readyz.postgres", error=str(exc))
        checks["postgres"] = f"err:{exc.__class__.__name__}"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if all(v == "ok" for v in checks.values()) else "degraded",
        "version": __version__,
        "env": settings.environment,
        "checks": checks,
    }
