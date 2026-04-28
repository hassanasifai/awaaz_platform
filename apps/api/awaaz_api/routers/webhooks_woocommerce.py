"""WooCommerce webhook receiver — accepts the wp-json/wc/v3 outgoing webhook
format and the custom Awaaz plugin format, signed with HMAC-SHA256.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import text

from awaaz_api.deps import DbAdminDep, SettingsDep
from awaaz_api.observability import get_logger, webhook_events_total
from awaaz_api.services.signing import verify_hmac_signature

router = APIRouter(prefix="/v1/webhooks/woo", tags=["webhooks"])
_log = get_logger("awaaz.webhook.woo")


@router.post("", status_code=status.HTTP_200_OK)
async def receive(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    x_wc_webhook_signature: Annotated[
        str | None, Header(alias="X-WC-Webhook-Signature")
    ] = None,
    x_awaaz_signature: Annotated[
        str | None, Header(alias="X-Awaaz-Signature")
    ] = None,
    x_wc_webhook_topic: Annotated[
        str | None, Header(alias="X-WC-Webhook-Topic")
    ] = None,
    x_wc_webhook_id: Annotated[str | None, Header(alias="X-WC-Webhook-Id")] = None,
) -> dict[str, str]:
    body = await request.body()
    secret = settings.webhook_hmac_default_key.get_secret_value()
    sig = x_wc_webhook_signature or x_awaaz_signature
    encoding = "base64" if x_wc_webhook_signature else "hex"
    prefix = None if x_wc_webhook_signature else "sha256="
    if not verify_hmac_signature(
        secret=secret, body=body, header=sig, encoding=encoding, prefix=prefix
    ):
        webhook_events_total.labels(source="woocommerce", result="bad_signature").inc()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")
    payload = await request.json()
    event_id = (
        x_wc_webhook_id
        or f"{x_wc_webhook_topic or 'woo'}:{payload.get('id', 'unknown')}"
    )
    await db.execute(
        text(
            """
            INSERT INTO webhook_events (source, event_id, event_type, payload)
            VALUES ('woocommerce', :eid, :et, :p::jsonb)
            ON CONFLICT (source, event_id) DO NOTHING
            """
        ),
        {"eid": event_id, "et": x_wc_webhook_topic or "order", "p": payload},
    )
    webhook_events_total.labels(source="woocommerce", result="accepted").inc()
    return {"status": "accepted"}
