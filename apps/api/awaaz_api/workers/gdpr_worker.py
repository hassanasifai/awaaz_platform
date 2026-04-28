"""Process Shopify GDPR webhooks (data_request, redact)."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from awaaz_api.observability import get_logger
from awaaz_api.persistence import AsyncSessionLocal, set_tenant_context

_log = get_logger("awaaz.worker.gdpr")


async def run(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            picked = await _pick_one()
            if picked is None:
                await asyncio.wait_for(stop.wait(), timeout=10)
                continue
            await _process(picked)
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log.exception("gdpr.error", error=str(exc))
            await asyncio.sleep(5)


async def _pick_one() -> dict[str, object] | None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_context(session, bypass=True)
            row = (
                await session.execute(
                    text(
                        """
                        SELECT id, event_type, payload
                        FROM webhook_events
                        WHERE source = 'shopify'
                          AND event_type IN ('customers/data_request',
                                             'customers/redact',
                                             'shop/redact')
                          AND processed_at IS NULL
                        ORDER BY received_at
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                        """
                    )
                )
            ).first()
            if row is None:
                return None
            await session.execute(
                text("UPDATE webhook_events SET processed_at = now() WHERE id = :id"),
                {"id": row.id},
            )
            return dict(row._mapping)


async def _process(event: dict[str, object]) -> None:
    """Pseudonymise customer rows referenced by the request payload."""

    payload = event["payload"]
    et = str(event["event_type"])
    if et == "customers/redact":
        # Best-effort: match by shopify_customer_id stored in metadata.
        cust_id = payload.get("customer", {}).get("id") if isinstance(payload, dict) else None
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await set_tenant_context(session, bypass=True)
                await session.execute(
                    text(
                        """
                        UPDATE customers
                           SET name_enc = NULL,
                               phone_enc = app_encrypt_pii('+REDACTED'),
                               email_enc = NULL,
                               opted_out_at = now()
                         WHERE id IN (
                            SELECT customer_id FROM orders
                            WHERE metadata->>'shopify_customer_id' = :sc
                         )
                        """
                    ),
                    {"sc": str(cust_id) if cust_id else ""},
                )
    elif et == "shop/redact":
        # Soft-delete the store after the 30-day grace.
        domain = payload.get("shop_domain") if isinstance(payload, dict) else None
        if domain:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await set_tenant_context(session, bypass=True)
                    await session.execute(
                        text(
                            "UPDATE stores SET status = 'deleted' "
                            "WHERE platform_shop_domain = :d"
                        ),
                        {"d": domain},
                    )
    _log.info("gdpr.processed", event_type=et)
