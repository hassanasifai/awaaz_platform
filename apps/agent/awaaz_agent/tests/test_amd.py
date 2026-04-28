"""AMD classifier — unit tests covering all Twilio AnsweredBy values."""

from __future__ import annotations

import pytest

from awaaz_agent.telephony.amd import classify_amd


@pytest.mark.parametrize(
    "answered_by, expected_speak",
    [
        ("human", False),
        ("machine_start", False),
        ("machine_end_beep", True),
        ("machine_end_silence", True),
        ("machine_end_other", True),
        ("fax", False),
        ("unknown", False),
        ("", False),
    ],
)
def test_classify_amd(answered_by: str, expected_speak: bool) -> None:
    out = classify_amd({"AnsweredBy": answered_by, "MachineDetectionConfidence": 0.9})
    assert out.should_speak_voicemail is expected_speak
