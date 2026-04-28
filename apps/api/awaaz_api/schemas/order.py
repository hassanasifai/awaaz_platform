"""Order intake + retrieval schemas — wire format for the generic webhook
and the dashboard."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from awaaz_api.persistence import normalize_phone


class CustomerIn(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    phone: str = Field(..., description="Will be normalised to E.164")
    language: Literal["ur", "en", "pa", "sd", "ps"] = "ur"

    @field_validator("phone")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return normalize_phone(v)


class AddressIn(BaseModel):
    line1: str = Field(..., max_length=300)
    line2: str | None = Field(default=None, max_length=300)
    city: str = Field(..., max_length=100)
    province: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)


class LineItemIn(BaseModel):
    name: str = Field(..., max_length=200)
    qty: int = Field(..., ge=1, le=10_000)
    unit_price: Decimal = Field(..., ge=0)
    sku: str | None = None


class OrderIntake(BaseModel):
    """Generic webhook payload — see ``docs/SPEC.md`` §6."""

    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(..., description="Per-store merchant identifier")
    platform: Literal["shopify", "woocommerce", "custom", "manual"]
    order_id: str = Field(..., max_length=200)
    external_order_id: str | None = Field(default=None, max_length=300)
    external_order_number: str | None = Field(default=None, max_length=100)
    customer: CustomerIn
    address: AddressIn
    items: list[LineItemIn] = Field(min_length=1, max_length=200)
    subtotal: Decimal | None = None
    shipping: Decimal | None = None
    total: Decimal = Field(..., ge=0)
    cod_amount: Decimal | None = None
    currency: str = Field(default="PKR", min_length=3, max_length=3)
    placed_at: datetime
    idempotency_key: str = Field(..., min_length=8, max_length=128)


class OrderOut(BaseModel):
    id: UUID
    external_order_id: str
    customer_phone_masked: str
    customer_name_masked: str | None
    confirmation_status: str
    attempt_count: int
    next_attempt_at: datetime | None
    total: Decimal
    currency: str
    placed_at: datetime
    tags: list[str]
