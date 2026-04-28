"""Hourly aggregation — recent confirmation rate, latency P95, etc.

Writes ``billing_events`` rows that the billing worker turns into Stripe
usage records.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from awaaz_api.observability import get_logger
from awaaz_api.persistence import AsyncSessionLocal, set_tenant_context

_log = get_logger("awaaz.worker.analytics")


async def run(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await _tick()
            try:
                await asyncio.wait_for(stop.wait(), timeout=600)
            except asyncio.TimeoutError:
                continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log.exception("analytics.error", error=str(exc))
            await asyncio.sleep(30)


async def _tick() -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_context(session, bypass=True)
            await session.execute(
                text(
                    """
                    INSERT INTO billing_events (
                        org_id, store_id, event_type, quantity, unit,
                        period_start, period_end, metadata
                    )
                    SELECT
                        org_id, store_id, 'conversation',
                        count(*) FILTER (WHERE outcome IS NOT NULL),
                        'count',
                        date_trunc('hour', now() - interval '1 hour'),
                        date_trunc('hour', now()),
                        jsonb_build_object('confirmed',
                            count(*) FILTER (WHERE outcome = 'confirmed'))
                    FROM conversations
                    WHERE opened_at >= date_trunc('hour', now() - interval '1 hour')
                      AND opened_at <  date_trunc('hour', now())
                    GROUP BY org_id, store_id
                    ON CONFLICT (org_id, event_type, period_start) DO NOTHING
                    """
                )
            )
    _log.info("analytics.rolled_up")
