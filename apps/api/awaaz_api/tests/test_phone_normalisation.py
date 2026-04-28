"""Pakistani phone-number normalisation + hashing."""

from __future__ import annotations

import pytest

from awaaz_api.persistence.encryption import hash_phone, normalize_phone


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("0300-1234567", "+923001234567"),
        ("03001234567", "+923001234567"),
        ("923001234567", "+923001234567"),
        ("+923001234567", "+923001234567"),
        ("(0300) 123-4567", "+923001234567"),
    ],
)
def test_normalise_pk_mobile(raw: str, expected: str) -> None:
    assert normalize_phone(raw, default_region="PK") == expected


def test_invalid_rejected():
    with pytest.raises(ValueError):
        normalize_phone("123", default_region="PK")


def test_hash_is_deterministic_and_keyed():
    h1 = hash_phone("+923001234567", key=b"a" * 32)
    h2 = hash_phone("+923001234567", key=b"a" * 32)
    h3 = hash_phone("+923001234567", key=b"b" * 32)
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64
