"""Consumes inbound WhatsApp webhook events and feeds the FSM."""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import text

from awaaz_api.observability import get_logger
from awaaz_api.persistence import AsyncSessionLocal, set_tenant_context

_log = get_logger("awaaz.worker.wa_event")


async def run(stop: asyncio.Event) -> None:
    backoff = 1.0
    while not stop.is_set():
        try:
            picked = await _pick_one()
            if picked is None:
                await asyncio.wait_for(stop.wait(), timeout=2)
                continue
            await _process(picked)
            backoff = 1.0
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log.exception("wa_event.error", error=str(exc))
            await asyncio.sleep(min(backoff, 30))
            backoff *= 2


async def _pick_one() -> dict[str, object] | None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_context(session, bypass=True)
            row = (
                await session.execute(
                    text(
                        """
                        SELECT id, source, event_id, event_type, store_id, payload
                        FROM webhook_events
                        WHERE source IN ('meta_wa', 'dialog360', 'twilio_wa')
                          AND processed_at IS NULL
                          AND error IS NULL
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
    """Defer to the FSM event handler — kept slim so we can dual-source events."""

    from awaaz_api.channels.dispatch import handle_inbound_event

    try:
        await handle_inbound_event(
            source=str(event["source"]),
            store_id=UUID(str(event["store_id"])) if event["store_id"] else None,
            event_type=str(event["event_type"]),
            payload=dict(event["payload"]),  # type: ignore[arg-type]
        )
    except Exception as exc:
        await _mark_error(UUID(str(event["id"])), str(exc))
        raise


async def _mark_error(event_id: UUID, error: str) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_context(session, bypass=True)
            await session.execute(
                text("UPDATE webhook_events SET error = :e WHERE id = :id"),
                {"e": error[:500], "id": event_id},
            )
