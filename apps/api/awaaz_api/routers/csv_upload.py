"""CSV bulk-upload of orders.

Format (UTF-8, comma-separated, first row headers):
    external_order_id, customer_name, customer_phone, address_line1, city,
    province, postal_code, total, placed_at, idempotency_key, item_name, item_qty,
    item_unit_price

Rows with the same ``idempotency_key`` collapse into one order whose ``items``
is the union of those rows.  Rows are validated independently — bad rows are
returned in the response and **do not** abort the rest.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import text

from awaaz_api.deps import DbDep
from awaaz_api.observability import get_logger
from awaaz_api.schemas.order import (
    AddressIn,
    CustomerIn,
    LineItemIn,
    OrderIntake,
)
from awaaz_api.services.dispatch import enqueue_outbound
from awaaz_api.services.intake import intake_order

router = APIRouter(prefix="/v1/orgs/{org_id}/stores/{store_id}/csv", tags=["csv"])
_log = get_logger("awaaz.csv")

_REQUIRED = (
    "external_order_id",
    "customer_phone",
    "total",
    "idempotency_key",
)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_csv(
    org_id: UUID,
    store_id: UUID,
    db: DbDep,
    file: UploadFile = File(...),
    dispatch: bool = Form(default=True),
) -> dict[str, object]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "expected a .csv file")

    raw = await file.read()
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "file must be UTF-8") from None
    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty file")
    missing = [c for c in _REQUIRED if c not in reader.fieldnames]
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"missing columns: {', '.join(missing)}",
        )

    grouped: dict[str, OrderIntake] = {}
    errors: list[dict[str, object]] = []
    for idx, row in enumerate(reader, start=2):
        try:
            ik = (row.get("idempotency_key") or "").strip()
            if not ik:
                raise ValueError("idempotency_key is required")
            if ik in grouped:
                grouped[ik].items.append(_parse_item(row))
                continue
            grouped[ik] = OrderIntake(
                merchant_id=str(store_id),
                platform="custom",
                order_id=row["external_order_id"].strip(),
                external_order_id=row.get("external_order_id"),
                customer=CustomerIn(
                    name=row.get("customer_name") or None,
                    phone=row["customer_phone"].strip(),
                    language="ur",
                ),
                address=AddressIn(
                    line1=row.get("address_line1") or "",
                    city=row.get("city") or "",
                    province=row.get("province") or None,
                    postal_code=row.get("postal_code") or None,
                ),
                items=[_parse_item(row)],
                total=Decimal(row["total"].strip()),
                currency=(row.get("currency") or "PKR").strip(),
                placed_at=_parse_dt(row.get("placed_at")),
                idempotency_key=ik,
            )
        except (ValueError, InvalidOperation) as exc:
            errors.append({"row": idx, "error": str(exc)})

    accepted: list[str] = []
    for ik, intake in grouped.items():
        result = await intake_order(db=db, payload=intake, store_id=store_id)
        accepted.append(str(result.order_id))
        if dispatch and result.created:
            await enqueue_outbound(db=db, order_id=result.order_id, channel="whatsapp")

    return {
        "accepted": accepted,
        "errors": errors,
        "total_rows": len(grouped) + len(errors),
    }


def _parse_item(row: dict[str, str]) -> LineItemIn:
    return LineItemIn(
        name=(row.get("item_name") or "Item").strip(),
        qty=int(row.get("item_qty") or "1"),
        unit_price=Decimal((row.get("item_unit_price") or "0").strip()),
    )


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"placed_at must be ISO-8601: {value!r}") from exc
    # Naive timestamps are interpreted as UTC.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
