"""Shared Pydantic primitives — pagination, idempotency, error shape."""

from __future__ import annotations

from typing import Annotated, Generic, TypeVar
from uuid import UUID

from fastapi import Header
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PageInfo(BaseModel):
    next_cursor: str | None = None
    has_more: bool = False


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    page_info: PageInfo


class ApiError(BaseModel):
    code: str
    message: str
    field: str | None = None
    details: dict[str, object] | None = None


class ErrorResponse(BaseModel):
    error: ApiError


IdempotencyHeader = Annotated[
    str | None,
    Header(
        alias="Idempotency-Key",
        description="UUID v4 — required on side-effecting tool routes.",
        max_length=64,
    ),
]


class TenantPath(BaseModel):
    """Reusable URL parameters."""

    model_config = ConfigDict(extra="forbid")

    org_id: UUID = Field(...)
    store_id: UUID = Field(...)
