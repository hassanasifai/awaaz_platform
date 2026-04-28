"""Generic outbound integration webhooks — order events back to merchants."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import text

from awaaz_api.deps import DbAdminDep, SettingsDep
from awaaz_api.observability import get_logger, webhook_events_total
from awaaz_api.services.signing import verify_hmac_signature

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])
_log = get_logger("awaaz.webhook.generic")


@router.post("/generic", status_code=status.HTTP_200_OK)
async def receive_generic(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    x_awaaz_signature: Annotated[str | None, Header(alias="X-Awaaz-Signature")] = None,
    x_idempotency_key: Annotated[str | None, Header(alias="X-Idempotency-Key")] = None,
) -> dict[str, str]:
    body = await request.body()
    secret = settings.webhook_hmac_default_key.get_secret_value()
    if not verify_hmac_signature(
        secret=secret, body=body, header=x_awaaz_signature, prefix="sha256="
    ):
        webhook_events_total.labels(source="generic", result="bad_signature").inc()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")

    payload = await request.json()
    event_id = x_idempotency_key or payload.get("idempotency_key") or "unknown"
    await db.execute(
        text(
            """
            INSERT INTO webhook_events (source, event_id, event_type, payload)
            VALUES ('generic', :eid, 'order', :p::jsonb)
            ON CONFLICT (source, event_id) DO NOTHING
            """
        ),
        {"eid": event_id, "p": payload},
    )
    webhook_events_total.labels(source="generic", result="accepted").inc()
    return {"status": "accepted"}
