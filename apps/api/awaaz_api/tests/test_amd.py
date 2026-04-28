"""Voice agent AMD classifier — voicemail vs human."""

from __future__ import annotations

# We import indirectly so the test module doesn't depend on the agent package
# being installed (CI may run them in separate venvs).
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "agent"))
amd = importlib.import_module("awaaz_agent.telephony.amd")


def test_human_decision():
    out = amd.classify_amd({"AnsweredBy": "human", "MachineDetectionConfidence": 0.95})
    assert out.result == "human"
    assert out.should_speak_voicemail is False


def test_machine_end_speaks_voicemail():
    out = amd.classify_amd({"AnsweredBy": "machine_end_beep"})
    assert out.should_speak_voicemail is True


def test_machine_start_does_not_speak():
    out = amd.classify_amd({"AnsweredBy": "machine_start"})
    assert out.should_speak_voicemail is False


def test_unknown_falls_back():
    out = amd.classify_amd({})
    assert out.result == "unknown"
    assert out.should_speak_voicemail is False
