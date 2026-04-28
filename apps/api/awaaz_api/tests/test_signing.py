"""Webhook signature verification — every supported scheme + replay safety."""

from __future__ import annotations

import base64
import hashlib
import hmac

import pytest

from awaaz_api.services.signing import (
    verify_hmac_signature,
    verify_meta_signature,
    verify_shopify_signature,
)


SECRET = b"super-secret-signing-key"
BODY = b'{"hello":"world"}'


def _hex_sig(body: bytes, secret: bytes = SECRET) -> str:
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def _b64_sig(body: bytes, secret: bytes = SECRET) -> str:
    return base64.b64encode(hmac.new(secret, body, hashlib.sha256).digest()).decode()


def test_verify_hex_sha256_with_prefix():
    sig = "sha256=" + _hex_sig(BODY)
    assert verify_hmac_signature(secret=SECRET, body=BODY, header=sig)


def test_verify_hex_sha256_without_prefix():
    sig = _hex_sig(BODY)
    assert verify_hmac_signature(secret=SECRET, body=BODY, header=sig, prefix=None)


def test_verify_base64_sha256():
    sig = _b64_sig(BODY)
    assert verify_hmac_signature(
        secret=SECRET, body=BODY, header=sig, encoding="base64", prefix=None
    )


def test_verify_meta_signature_happy_path():
    sig = "sha256=" + _hex_sig(BODY)
    assert verify_meta_signature(app_secret=SECRET.decode(), body=BODY, header=sig)


def test_verify_meta_signature_wrong_secret():
    sig = "sha256=" + _hex_sig(BODY, secret=b"different")
    assert not verify_meta_signature(app_secret=SECRET.decode(), body=BODY, header=sig)


def test_verify_shopify_signature():
    sig = _b64_sig(BODY)
    assert verify_shopify_signature(api_secret=SECRET.decode(), body=BODY, header=sig)


def test_missing_header_rejected():
    assert not verify_hmac_signature(secret=SECRET, body=BODY, header=None)
    assert not verify_hmac_signature(secret=SECRET, body=BODY, header="")


def test_empty_secret_rejected():
    sig = "sha256=" + _hex_sig(BODY)
    assert not verify_hmac_signature(secret="", body=BODY, header=sig)


def test_tamper_detected():
    sig = "sha256=" + _hex_sig(BODY)
    tampered = BODY + b"x"
    assert not verify_hmac_signature(secret=SECRET, body=tampered, header=sig)


def test_unsupported_encoding():
    with pytest.raises(ValueError):
        verify_hmac_signature(
            secret=SECRET, body=BODY, header=_hex_sig(BODY), encoding="ascii"
        )
