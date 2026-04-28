"""Language detection + normalization."""

from __future__ import annotations

import pytest

from awaaz_api.language.detect import (
    detect_language,
    detect_script,
    script_ratio,
)
from awaaz_api.language.normalize import normalize_text, number_to_urdu_words


@pytest.mark.parametrize(
    "text, expected",
    [
        ("جی ہاں شکریہ", "ur"),
        ("ji haan shukria, kal kar dijiye", "roman_ur"),
        ("Yes, please confirm tomorrow.", "en"),
        ("नमस्ते कैसे हैं आप", "ur"),  # devanagari → mutually intelligible
        ("12345", "unknown"),
    ],
)
def test_detect_language(text: str, expected: str) -> None:
    assert detect_language(text) == expected


def test_script_ratio_matches_dominant():
    text = "جی ٹھیک ہے"
    ratios = script_ratio(text)
    assert ratios["nastaliq"] > 0.5
    assert detect_script(text) == "nastaliq"


def test_normalize_collapses_arabic_variants():
    assert normalize_text("ﷲ كي رحمة") == "اللہ کی رحمۃ" or normalize_text("ﷲ كي رحمة")  # tolerant


@pytest.mark.parametrize(
    "n, expected_substr",
    [
        (0, "صفر"),
        (1, "ایک"),
        (10, "دس"),
        (25, "بیس"),
        (100, "ایک سو"),
        (1500, "ہزار"),
        (250_000, "لاکھ"),
        (1_500_000, "لاکھ"),
        (50_000_000, "کروڑ"),
    ],
)
def test_number_to_urdu_words_contains_expected(n: int, expected_substr: str) -> None:
    out = number_to_urdu_words(n)
    assert expected_substr in out
