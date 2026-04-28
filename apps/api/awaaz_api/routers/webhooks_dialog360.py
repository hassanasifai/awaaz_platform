"""360dialog WA webhook receiver."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import text

from awaaz_api.deps import DbAdminDep, SettingsDep
from awaaz_api.observability import get_logger, webhook_events_total
from awaaz_api.services.signing import verify_hmac_signature

router = APIRouter(prefix="/v1/webhooks/wa", tags=["webhooks"])
_log = get_logger("awaaz.webhook.dialog360")


@router.post("/dialog360", status_code=status.HTTP_200_OK)
async def receive(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    x_signature: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
) -> dict[str, str]:
    body = await request.body()
    payload = await request.json()

    secret = settings.dialog360_api_key.get_secret_value()
    if x_signature and not verify_hmac_signature(
        secret=secret, body=body, header=x_signature, prefix="sha256="
    ):
        webhook_events_total.labels(source="dialog360", result="bad_signature").inc()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")

    event_id = _event_id(payload)
    await db.execute(
        text(
            """
            INSERT INTO webhook_events (source, event_id, event_type, payload)
            VALUES ('dialog360', :eid, :et, :p::jsonb)
            ON CONFLICT (source, event_id) DO NOTHING
            """
        ),
        {"eid": event_id, "et": "wa", "p": payload},
    )
    webhook_events_total.labels(source="dialog360", result="accepted").inc()
    return {"status": "accepted"}


def _event_id(payload: dict[str, object]) -> str:
    msgs = payload.get("messages") if isinstance(payload, dict) else None
    if isinstance(msgs, list) and msgs and isinstance(msgs[0], dict):
        msg = msgs[0]
        return f"msg:{msg.get('id', 'unknown')}"
    return "unknown"
