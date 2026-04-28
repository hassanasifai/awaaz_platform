"""PTA voice compliance gates — unit tests."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from awaaz_agent.telephony.compliance import (
    caller_id_allowed,
    in_call_window,
    is_dncr_listed,
)

PKT = ZoneInfo("Asia/Karachi")


@pytest.mark.parametrize(
    "hour, expected",
    [(9, False), (10, True), (15, True), (19, True), (20, False), (22, False)],
)
def test_call_window(hour: int, expected: bool) -> None:
    now = datetime(2026, 4, 28, hour, 0, tzinfo=PKT)
    assert in_call_window(now=now) is expected


def test_dncr() -> None:
    listed = frozenset({"abc"})
    assert is_dncr_listed("abc", listed)
    assert not is_dncr_listed("xyz", listed)


def test_caller_id_pool() -> None:
    pool = ["+92410000001"]
    assert caller_id_allowed("+92410000001", pool)
    assert not caller_id_allowed("+92341111111", pool)
