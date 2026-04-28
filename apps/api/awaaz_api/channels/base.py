"""Channel provider Protocol — every WA backend implements this."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

InboundContentType = Literal[
    "text",
    "voice",
    "image",
    "sticker",
    "document",
    "location",
    "interactive",
    "button_reply",
    "list_reply",
    "unsupported",
]


@dataclass(frozen=True, slots=True)
class InboundMedia:
    s3_key: str
    mime: str
    duration_ms: int | None = None
    sha256: str | None = None
    transcription: str | None = None


@dataclass(frozen=True, slots=True)
class InboundMessage:
    provider_message_id: str
    from_phone_e164: str
    to_phone_e164: str
    content_type: InboundContentType
    body: str | None
    media: InboundMedia | None
    timestamp: datetime
    raw: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SentMessage:
    provider_message_id: str
    accepted_at: datetime
    raw: dict[str, object] = field(default_factory=dict)


class WAChannelProvider(Protocol):
    """Common surface for ``meta_cloud``, ``dialog360``, ``twilio_wa``."""

    name: str

    async def send_text(
        self,
        *,
        to_phone_e164: str,
        body: str,
        idempotency_key: str,
        reply_to_message_id: str | None = None,
    ) -> SentMessage: ...

    async def send_template(
        self,
        *,
        to_phone_e164: str,
        template_name: str,
        language: str,
        body_params: list[str],
        idempotency_key: str,
    ) -> SentMessage: ...

    async def send_voice_note(
        self,
        *,
        to_phone_e164: str,
        media_url_or_id: str,
        idempotency_key: str,
    ) -> SentMessage: ...

    async def mark_read(self, *, provider_message_id: str) -> None: ...

    async def fetch_media(self, *, media_id_or_url: str) -> tuple[bytes, str]:
        """Returns (bytes, mime).  Streaming variants live in subclasses."""
        ...

    def parse_inbound(self, payload: Mapping[str, object]) -> list[InboundMessage]: ...
