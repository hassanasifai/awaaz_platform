"""Meta WhatsApp Cloud API webhook receiver.

Verification and message handling per the WhatsApp Business Platform docs:
https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request, status
from sqlalchemy import text

from awaaz_api.deps import DbAdminDep, SettingsDep
from awaaz_api.observability import get_logger, webhook_events_total
from awaaz_api.services.signing import verify_meta_signature

router = APIRouter(prefix="/v1/webhooks/wa", tags=["webhooks"])
_log = get_logger("awaaz.webhook.meta")


@router.get("/meta")
async def verify(
    settings: SettingsDep,
    hub_mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    hub_verify_token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    hub_challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> int:
    """Meta verification handshake — echo the challenge if our token matches."""
    expected = settings.meta_wa_verify_token.get_secret_value()
    if hub_mode != "subscribe" or hub_verify_token != expected or not hub_challenge:
        webhook_events_total.labels(source="meta_wa", result="verify_failed").inc()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "verification failed")
    webhook_events_total.labels(source="meta_wa", result="verify_ok").inc()
    return int(hub_challenge)


@router.post("/meta", status_code=status.HTTP_200_OK)
async def receive(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    background: BackgroundTasks,
    x_hub_signature_256: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
) -> dict[str, str]:
    body = await request.body()
    payload = await request.json()

    # Resolve store from phone_number_id BEFORE signature check so per-store
    # secrets can be used.  If the store has no app secret configured, fall
    # back to the global env-var default.
    phone_number_id = _extract_phone_number_id(payload)
    store_id, app_secret = await _resolve_store(db, phone_number_id, settings)
    if not verify_meta_signature(
        app_secret=app_secret,
        body=body,
        header=x_hub_signature_256,
    ):
        webhook_events_total.labels(source="meta_wa", result="bad_signature").inc()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")

    event_id = _payload_event_id(payload)
    try:
        await db.execute(
            text(
                """
                INSERT INTO webhook_events (source, event_id, event_type, store_id, payload)
                VALUES ('meta_wa', :eid, :etype, :sid, :p::jsonb)
                """
            ),
            {
                "eid": event_id,
                "etype": _extract_event_type(payload),
                "sid": store_id,
                "p": payload,
            },
        )
    except Exception:  # idempotent: duplicate event id is fine
        webhook_events_total.labels(source="meta_wa", result="duplicate").inc()
        return {"status": "duplicate"}

    background.add_task(
        _enqueue_for_processing,
        event_id=event_id,
        store_id=store_id,
        payload=payload,
    )
    webhook_events_total.labels(source="meta_wa", result="accepted").inc()
    return {"status": "accepted"}


# ---------------------------------------------------------------------------
def _extract_phone_number_id(payload: dict[str, Any]) -> str | None:
    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]
        return change["value"]["metadata"]["phone_number_id"]
    except (KeyError, IndexError, TypeError):
        return None


def _extract_event_type(payload: dict[str, Any]) -> str:
    try:
        change = payload["entry"][0]["changes"][0]
        if "value" in change and "messages" in change["value"]:
            return "message"
        if "value" in change and "statuses" in change["value"]:
            return "status"
        return change.get("field", "unknown")
    except (KeyError, IndexError, TypeError):
        return "unknown"


def _payload_event_id(payload: dict[str, Any]) -> str:
    try:
        change = payload["entry"][0]["changes"][0]["value"]
        msgs = change.get("messages") or []
        if msgs and "id" in msgs[0]:
            return f"msg:{msgs[0]['id']}"
        statuses = change.get("statuses") or []
        if statuses and "id" in statuses[0]:
            ts = statuses[0].get("timestamp", "0")
            return f"status:{statuses[0]['id']}:{ts}"
        return f"entry:{payload['entry'][0].get('id', '?')}"
    except (KeyError, IndexError, TypeError):
        return "unknown"


async def _resolve_store(
    db, phone_number_id: str | None, settings,  # type: ignore[no-untyped-def]
) -> tuple[UUID | None, str]:
    if not phone_number_id:
        return None, settings.meta_wa_app_secret.get_secret_value()
    row = (
        await db.execute(
            text(
                """
                SELECT id, app_decrypt_pii(wa_app_secret_enc) AS app_secret
                FROM stores
                WHERE wa_phone_number_id = :p
                  AND status = 'active'
                LIMIT 1
                """
            ),
            {"p": phone_number_id},
        )
    ).first()
    if row is None:
        return None, settings.meta_wa_app_secret.get_secret_value()
    secret = row.app_secret or settings.meta_wa_app_secret.get_secret_value()
    return row.id, secret


async def _enqueue_for_processing(  # pragma: no cover - background
    *, event_id: str, store_id: UUID | None, payload: dict[str, Any]
) -> None:
    """Hand the event to the FSM-runner worker.

    The worker reads ``webhook_events`` for any unprocessed rows; this stub
    is a hook for synchronous test-mode dispatch.
    """
    _log.info(
        "wa.event.queued",
        event_id=event_id,
        store_id=str(store_id) if store_id else None,
    )
