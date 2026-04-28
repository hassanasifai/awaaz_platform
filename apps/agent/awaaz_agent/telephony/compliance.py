"""PTA voice compliance gates — enforced before every dispatch."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

PKT = ZoneInfo("Asia/Karachi")


def in_call_window(
    *, now: datetime | None = None, start: str = "10:00", end: str = "20:00"
) -> bool:
    """Return True if ``now`` (defaults to PKT now) is within the calling window."""
    now = now or datetime.now(tz=PKT)
    now_pkt = now.astimezone(PKT)
    start_h, start_m = (int(p) for p in start.split(":"))
    end_h, end_m = (int(p) for p in end.split(":"))
    t = now_pkt.time()
    return time(start_h, start_m) <= t < time(end_h, end_m)


def is_dncr_listed(phone_hash: str, dncr_set: frozenset[str]) -> bool:
    return phone_hash in dncr_set


def caller_id_allowed(caller_id: str, allowed_pool: list[str]) -> bool:
    """CLI must come from PTA-allocated pool — no spoofing."""
    return caller_id in allowed_pool
