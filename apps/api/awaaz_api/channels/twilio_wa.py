"""Twilio WhatsApp channel."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

import httpx

from .base import InboundMedia, InboundMessage, SentMessage


class TwilioWAChannel:
    name = "twilio_wa"

    def __init__(self, *, account_sid: str, auth_token: str, from_: str) -> None:
        self._sid = account_sid
        self._from = from_  # e.g. "whatsapp:+14155238886"
        self._client = httpx.AsyncClient(
            base_url=f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}",
            timeout=10.0,
            auth=(account_sid, auth_token),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def send_text(
        self, *, to_phone_e164: str, body: str, idempotency_key: str,
        reply_to_message_id: str | None = None,
    ) -> SentMessage:
        data = {"From": self._from, "To": f"whatsapp:{to_phone_e164}", "Body": body[:1600]}
        return await self._post_message(data, idempotency_key)

    async def send_template(
        self, *, to_phone_e164: str, template_name: str, language: str,
        body_params: list[str], idempotency_key: str,
    ) -> SentMessage:
        # Twilio uses ContentSid for approved templates; template_name maps to one.
        data = {
            "From": self._from,
            "To": f"whatsapp:{to_phone_e164}",
            "ContentSid": template_name,
            "ContentVariables": _twilio_content_vars(body_params),
        }
        return await self._post_message(data, idempotency_key)

    async def send_voice_note(
        self, *, to_phone_e164: str, media_url_or_id: str, idempotency_key: str
    ) -> SentMessage:
        data = {
            "From": self._from,
            "To": f"whatsapp:{to_phone_e164}",
            "MediaUrl": media_url_or_id,
        }
        return await self._post_message(data, idempotency_key)

    async def mark_read(self, *, provider_message_id: str) -> None:
        # Twilio does not support marking as read for WA Business.
        return

    async def fetch_media(self, *, media_id_or_url: str) -> tuple[bytes, str]:
        r = await self._client.get(media_id_or_url)
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "application/octet-stream")

    async def _post_message(self, data: dict[str, str], idem: str) -> SentMessage:
        resp = await self._client.post(
            "/Messages.json", data=data, headers={"X-Idempotency-Key": idem}
        )
        resp.raise_for_status()
        body = resp.json()
        return SentMessage(
            provider_message_id=str(body.get("sid", "")),
            accepted_at=datetime.now(timezone.utc),
            raw=body,
        )

    def parse_inbound(self, payload: Mapping[str, Any]) -> list[InboundMessage]:
        # Twilio webhook is form-urlencoded → dict; we receive a single message.
        from_ = str(payload.get("From", "")).removeprefix("whatsapp:")
        to = str(payload.get("To", "")).removeprefix("whatsapp:")
        msg_sid = str(payload.get("MessageSid", ""))
        body = payload.get("Body")
        media_url = payload.get("MediaUrl0")
        if media_url:
            media = InboundMedia(
                s3_key="",
                mime=str(payload.get("MediaContentType0", "application/octet-stream")),
            )
            ctype = (
                "voice"
                if str(payload.get("MediaContentType0", "")).startswith("audio")
                else "image"
            )
        else:
            media = None
            ctype = "text"
        return [
            InboundMessage(
                provider_message_id=msg_sid,
                from_phone_e164=("+" + from_.lstrip("+")) if from_ else "",
                to_phone_e164=("+" + to.lstrip("+")) if to else "",
                content_type=ctype,  # type: ignore[arg-type]
                body=body if isinstance(body, str) else None,
                media=media,
                timestamp=datetime.now(timezone.utc),
                raw=dict(payload),
            )
        ]


def _twilio_content_vars(params: list[str]) -> str:
    import json

    return json.dumps({str(i + 1): v for i, v in enumerate(params)})
