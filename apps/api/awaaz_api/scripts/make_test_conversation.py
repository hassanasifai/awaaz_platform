"""Trigger a test WhatsApp conversation against a real store + phone.

Usage:
    python -m awaaz_api.scripts.make_test_conversation --phone +923XX... --order-id ord-1
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from awaaz_api.channels.dispatch import outbound_first_contact
from awaaz_api.observability import configure_logging, get_logger
from awaaz_api.persistence import AsyncSessionLocal, normalize_phone, set_tenant_context

_log = get_logger("awaaz.test_convo")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phone", required=True)
    parser.add_argument("--order-id", default=str(uuid.uuid4()))
    parser.add_argument("--store-slug", default="lawn-bazaar")
    args = parser.parse_args()

    configure_logging()
    phone = normalize_phone(args.phone)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_context(session, bypass=True)
            row = (
                await session.execute(
                    text("SELECT id, org_id FROM stores WHERE slug = :s"),
                    {"s": args.store_slug},
                )
            ).first()
            if row is None:
                print(f"store {args.store_slug!r} not found — run seed_dev first.", file=sys.stderr)
                return 1
            store_id, org_id = row.id, row.org_id

            customer_id = (
                await session.execute(
                    text(
                        """
                        INSERT INTO customers (org_id, store_id, phone_hash, phone_enc, name_enc, language)
                        VALUES (:org, :sid, app_phone_hash(:phone), app_encrypt_pii(:phone),
                                app_encrypt_pii('Test Buyer'), 'ur')
                        ON CONFLICT (store_id, phone_hash) DO UPDATE SET language = 'ur'
                        RETURNING id
                        """
                    ),
                    {"org": org_id, "sid": store_id, "phone": phone},
                )
            ).scalar_one()
            order_id = (
                await session.execute(
                    text(
                        """
                        INSERT INTO orders (
                            org_id, store_id, customer_id, external_order_id, total,
                            placed_at, idempotency_key
                        )
                        VALUES (:org, :sid, :cid, :eid, 5000, :placed, :ik)
                        RETURNING id
                        """
                    ),
                    {
                        "org": org_id,
                        "sid": store_id,
                        "cid": customer_id,
                        "eid": args.order_id,
                        "placed": datetime.now(tz=timezone.utc),
                        "ik": f"test-{uuid.uuid4()}",
                    },
                )
            ).scalar_one()
            await session.execute(
                text(
                    """
                    INSERT INTO wa_opt_ins (org_id, store_id, customer_id, phone_hash, source)
                    VALUES (:org, :sid, :cid, app_phone_hash(:phone), 'operator_manual')
                    ON CONFLICT (store_id, phone_hash) DO NOTHING
                    """
                ),
                {"org": org_id, "sid": store_id, "cid": customer_id, "phone": phone},
            )

    await outbound_first_contact(
        org_id=org_id, store_id=store_id, order_id=order_id, channel="whatsapp"
    )
    print(f"dispatched test conversation to {phone} (order {order_id})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(asyncio.run(main()))
