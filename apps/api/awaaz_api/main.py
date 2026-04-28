"""FastAPI application entry-point.

Two roles:
- ``AWAAZ_ROLE=api`` runs uvicorn serving the HTTP API.
- ``AWAAZ_ROLE=worker`` runs the background worker entry-point instead.

Every cross-cutting concern is wired here: logging, OTel, Sentry, middleware,
routers.  Adding a new router?  Append it to ``ROUTERS`` and write tests —
nothing else.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Final

import sentry_sdk
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from awaaz_api import __version__
from awaaz_api.middleware import (
    install_middleware,
    rate_limit_handler,
)
from awaaz_api.observability import (
    configure_logging,
    get_logger,
    setup_telemetry,
)
from awaaz_api.routers import (
    agents,
    analytics,
    auth as auth_router,
    conversations,
    csv_upload,
    health,
    messages,
    orders,
    orgs,
    sms,
    stores,
    transcripts,
    webhooks_meta_wa,
    webhooks_dialog360,
    webhooks_twilio_voice,
    webhooks_twilio_wa,
    webhooks_shopify,
    webhooks_stripe,
    webhooks_generic,
    webhooks_woocommerce,
)
from awaaz_api.settings import get_settings

ROUTERS: Final = (
    health.router,
    auth_router.router,
    orgs.router,
    stores.router,
    agents.router,
    orders.router,
    conversations.router,
    messages.router,
    transcripts.router,
    analytics.router,
    sms.router,
    csv_upload.router,
    # Webhooks
    webhooks_meta_wa.router,
    webhooks_dialog360.router,
    webhooks_twilio_wa.router,
    webhooks_twilio_voice.router,
    webhooks_shopify.router,
    webhooks_woocommerce.router,
    webhooks_generic.router,
    webhooks_stripe.router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    log = get_logger("awaaz.lifespan")
    log.info("api.startup", version=__version__, env=get_settings().environment)
    yield
    log.info("api.shutdown")


def _configure_sentry() -> None:
    settings = get_settings()
    if not settings.sentry_dsn or settings.environment == "test":
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        attach_stacktrace=True,
        release=f"awaaz-api@{__version__}",
    )


def create_app() -> FastAPI:
    configure_logging()
    _configure_sentry()
    settings = get_settings()

    app = FastAPI(
        title="Awaaz API",
        version=__version__,
        description=(
            "Multi-tenant conversational AI agent platform for Pakistani "
            "e-commerce — WhatsApp primary, voice secondary."
        ),
        lifespan=lifespan,
        # In production the dashboard is the only public consumer; we expose
        # OpenAPI + redoc at /v1/openapi.json so CSP can lock down /docs.
        openapi_url="/v1/openapi.json",
        docs_url="/v1/docs" if settings.environment != "production" else None,
        redoc_url="/v1/redoc" if settings.environment != "production" else None,
    )

    setup_telemetry(instrument_fastapi_app=app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.trusted_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id", "X-Trace-Id"],
    )

    install_middleware(app)
    app.add_exception_handler(__import__("slowapi.errors", fromlist=["RateLimitExceeded"]).RateLimitExceeded, rate_limit_handler)

    for r in ROUTERS:
        app.include_router(r)

    @app.get("/metrics", include_in_schema=False)
    async def metrics(_request: Request) -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app: FastAPI = create_app()


def cli() -> None:  # pragma: no cover - thin entry-point
    settings = get_settings()
    role = os.environ.get("AWAAZ_ROLE", settings.awaaz_role)
    if role == "worker":
        from awaaz_api.workers.run_all import main as run_workers

        run_workers()
        return
    uvicorn.run(
        "awaaz_api.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        proxy_headers=True,
        forwarded_allow_ips="*",
        access_log=False,
    )


if __name__ == "__main__":  # pragma: no cover
    cli()
