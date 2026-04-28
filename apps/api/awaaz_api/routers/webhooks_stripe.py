"""Stripe webhook receiver — uses Stripe's own signature scheme."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import text

from awaaz_api.deps import DbAdminDep, SettingsDep
from awaaz_api.observability import get_logger, webhook_events_total

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])
_log = get_logger("awaaz.webhook.stripe")


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def receive_stripe(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict[str, str]:
    if not stripe_signature:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing signature")

    body = await request.body()
    try:
        import stripe

        event = stripe.Webhook.construct_event(
            payload=body,
            sig_header=stripe_signature,
            secret=settings.stripe_webhook_secret.get_secret_value(),
        )
    except Exception as exc:  # pragma: no cover - delegated to Stripe SDK
        webhook_events_total.labels(source="stripe", result="bad_signature").inc()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"bad signature: {exc}") from exc

    await db.execute(
        text(
            """
            INSERT INTO webhook_events (source, event_id, event_type, payload)
            VALUES ('stripe', :eid, :et, :p::jsonb)
            ON CONFLICT (source, event_id) DO NOTHING
            """
        ),
        {"eid": event["id"], "et": event["type"], "p": dict(event)},
    )
    webhook_events_total.labels(source="stripe", result="accepted").inc()
    return {"status": "accepted"}
