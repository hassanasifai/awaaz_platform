"""Meta WhatsApp Cloud API implementation.

Docs:
- send messages: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
- inbound webhook payload: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from awaaz_api.observability import get_logger

from .base import (
    InboundContentType,
    InboundMedia,
    InboundMessage,
    SentMessage,
)

_log = get_logger("awaaz.channel.meta")


class MetaCloudWAChannel:
    name = "meta_cloud"

    def __init__(
        self,
        *,
        access_token: str,
        phone_number_id: str,
        api_version: str = "v21.0",
        graph_base: str = "https://graph.facebook.com",
        timeout: float = 10.0,
    ) -> None:
        self._token = access_token
        self._pnid = phone_number_id
        self._base = f"{graph_base.rstrip('/')}/{api_version}"
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------ send
    async def send_text(
        self,
        *,
        to_phone_e164: str,
        body: str,
        idempotency_key: str,
        reply_to_message_id: str | None = None,
    ) -> SentMessage:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": _strip_plus(to_phone_e164),
            "type": "text",
            "text": {"preview_url": False, "body": body[:4096]},
        }
        if reply_to_message_id:
            payload["context"] = {"message_id": reply_to_message_id}
        return await self._post_message(payload, idempotency_key)

    async def send_template(
        self,
        *,
        to_phone_e164: str,
        template_name: str,
        language: str,
        body_params: list[str],
        idempotency_key: str,
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
        return await self._post_message(payload, idempotency_key)

    async def send_voice_note(
        self,
        *,
        to_phone_e164: str,
        media_url_or_id: str,
        idempotency_key: str,
    ) -> SentMessage:
        media_field = (
            {"id": media_url_or_id}
            if media_url_or_id and not media_url_or_id.startswith("http")
            else {"link": media_url_or_id}
        )
        payload = {
            "messaging_product": "whatsapp",
            "to": _strip_plus(to_phone_e164),
            "type": "audio",
            "audio": media_field,
        }
        return await self._post_message(payload, idempotency_key)

    async def mark_read(self, *, provider_message_id: str) -> None:
        url = f"{self._base}/{self._pnid}/messages"
        try:
            await self._client.post(
                url,
                json={
                    "messaging_product": "whatsapp",
                    "status": "read",
                    "message_id": provider_message_id,
                },
            )
        except httpx.HTTPError as exc:  # not fatal
            _log.warning("meta.mark_read.fail", error=str(exc))

    async def fetch_media(self, *, media_id_or_url: str) -> tuple[bytes, str]:
        if media_id_or_url.startswith("http"):
            url = media_id_or_url
            mime = "application/octet-stream"
        else:
            meta = await self._client.get(f"{self._base}/{media_id_or_url}")
            meta.raise_for_status()
            data = meta.json()
            url = data["url"]
            mime = data.get("mime_type", "application/octet-stream")
        # Token must follow on this hop too — Graph CDN requires it.
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.content, mime

    async def _post_message(
        self, payload: dict[str, Any], idempotency_key: str
    ) -> SentMessage:
        url = f"{self._base}/{self._pnid}/messages"
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.post(
                    url,
                    json=payload,
                    headers={"X-Idempotency-Key": idempotency_key},
                )
                if resp.status_code >= 500:
                    raise httpx.HTTPError(f"meta {resp.status_code}: {resp.text}")
                if resp.status_code >= 400:
                    raise WAProviderError(
                        f"meta {resp.status_code}: {resp.text}",
                        status=resp.status_code,
                    )
                data = resp.json()
                msg_id = (data.get("messages") or [{}])[0].get("id", "")
                return SentMessage(
                    provider_message_id=msg_id,
                    accepted_at=datetime.now(timezone.utc),
                    raw=data,
                )
        # Unreachable — tenacity raises on exhaustion.
        raise RuntimeError("unreachable")  # pragma: no cover

    # --------------------------------------------------------------- inbound
    def parse_inbound(self, payload: Mapping[str, Any]) -> list[InboundMessage]:
        messages: list[InboundMessage] = []
        try:
            entries = payload.get("entry") or []
        except AttributeError:
            return messages
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                metadata = value.get("metadata", {})
                to_phone = "+" + str(metadata.get("display_phone_number", "")).lstrip("+")
                for msg in value.get("messages", []) or []:
                    content_type, body, media = _decode_message(msg)
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


class WAProviderError(Exception):
    def __init__(self, msg: str, *, status: int) -> None:
        super().__init__(msg)
        self.status = status


def _strip_plus(e164: str) -> str:
    return e164.lstrip("+")


def _decode_message(msg: dict[str, Any]) -> tuple[InboundContentType, str | None, InboundMedia | None]:
    t = msg.get("type", "unsupported")
    if t == "text":
        return "text", msg.get("text", {}).get("body"), None
    if t == "audio":
        a = msg.get("audio", {})
        return (
            "voice",
            None,
            InboundMedia(
                s3_key="",
                mime=a.get("mime_type", "audio/ogg"),
                sha256=a.get("sha256"),
            ),
        )
    if t == "image":
        i = msg.get("image", {})
        return "image", i.get("caption"), InboundMedia(
            s3_key="", mime=i.get("mime_type", "image/jpeg"), sha256=i.get("sha256")
        )
    if t == "interactive":
        intr = msg.get("interactive", {})
        if intr.get("type") == "button_reply":
            return "button_reply", intr["button_reply"].get("title"), None
        if intr.get("type") == "list_reply":
            return "list_reply", intr["list_reply"].get("title"), None
        return "interactive", None, None
    if t == "location":
        loc = msg.get("location", {})
        return "location", f"{loc.get('latitude')},{loc.get('longitude')}", None
    if t == "sticker":
        return "sticker", None, None
    return "unsupported", None, None
