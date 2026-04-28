"""Shopify webhook receiver — orders + GDPR mandatory webhooks."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import text

from awaaz_api.deps import DbAdminDep, SettingsDep
from awaaz_api.observability import get_logger, webhook_events_total
from awaaz_api.services.signing import verify_shopify_signature

router = APIRouter(prefix="/v1/webhooks/shopify", tags=["webhooks"])
_log = get_logger("awaaz.webhook.shopify")


async def _accept_shopify(
    request: Request,
    settings,  # type: ignore[no-untyped-def]
    db,
    *,
    topic: str,
    x_shop_domain: str | None,
    x_topic: str | None,
    x_event_id: str | None,
    x_signature: str | None,
) -> tuple[dict[str, Any], str | None]:
    body = await request.body()
    secret = settings.shopify_api_secret.get_secret_value()
    if not verify_shopify_signature(api_secret=secret, body=body, header=x_signature):
        webhook_events_total.labels(source="shopify", result="bad_signature").inc()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")
    payload = await request.json()
    event_id = x_event_id or f"{x_topic}:{payload.get('id', 'unknown')}"
    await db.execute(
        text(
            """
            INSERT INTO webhook_events (source, event_id, event_type, payload)
            VALUES ('shopify', :eid, :et, :p::jsonb)
            ON CONFLICT (source, event_id) DO NOTHING
            """
        ),
        {"eid": event_id, "et": x_topic or topic, "p": payload},
    )
    webhook_events_total.labels(source="shopify", result="accepted").inc()
    return payload, x_shop_domain


@router.post("/orders/create")
async def orders_create(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    x_shopify_shop_domain: Annotated[str | None, Header(alias="X-Shopify-Shop-Domain")] = None,
    x_shopify_topic: Annotated[str | None, Header(alias="X-Shopify-Topic")] = None,
    x_shopify_webhook_id: Annotated[str | None, Header(alias="X-Shopify-Webhook-Id")] = None,
    x_shopify_hmac_sha256: Annotated[str | None, Header(alias="X-Shopify-Hmac-Sha256")] = None,
) -> dict[str, str]:
    await _accept_shopify(
        request, settings, db,
        topic="orders/create",
        x_shop_domain=x_shopify_shop_domain,
        x_topic=x_shopify_topic,
        x_event_id=x_shopify_webhook_id,
        x_signature=x_shopify_hmac_sha256,
    )
    return {"status": "accepted"}


@router.post("/orders/updated")
async def orders_updated(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    x_shopify_shop_domain: Annotated[str | None, Header(alias="X-Shopify-Shop-Domain")] = None,
    x_shopify_topic: Annotated[str | None, Header(alias="X-Shopify-Topic")] = None,
    x_shopify_webhook_id: Annotated[str | None, Header(alias="X-Shopify-Webhook-Id")] = None,
    x_shopify_hmac_sha256: Annotated[str | None, Header(alias="X-Shopify-Hmac-Sha256")] = None,
) -> dict[str, str]:
    await _accept_shopify(
        request, settings, db,
        topic="orders/updated",
        x_shop_domain=x_shopify_shop_domain,
        x_topic=x_shopify_topic,
        x_event_id=x_shopify_webhook_id,
        x_signature=x_shopify_hmac_sha256,
    )
    return {"status": "accepted"}


@router.post("/orders/cancelled")
async def orders_cancelled(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    x_shopify_shop_domain: Annotated[str | None, Header(alias="X-Shopify-Shop-Domain")] = None,
    x_shopify_topic: Annotated[str | None, Header(alias="X-Shopify-Topic")] = None,
    x_shopify_webhook_id: Annotated[str | None, Header(alias="X-Shopify-Webhook-Id")] = None,
    x_shopify_hmac_sha256: Annotated[str | None, Header(alias="X-Shopify-Hmac-Sha256")] = None,
) -> dict[str, str]:
    await _accept_shopify(
        request, settings, db,
        topic="orders/cancelled",
        x_shop_domain=x_shopify_shop_domain,
        x_topic=x_shopify_topic,
        x_event_id=x_shopify_webhook_id,
        x_signature=x_shopify_hmac_sha256,
    )
    return {"status": "accepted"}


@router.post("/app/uninstalled")
async def app_uninstalled(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    x_shopify_shop_domain: Annotated[str | None, Header(alias="X-Shopify-Shop-Domain")] = None,
    x_shopify_topic: Annotated[str | None, Header(alias="X-Shopify-Topic")] = None,
    x_shopify_webhook_id: Annotated[str | None, Header(alias="X-Shopify-Webhook-Id")] = None,
    x_shopify_hmac_sha256: Annotated[str | None, Header(alias="X-Shopify-Hmac-Sha256")] = None,
) -> dict[str, str]:
    await _accept_shopify(
        request, settings, db,
        topic="app/uninstalled",
        x_shop_domain=x_shopify_shop_domain,
        x_topic=x_shopify_topic,
        x_event_id=x_shopify_webhook_id,
        x_signature=x_shopify_hmac_sha256,
    )
    return {"status": "accepted"}


# ---------------- GDPR mandatory webhooks (60-day SLAs)
@router.post("/customers/data_request")
async def customers_data_request(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    x_shopify_shop_domain: Annotated[str | None, Header(alias="X-Shopify-Shop-Domain")] = None,
    x_shopify_topic: Annotated[str | None, Header(alias="X-Shopify-Topic")] = None,
    x_shopify_webhook_id: Annotated[str | None, Header(alias="X-Shopify-Webhook-Id")] = None,
    x_shopify_hmac_sha256: Annotated[str | None, Header(alias="X-Shopify-Hmac-Sha256")] = None,
) -> dict[str, str]:
    await _accept_shopify(
        request, settings, db,
        topic="customers/data_request",
        x_shop_domain=x_shopify_shop_domain,
        x_topic=x_shopify_topic,
        x_event_id=x_shopify_webhook_id,
        x_signature=x_shopify_hmac_sha256,
    )
    return {"status": "accepted"}


@router.post("/customers/redact")
async def customers_redact(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    x_shopify_shop_domain: Annotated[str | None, Header(alias="X-Shopify-Shop-Domain")] = None,
    x_shopify_topic: Annotated[str | None, Header(alias="X-Shopify-Topic")] = None,
    x_shopify_webhook_id: Annotated[str | None, Header(alias="X-Shopify-Webhook-Id")] = None,
    x_shopify_hmac_sha256: Annotated[str | None, Header(alias="X-Shopify-Hmac-Sha256")] = None,
) -> dict[str, str]:
    await _accept_shopify(
        request, settings, db,
        topic="customers/redact",
        x_shop_domain=x_shopify_shop_domain,
        x_topic=x_shopify_topic,
        x_event_id=x_shopify_webhook_id,
        x_signature=x_shopify_hmac_sha256,
    )
    return {"status": "accepted"}


@router.post("/shop/redact")
async def shop_redact(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    x_shopify_shop_domain: Annotated[str | None, Header(alias="X-Shopify-Shop-Domain")] = None,
    x_shopify_topic: Annotated[str | None, Header(alias="X-Shopify-Topic")] = None,
    x_shopify_webhook_id: Annotated[str | None, Header(alias="X-Shopify-Webhook-Id")] = None,
    x_shopify_hmac_sha256: Annotated[str | None, Header(alias="X-Shopify-Hmac-Sha256")] = None,
) -> dict[str, str]:
    await _accept_shopify(
        request, settings, db,
        topic="shop/redact",
        x_shop_domain=x_shopify_shop_domain,
        x_topic=x_shopify_topic,
        x_event_id=x_shopify_webhook_id,
        x_signature=x_shopify_hmac_sha256,
    )
    return {"status": "accepted"}
