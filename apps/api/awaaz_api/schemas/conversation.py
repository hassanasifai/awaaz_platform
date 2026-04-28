"""Conversation + message read models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Channel = Literal["whatsapp", "voice", "sms"]
Outcome = Literal[
    "confirmed",
    "cancelled",
    "rescheduled",
    "change_request",
    "wrong_number",
    "callback",
    "escalated",
    "no_response",
    "failed",
]


class MessageOut(BaseModel):
    id: UUID
    direction: Literal["inbound", "outbound"]
    role: Literal["user", "assistant", "system", "tool"]
    content_type: str
    body: str | None
    template_name: str | None
    media_s3_key: str | None
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    created_at: datetime


class ConversationOut(BaseModel):
    id: UUID
    channel: Channel
    state: str
    outcome: Outcome | None
    outcome_reason: str | None
    cost_usd: float
    tokens_input: int
    tokens_output: int
    opened_at: datetime
    closed_at: datetime | None
    last_inbound_at: datetime | None
    last_outbound_at: datetime | None
