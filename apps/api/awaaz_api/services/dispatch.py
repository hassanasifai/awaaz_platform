"""Outbound dispatch — schedule the next attempt on the retry queue."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from awaaz_api.observability import get_logger

_log = get_logger("awaaz.dispatch")

Channel = Literal["whatsapp", "voice", "sms"]


async def enqueue_outbound(
    *,
    db: AsyncSession,
    order_id: UUID,
    channel: Channel,
    delay: timedelta = timedelta(0),
    payload: dict[str, object] | None = None,
) -> UUID:
    """Insert a row into ``retry_queues``.  Worker picks it up via PGQueuer."""

    row = (
        await db.execute(
            text(
                """
                INSERT INTO retry_queues
                    (org_id, store_id, order_id, channel, attempt, scheduled_for, payload)
                SELECT o.org_id, o.store_id, o.id, :ch,
                       o.attempt_count + 1,
                       :when,
                       COALESCE(:payload, '{}'::jsonb)
                FROM orders o WHERE o.id = :oid
                RETURNING id
                """
            ),
            {
                "ch": channel,
                "when": datetime.now(tz=timezone.utc) + delay,
                "payload": payload or {},
                "oid": order_id,
            },
        )
    ).one()
    await db.execute(
        text(
            "UPDATE orders SET confirmation_status = 'dispatched', "
            "next_attempt_at = :when, attempt_count = attempt_count + 1 "
            "WHERE id = :oid"
        ),
        {"when": datetime.now(tz=timezone.utc) + delay, "oid": order_id},
    )
    _log.info(
        "dispatch.enqueue",
        order_id=str(order_id),
        channel=channel,
        delay_s=int(delay.total_seconds()),
    )
    return row.id


async def schedule_retry(
    *,
    db: AsyncSession,
    order_id: UUID,
    channel: Channel,
    backoff_minutes: int,
) -> UUID | None:
    """Schedule a retry up to MAX_RETRY_ATTEMPTS; return None if exhausted."""

    from awaaz_api.settings import get_settings

    cap = get_settings().max_retry_attempts
    cur = (
        await db.execute(
            text("SELECT attempt_count FROM orders WHERE id = :oid"),
            {"oid": order_id},
        )
    ).scalar_one()
    if cur >= cap:
        await db.execute(
            text("UPDATE orders SET confirmation_status = 'failed' WHERE id = :oid"),
            {"oid": order_id},
        )
        return None
    return await enqueue_outbound(
        db=db,
        order_id=order_id,
        channel=channel,
        delay=timedelta(minutes=backoff_minutes),
    )
