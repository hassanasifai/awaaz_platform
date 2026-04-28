"""360dialog WA Cloud-API channel.

Surface mirrors :class:`MetaCloudWAChannel` but signs requests with a
``D360-API-KEY`` header instead of an OAuth bearer token.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

import httpx

from awaaz_api.observability import get_logger

from .base import (
    InboundContentType,
    InboundMedia,
    InboundMessage,
    SentMessage,
)
from .meta_cloud import _decode_message, _strip_plus  # type: ignore[attr-defined]

_log = get_logger("awaaz.channel.dialog360")


class Dialog360WAChannel:
    name = "dialog360"

    def __init__(self, *, api_key: str, base_url: str, timeout: float = 10.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"D360-API-KEY": api_key, "Content-Type": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def send_text(
        self, *, to_phone_e164: str, body: str, idempotency_key: str,
        reply_to_message_id: str | None = None,
    ) -> SentMessage:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": _strip_plus(to_phone_e164),
            "type": "text",
            "text": {"body": body[:4096]},
        }
        if reply_to_message_id:
            payload["context"] = {"message_id": reply_to_message_id}
        return await self._send(payload, idempotency_key)

    async def send_template(
        self, *, to_phone_e164: str, template_name: str, language: str,
        body_params: list[str], idempotency_key: str,
    ) -> SentMessage:
        components: list[dict[str, Any]] = []
        if body_params:
            components.append(
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": p} for p in body_params
                    ],
                }
            )
        payload = {
            "messaging_product": "whatsapp",
            "to": _strip_plus(to_phone_e164),
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": components,
            },
        }
        return await self._send(payload, idempotency_key)

    async def send_voice_note(
        self, *, to_phone_e164: str, media_url_or_id: str, idempotency_key: str
    ) -> SentMessage:
        media = (
            {"link": media_url_or_id}
            if media_url_or_id.startswith("http")
            else {"id": media_url_or_id}
        )
        payload = {
            "messaging_product": "whatsapp",
            "to": _strip_plus(to_phone_e164),
            "type": "audio",
            "audio": media,
        }
        return await self._send(payload, idempotency_key)

    async def mark_read(self, *, provider_message_id: str) -> None:
        try:
            await self._client.post(
                "/messages",
                json={
                    "messaging_product": "whatsapp",
                    "status": "read",
                    "message_id": provider_message_id,
                },
            )
        except httpx.HTTPError as exc:
            _log.warning("dialog360.mark_read.fail", error=str(exc))

    async def fetch_media(self, *, media_id_or_url: str) -> tuple[bytes, str]:
        if media_id_or_url.startswith("http"):
            r = await self._client.get(media_id_or_url)
        else:
            meta = await self._client.get(f"/{media_id_or_url}")
            meta.raise_for_status()
            data = meta.json()
            r = await self._client.get(data["url"])
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "application/octet-stream")

    async def _send(self, payload: dict[str, Any], idem: str) -> SentMessage:
        resp = await self._client.post(
            "/messages", json=payload, headers={"X-Idempotency-Key": idem}
        )
        if resp.status_code >= 400:
            raise httpx.HTTPError(f"360dialog {resp.status_code}: {resp.text}")
        data = resp.json()
        msg_id = (data.get("messages") or [{}])[0].get("id", "")
        return SentMessage(
            provider_message_id=msg_id,
            accepted_at=datetime.now(timezone.utc),
            raw=data,
        )

    def parse_inbound(self, payload: Mapping[str, Any]) -> list[InboundMessage]:
        messages: list[InboundMessage] = []
        msgs_raw = payload.get("messages") if isinstance(payload, dict) else None
        contacts = payload.get("contacts") if isinstance(payload, dict) else None  # type: ignore[union-attr]
        if not msgs_raw:
            return messages
        to_phone = ""
        if contacts and isinstance(contacts, list) and contacts:
            to_phone = "+" + str(contacts[0].get("wa_id", "")).lstrip("+")
        for msg in msgs_raw:
            content_type, body, media = _decode_message(msg)  # reuse Meta parser
            messages.append(
                InboundMessage(
                    provider_message_id=str(msg.get("id", "")),
                    from_phone_e164="+" + str(msg.get("from", "")).lstrip("+"),
                    to_phone_e164=to_phone,
                    content_type=content_type,
                    body=body,
                    media=media,
                    timestamp=datetime.fromtimestamp(
                        int(msg.get("timestamp", 0)), tz=timezone.utc
                    ),
                    raw=dict(msg),
                )
            )
        return messages
