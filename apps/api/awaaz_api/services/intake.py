"""Order intake — idempotent upsert into ``orders`` + ``customers``."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from awaaz_api.observability import get_logger
from awaaz_api.persistence import PIIVault, encrypt_pii, hash_phone, normalize_phone
from awaaz_api.schemas.order import OrderIntake

_log = get_logger("awaaz.intake")


@dataclass(frozen=True, slots=True)
class IntakeResult:
    order_id: UUID
    customer_id: UUID
    created: bool


async def intake_order(
    *,
    db: AsyncSession,
    payload: OrderIntake,
    store_id: UUID,
) -> IntakeResult:
    org_id = (
        await db.execute(
            text("SELECT org_id FROM stores WHERE id = :sid AND status != 'deleted'"),
            {"sid": store_id},
        )
    ).scalar_one_or_none()
    if org_id is None:
        raise ValueError(f"store {store_id} not found or deleted")

    phone_e164 = normalize_phone(payload.customer.phone)
    phone_hash = hash_phone(phone_e164)

    customer_row = (
        await db.execute(
            text(
                "SELECT id FROM customers WHERE store_id = :sid AND phone_hash = :ph"
            ),
            {"sid": store_id, "ph": phone_hash},
        )
    ).first()
    if customer_row:
        customer_id = customer_row.id
    else:
        vault = PIIVault.for_customer(
            name=payload.customer.name, phone_e164=phone_e164
        )
        enc = await vault.encrypt(db)
        customer_id = (
            await db.execute(
                text(
                    """
                    INSERT INTO customers (org_id, store_id, phone_hash, phone_enc, name_enc, language)
                    VALUES (:org, :sid, :ph, :pe, :ne, :lang)
                    ON CONFLICT (store_id, phone_hash) DO UPDATE SET name_enc = COALESCE(EXCLUDED.name_enc, customers.name_enc)
                    RETURNING id
                    """
                ),
                {
                    "org": org_id,
                    "sid": store_id,
                    "ph": enc.phone_hash,
                    "pe": enc.phone_enc,
                    "ne": enc.name_enc,
                    "lang": payload.customer.language,
                },
            )
        ).scalar_one()

    line1_enc = await encrypt_pii(db, payload.address.line1)
    line2_enc = await encrypt_pii(db, payload.address.line2)

    existing = (
        await db.execute(
            text(
                "SELECT id FROM orders WHERE store_id = :sid AND idempotency_key = :ik"
            ),
            {"sid": store_id, "ik": payload.idempotency_key},
        )
    ).first()
    if existing:
        return IntakeResult(order_id=existing.id, customer_id=customer_id, created=False)

    order_id = (
        await db.execute(
            text(
                """
                INSERT INTO orders (
                    org_id, store_id, customer_id, external_order_id, external_order_number,
                    address_line1_enc, address_line2_enc, city, province, postal_code,
                    subtotal, shipping, total, currency, cod_amount, payment_method,
                    line_items, placed_at, idempotency_key
                )
                VALUES (
                    :org, :sid, :cid, :eoid, :eonum,
                    :a1, :a2, :city, :prov, :pc,
                    :sub, :ship, :tot, :cur, :cod, 'cod',
                    :items::jsonb, :placed, :ik
                )
                RETURNING id
                """
            ),
            {
                "org": org_id,
                "sid": store_id,
                "cid": customer_id,
                "eoid": payload.external_order_id or payload.order_id,
                "eonum": payload.external_order_number or payload.order_id,
                "a1": line1_enc,
                "a2": line2_enc,
                "city": payload.address.city,
                "prov": payload.address.province,
                "pc": payload.address.postal_code,
                "sub": payload.subtotal,
                "ship": payload.shipping,
                "tot": payload.total,
                "cur": payload.currency,
                "cod": payload.cod_amount or payload.total,
                "items": [li.model_dump(mode="json") for li in payload.items],
                "placed": payload.placed_at,
                "ik": payload.idempotency_key,
            },
        )
    ).scalar_one()
    _log.info("order.intake", store_id=str(store_id), order_id=str(order_id))
    return IntakeResult(order_id=order_id, customer_id=customer_id, created=True)
