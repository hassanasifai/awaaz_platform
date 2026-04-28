"""Async AMD callback handling — tuned for Pakistani voicemail patterns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AmdResult = Literal["human", "machine_start", "machine_end_beep", "machine_end_silence", "fax", "unknown"]


@dataclass(frozen=True, slots=True)
class AmdDecision:
    result: AmdResult
    confidence: float
    should_speak_voicemail: bool


def classify_amd(event: dict[str, str | int | float]) -> AmdDecision:
    """Map a Twilio AMD callback into our voicemail-vs-human decision.

    Twilio's ``AnsweredBy`` covers: ``human``, ``machine_start``,
    ``machine_end_beep``, ``machine_end_silence``, ``machine_end_other``,
    ``fax``, ``unknown``.
    """

    answered_by = str(event.get("AnsweredBy", "unknown"))
    confidence = float(event.get("MachineDetectionConfidence", 0) or 0)

    # We only speak the 5-second branded voicemail prompt when the
    # answering machine has fully finished its greeting.  Otherwise we'd
    # be talking over the customer's mailbox prompt.
    if answered_by in {"machine_end_beep", "machine_end_silence", "machine_end_other"}:
        return AmdDecision(answered_by, confidence, should_speak_voicemail=True)
    if answered_by == "human":
        return AmdDecision("human", confidence, should_speak_voicemail=False)
    if answered_by.startswith("machine_"):
        return AmdDecision(answered_by, confidence, should_speak_voicemail=False)  # type: ignore[arg-type]
    if answered_by == "fax":
        return AmdDecision("fax", confidence, should_speak_voicemail=False)
    return AmdDecision("unknown", confidence, should_speak_voicemail=False)
