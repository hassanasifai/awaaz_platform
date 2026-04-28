"""Language + script detection.

We pick the dominant script via Unicode block ratios, then back-stop with a
tiny keyword classifier for distinguishing Roman Urdu from English (both use
Latin script).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

Language = Literal["ur", "roman_ur", "en", "pa", "sd", "ps", "unknown"]
Script = Literal["nastaliq", "latin", "devanagari", "mixed", "unknown"]


_ROMAN_URDU_TOKENS = frozenset(
    {
        "hai", "nahi", "nahin", "kya", "ji", "haan", "han", "thik", "theek",
        "achha", "acha", "shukria", "salam", "assalam", "aoa", "kar", "karna",
        "kal", "ab", "abhi", "wapas", "delivery", "address", "order",
        "confirm", "cancel", "kab", "kahan", "main", "mein", "aap", "tum",
        "ghar", "wallahi", "bilkul", "ji haan", "ji nahi", "okay", "ok",
    }
)


def script_ratio(text: str) -> dict[Script, float]:
    """Fraction of letter-class characters by script."""
    nastaliq = latin = devanagari = other = 0
    for ch in text:
        if not ch.isalpha():
            continue
        cp = ord(ch)
        if 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0xFB50 <= cp <= 0xFDFF:
            nastaliq += 1
        elif 0x0041 <= cp <= 0x007A:
            latin += 1
        elif 0x0900 <= cp <= 0x097F:
            devanagari += 1
        else:
            other += 1
    total = nastaliq + latin + devanagari + other
    if total == 0:
        return {"nastaliq": 0.0, "latin": 0.0, "devanagari": 0.0, "mixed": 0.0, "unknown": 1.0}
    return {
        "nastaliq": nastaliq / total,
        "latin": latin / total,
        "devanagari": devanagari / total,
        "mixed": 1.0 if (nastaliq > 0 and latin > 0) else 0.0,
        "unknown": other / total,
    }


def detect_script(text: str, *, threshold: float = 0.6) -> Script:
    ratios = script_ratio(text)
    for s in ("nastaliq", "latin", "devanagari"):
        if ratios[s] >= threshold:  # type: ignore[index]
            return s  # type: ignore[return-value]
    if ratios["mixed"] > 0:
        return "mixed"
    return "unknown"


def detect_language(text: str) -> Language:
    """Best-effort language guess.  Optimised for the WA inbox use-case."""
    script = detect_script(text)
    if script == "nastaliq":
        return "ur"
    if script == "latin":
        return "roman_ur" if _looks_roman_urdu(text) else "en"
    if script == "devanagari":
        return "ur"  # Hindi/Urdu are mutually intelligible spoken; treat the same FSM-side
    return "unknown"


def _looks_roman_urdu(text: str) -> bool:
    tokens = _tokenise(text)
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in _ROMAN_URDU_TOKENS)
    return hits / len(tokens) >= 0.10  # 1 in 10 tokens is enough


def _tokenise(text: str) -> Iterable[str]:
    return [t for t in text.lower().replace(",", " ").replace(".", " ").split() if t]
