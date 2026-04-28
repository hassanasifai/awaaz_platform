"""Twilio WhatsApp webhook receiver."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import text

from awaaz_api.deps import DbAdminDep, SettingsDep
from awaaz_api.observability import get_logger, webhook_events_total
from awaaz_api.services.signing import verify_hmac_signature

router = APIRouter(prefix="/v1/webhooks/wa", tags=["webhooks"])
_log = get_logger("awaaz.webhook.twilio_wa")


@router.post("/twilio", status_code=status.HTTP_200_OK)
async def receive(
    request: Request,
    settings: SettingsDep,
    db: DbAdminDep,
    x_twilio_signature: Annotated[str | None, Header(alias="X-Twilio-Signature")] = None,
) -> dict[str, str]:
    """Twilio signs `URL + concatenation of POST params (sorted)`.

    For body-as-form we delegate to the Twilio SDK's RequestValidator at the
    consumer side; here we only HMAC-verify the raw body for the JSON variant.
    Twilio's classic webhook is form-encoded, so we accept either.
    """

    body = await request.body()
    secret = settings.twilio_wa_auth_token.get_secret_value()

    if x_twilio_signature:
        # The classic Twilio signature scheme requires URL + sorted form params.
        # We use the SDK to avoid re-implementing it.
        try:
            from twilio.request_validator import RequestValidator

            validator = RequestValidator(secret)
            url = str(request.url)
            form = await request.form() if request.headers.get("content-type", "").startswith(
                "application/x-www-form-urlencoded"
            ) else {}
            ok = validator.validate(url, form, x_twilio_signature)
        except Exception:  # pragma: no cover - SDK absent or odd input
            ok = verify_hmac_signature(
                secret=secret, body=body, header=x_twilio_signature, encoding="base64", prefix=None
            )
        if not ok:
            webhook_events_total.labels(source="twilio_wa", result="bad_signature").inc()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")

    payload = (
        await request.json()
        if request.headers.get("content-type", "").startswith("application/json")
        else dict(await request.form())
    )
    event_id = str(payload.get("MessageSid") or payload.get("SmsSid") or payload.get("AccountSid"))

    await db.execute(
        text(
            """
            INSERT INTO webhook_events (source, event_id, event_type, payload)
            VALUES ('twilio_wa', :eid, 'wa', :p::jsonb)
            ON CONFLICT (source, event_id) DO NOTHING
            """
        ),
        {"eid": event_id, "p": payload},
    )
    webhook_events_total.labels(source="twilio_wa", result="accepted").inc()
    return {"status": "accepted"}
