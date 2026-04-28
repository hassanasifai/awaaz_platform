"""Text normalization + number-to-Urdu-words.

Avoids ``urduhack``'s heavy import path; the bits we need are small enough
to maintain in-tree, and the test surface is deterministic.
"""

from __future__ import annotations

import re
from typing import Final

# Mapping of variant Arabic-Persian forms to canonical Urdu nastaliq.
_NORMALISATIONS: Final[dict[str, str]] = {
    "ي": "ی",
    "ى": "ی",
    "ك": "ک",
    "ة": "ہ",
    "ٱ": "ا",
    "أ": "ا",
    "إ": "ا",
    "ﷲ": "اللہ",
    # Arabic-Indic digits → Urdu (Western Arabic-Indic) digits stay as-is for
    # compatibility with phone-number parsing; we just collapse two variants.
    "٠": "۰", "١": "۱", "٢": "۲", "٣": "۳", "٤": "۴",
    "٥": "۵", "٦": "۶", "٧": "۷", "٨": "۸", "٩": "۹",
}

_WS = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    if not text:
        return ""
    out = []
    for ch in text:
        out.append(_NORMALISATIONS.get(ch, ch))
    return _WS.sub(" ", "".join(out)).strip()


# ---------------------------------------------------------------------------
# Number to Urdu words — covers 0..999_999_99 (i.e. lakhs and crores).
# ---------------------------------------------------------------------------
_UNITS = (
    "صفر", "ایک", "دو", "تین", "چار", "پانچ", "چھ", "سات", "آٹھ", "نو",
    "دس", "گیارہ", "بارہ", "تیرہ", "چودہ", "پندرہ", "سولہ", "سترہ",
    "اٹھارہ", "انیس",
)
_TENS = {
    20: "بیس", 30: "تیس", 40: "چالیس", 50: "پچاس",
    60: "ساٹھ", 70: "ستر", 80: "اسی", 90: "نوے",
}


def _below_hundred(n: int) -> str:
    if n < 20:
        return _UNITS[n]
    if n in _TENS:
        return _TENS[n]
    base = n - (n % 10)
    return f"{_UNITS[n % 10]} {_TENS.get(base, '?')}"


def _below_thousand(n: int) -> str:
    if n < 100:
        return _below_hundred(n)
    h = n // 100
    rest = n % 100
    parts = [f"{_UNITS[h]} سو"]
    if rest:
        parts.append(_below_hundred(rest))
    return " ".join(parts)


def number_to_urdu_words(n: int) -> str:
    """Convert non-negative integer up to 99 99 999 99 into Urdu words."""

    if n < 0:
        return f"منفی {number_to_urdu_words(-n)}"
    if n < 1000:
        return _below_thousand(n)
    if n < 100_000:  # < 1 lakh
        thousands, rest = divmod(n, 1000)
        out = [f"{_below_thousand(thousands)} ہزار"]
        if rest:
            out.append(_below_thousand(rest))
        return " ".join(out)
    if n < 10_000_000:  # < 1 crore
        lakhs, rest = divmod(n, 100_000)
        out = [f"{_below_thousand(lakhs)} لاکھ"]
        if rest:
            out.append(number_to_urdu_words(rest))
        return " ".join(out)
    crores, rest = divmod(n, 10_000_000)
    out = [f"{_below_thousand(crores)} کروڑ"]
    if rest:
        out.append(number_to_urdu_words(rest))
    return " ".join(out)
