"""Urdu / Roman-Urdu / English language utilities."""

from __future__ import annotations

from .detect import detect_language, detect_script, script_ratio
from .normalize import normalize_text, number_to_urdu_words

__all__ = [
    "detect_language",
    "detect_script",
    "script_ratio",
    "normalize_text",
    "number_to_urdu_words",
]
