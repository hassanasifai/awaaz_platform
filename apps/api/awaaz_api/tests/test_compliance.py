"""Voice compliance gates — call window, DNCR, CLI allow-list."""

from __future__ import annotations

import importlib
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "agent"))
compliance = importlib.import_module("awaaz_agent.telephony.compliance")

PKT = ZoneInfo("Asia/Karachi")


def test_call_window_within_business_hours():
    now = datetime(2026, 4, 28, 11, 0, tzinfo=PKT)
    assert compliance.in_call_window(now=now)


def test_call_window_too_early():
    now = datetime(2026, 4, 28, 9, 0, tzinfo=PKT)
    assert not compliance.in_call_window(now=now)


def test_call_window_too_late():
    now = datetime(2026, 4, 28, 22, 0, tzinfo=PKT)
    assert not compliance.in_call_window(now=now)


def test_dncr_blocks_listed_phone():
    listed = frozenset({"abc123"})
    assert compliance.is_dncr_listed("abc123", listed)
    assert not compliance.is_dncr_listed("def456", listed)


def test_caller_id_must_be_in_allow_pool():
    pool = ["+924100000001", "+924100000002"]
    assert compliance.caller_id_allowed("+924100000001", pool)
    assert not compliance.caller_id_allowed("+923331234567", pool)
