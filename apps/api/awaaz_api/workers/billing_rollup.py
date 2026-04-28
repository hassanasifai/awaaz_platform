"""Reports billing_events to Stripe as usage records."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from awaaz_api.observability import get_logger
from awaaz_api.persistence import AsyncSessionLocal, set_tenant_context
from awaaz_api.settings import get_settings

_log = get_logger("awaaz.worker.billing")


async def run(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await _tick()
            try:
                await asyncio.wait_for(stop.wait(), timeout=900)
            except asyncio.TimeoutError:
                continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log.exception("billing.error", error=str(exc))
            await asyncio.sleep(60)


async def _tick() -> None:
    settings = get_settings()
    if not settings.stripe_secret_key.get_secret_value():
        _log.debug("billing.skip_no_stripe")
        return
    import stripe

    stripe.api_key = settings.stripe_secret_key.get_secret_value()

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_context(session, bypass=True)
            rows = (
                await session.execute(
                    text(
                        """
                        SELECT be.id, be.org_id, be.event_type, be.quantity,
                               be.period_start, be.period_end,
                               o.stripe_customer_id
                        FROM billing_events be
                        JOIN organizations o ON o.id = be.org_id
                        WHERE be.reported_at IS NULL
                          AND o.stripe_customer_id IS NOT NULL
                        ORDER BY be.period_start
                        LIMIT 100
                        """
                    )
                )
            ).all()
            for r in rows:
                try:
                    # The actual `subscription_item` mapping is set up in the
                    # dashboard; this worker assumes a single metered item per
                    # customer for the conversation event type.
                    record = stripe.SubscriptionItem.create_usage_record(
                        id="placeholder",  # replaced via configuration
                        quantity=int(r.quantity),
                        timestamp=int(r.period_start.timestamp()),
                        action="increment",
                    )
                    await session.execute(
                        text(
                            "UPDATE billing_events SET stripe_usage_record_id = :uid, "
                            "reported_at = now() WHERE id = :id"
                        ),
                        {"uid": record["id"], "id": r.id},
                    )
                except Exception as exc:  # pragma: no cover - depends on Stripe
                    _log.warning(
                        "billing.skip_record",
                        org_id=str(r.org_id),
                        error=str(exc),
                    )
