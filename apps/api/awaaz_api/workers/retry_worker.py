"""Polls ``retry_queues`` for due rows and dispatches outbound messages.

Picks up the next due row using ``FOR UPDATE SKIP LOCKED`` so multiple
workers can run safely.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text

from awaaz_api.observability import get_logger
from awaaz_api.persistence import AsyncSessionLocal, set_tenant_context

_log = get_logger("awaaz.worker.retry")


async def run(stop: asyncio.Event) -> None:
    backoff = 1.0
    while not stop.is_set():
        try:
            picked = await _pick_one()
            if picked is None:
                await asyncio.wait_for(stop.wait(), timeout=2)
                continue
            await _dispatch(picked)
            backoff = 1.0
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log.exception("retry.error", error=str(exc))
            await asyncio.sleep(min(backoff, 30))
            backoff *= 2


async def _pick_one() -> dict[str, object] | None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(text("SET LOCAL app.bypass_rls = 'on'"))
            row = (
                await session.execute(
                    text(
                        """
                        SELECT id, org_id, store_id, order_id, channel, attempt, payload
                        FROM retry_queues
                        WHERE picked_up_at IS NULL
                          AND completed_at IS NULL
                          AND scheduled_for <= now()
                        ORDER BY scheduled_for
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                        """
                    )
                )
            ).first()
            if row is None:
                return None
            await session.execute(
                text("UPDATE retry_queues SET picked_up_at = now() WHERE id = :id"),
                {"id": row.id},
            )
            return dict(row._mapping)


async def _dispatch(item: dict[str, object]) -> None:
    """Hand off to the channel-specific dispatch handler.

    Imported lazily so the worker boots even when the (currently optional)
    channel modules have unmet runtime deps in dev (e.g. no Twilio creds).
    """

    from awaaz_api.channels.dispatch import outbound_first_contact

    org_id = UUID(str(item["org_id"]))
    store_id = UUID(str(item["store_id"]))
    order_id = UUID(str(item["order_id"]))
    channel = str(item["channel"])
    queue_id = UUID(str(item["id"]))

    try:
        await outbound_first_contact(
            org_id=org_id, store_id=store_id, order_id=order_id, channel=channel
        )
        await _mark_done(queue_id, ok=True, error=None)
    except Exception as exc:
        _log.exception("retry.dispatch_failed", error=str(exc), channel=channel)
        await _mark_done(queue_id, ok=False, error=str(exc))


async def _mark_done(queue_id: UUID, *, ok: bool, error: str | None) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_context(session, bypass=True)
            await session.execute(
                text(
                    """
                    UPDATE retry_queues
                       SET completed_at = :now, error = :err
                     WHERE id = :id
                    """
                ),
                {
                    "id": queue_id,
                    "now": datetime.now(tz=timezone.utc),
                    "err": error if not ok else None,
                },
            )
