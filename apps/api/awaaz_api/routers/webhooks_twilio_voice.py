"""Twilio Programmable Voice webhooks (status, AMD, recording)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import text

from awaaz_api.deps import DbAdminDep, SettingsDep
from awaaz_api.observability import get_logger, webhook_events_total

router = APIRouter(prefix="/v1/webhooks/twilio", tags=["webhooks"])
_log = get_logger("awaaz.webhook.twilio_voice")


@router.post("/voice/status", status_code=status.HTTP_200_OK)
async def status_cb(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    x_twilio_signature: Annotated[str | None, Header(alias="X-Twilio-Signature")] = None,
) -> dict[str, str]:
    return await _accept(request, "twilio_voice_status", settings, db, x_twilio_signature)


@router.post("/amd", status_code=status.HTTP_200_OK)
async def amd_cb(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    x_twilio_signature: Annotated[str | None, Header(alias="X-Twilio-Signature")] = None,
) -> dict[str, str]:
    return await _accept(request, "twilio_voice_amd", settings, db, x_twilio_signature)


async def _accept(
    request: Request,
    source: str,
    settings,  # type: ignore[no-untyped-def]
    db,
    x_twilio_signature: str | None,
) -> dict[str, str]:
    body = await request.body()  # noqa: F841 (kept for parity / future audit)
    if x_twilio_signature:
        try:
            from twilio.request_validator import RequestValidator

            validator = RequestValidator(settings.twilio_auth_token.get_secret_value())
            form = (
                await request.form()
                if request.headers.get("content-type", "").startswith(
                    "application/x-www-form-urlencoded"
                )
                else {}
            )
            ok = validator.validate(str(request.url), form, x_twilio_signature)
        except Exception:  # pragma: no cover
            ok = False
        if not ok:
            webhook_events_total.labels(source=source, result="bad_signature").inc()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")
    payload = dict(await request.form())
    event_id = str(payload.get("CallSid") or payload.get("AccountSid"))
    await db.execute(
        text(
            """
            INSERT INTO webhook_events (source, event_id, event_type, payload)
            VALUES (:s, :eid, :et, :p::jsonb)
            ON CONFLICT (source, event_id) DO NOTHING
            """
        ),
        {"s": source, "eid": event_id, "et": payload.get("CallStatus") or "voice", "p": payload},
    )
    webhook_events_total.labels(source=source, result="accepted").inc()
    return {"status": "accepted"}
