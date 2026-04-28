"""Order list / detail / generic intake endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from sqlalchemy import text

from awaaz_api.deps import CurrentUserDep, DbAdminDep, DbDep, SettingsDep
from awaaz_api.observability import get_logger
from awaaz_api.schemas.order import OrderIntake, OrderOut
from awaaz_api.services.dispatch import enqueue_outbound
from awaaz_api.services.intake import intake_order
from awaaz_api.services.signing import verify_hmac_signature

router = APIRouter(prefix="/v1", tags=["orders"])
_log = get_logger("awaaz.orders")


@router.get("/orgs/{org_id}/stores/{store_id}/orders", response_model=list[OrderOut])
async def list_orders(
    org_id: UUID,
    store_id: UUID,
    user: CurrentUserDep,
    db: DbDep,
    cursor: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[OrderOut]:
    if user.org_id != org_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "wrong org")
    where = ["store_id = :sid"]
    params: dict[str, object] = {"sid": store_id, "lim": limit}
    if cursor:
        where.append("created_at < :cursor")
        params["cursor"] = cursor
    if status_filter:
        where.append("confirmation_status = :st")
        params["st"] = status_filter
    rows = (
        await db.execute(
            text(
                f"""
                SELECT id, external_order_id, total, currency, placed_at,
                       confirmation_status, attempt_count, next_attempt_at, tags,
                       app_decrypt_pii(name_enc) AS customer_name,
                       app_decrypt_pii(phone_enc) AS customer_phone
                FROM orders
                JOIN customers ON customers.id = orders.customer_id
                WHERE {' AND '.join(where)}
                ORDER BY orders.created_at DESC
                LIMIT :lim
                """
            ),
            params,
        )
    ).all()
    return [_mask_row(r) for r in rows]


def _mask_row(r) -> OrderOut:  # type: ignore[no-untyped-def]
    phone = r.customer_phone or ""
    masked_phone = phone[:5] + "*" * max(0, len(phone) - 7) + phone[-2:] if phone else ""
    name = (r.customer_name or "").strip()
    masked_name = (name[:1] + "***") if name else None
    return OrderOut(
        id=r.id,
        external_order_id=r.external_order_id,
        customer_phone_masked=masked_phone,
        customer_name_masked=masked_name,
        confirmation_status=r.confirmation_status,
        attempt_count=r.attempt_count,
        next_attempt_at=r.next_attempt_at,
        total=r.total,
        currency=r.currency,
        placed_at=r.placed_at,
        tags=list(r.tags or []),
    )


# ---------------------------------------------------------------------------
# Generic intake (HMAC-signed) — see SPEC §6.
# ---------------------------------------------------------------------------
@router.post(
    "/orders/intake",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generic order intake (HMAC-signed)",
)
async def intake(
    request: Request,
    payload: OrderIntake,
    settings: SettingsDep,
    db: DbAdminDep,
    x_awaaz_signature: Annotated[str | None, Header(alias="X-Awaaz-Signature")] = None,
) -> dict[str, object]:
    body = await request.body()
    store_id = await _resolve_store_for_intake(payload.merchant_id, db)
    if store_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown merchant_id")
    secret = await _store_webhook_secret(store_id, db) or settings.webhook_hmac_default_key.get_secret_value()
    if not verify_hmac_signature(secret=secret, body=body, header=x_awaaz_signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")

    result = await intake_order(db=db, payload=payload, store_id=store_id)
    if result.created:
        await enqueue_outbound(db=db, order_id=result.order_id, channel="whatsapp")
    return {
        "order_id": str(result.order_id),
        "created": result.created,
        "duplicate": not result.created,
    }


async def _resolve_store_for_intake(merchant_id: str, db) -> UUID | None:  # type: ignore[no-untyped-def]
    """`merchant_id` is the merchant-supplied token: store slug or a key."""

    row = (
        await db.execute(
            text(
                """
                SELECT id FROM stores
                WHERE (slug = :m OR id::text = :m)
                  AND status = 'active'
                LIMIT 1
                """
            ),
            {"m": merchant_id},
        )
    ).first()
    return row.id if row else None


async def _store_webhook_secret(store_id: UUID, db) -> str | None:  # type: ignore[no-untyped-def]
    row = (
        await db.execute(
            text(
                "SELECT app_decrypt_pii(webhook_secret_enc) AS s FROM stores WHERE id = :id"
            ),
            {"id": store_id},
        )
    ).first()
    return row.s if row else None
