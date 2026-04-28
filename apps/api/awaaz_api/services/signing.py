"""HMAC verification helpers for inbound webhooks.

Every webhook we accept passes through one of these.  ``hmac.compare_digest``
is non-negotiable — we never use ``==`` for crypto comparisons.
"""

from __future__ import annotations

import base64
import hashlib
import hmac


def verify_hmac_signature(
    *,
    secret: str | bytes,
    body: bytes,
    header: str | None,
    algorithm: str = "sha256",
    encoding: str = "hex",
    prefix: str | None = "sha256=",
) -> bool:
    """Generic ``X-...-Signature: sha256=<hex>`` style verification."""

    if not header:
        return False
    if isinstance(secret, str):
        secret_bytes = secret.encode("utf-8")
    else:
        secret_bytes = secret
    if not secret_bytes:
        return False
    received = header.strip()
    if prefix and received.startswith(prefix):
        received = received[len(prefix):]
    expected = hmac.new(secret_bytes, body, getattr(hashlib, algorithm)).digest()
    if encoding == "hex":
        expected_repr = expected.hex()
        return hmac.compare_digest(expected_repr, received)
    if encoding == "base64":
        expected_repr = base64.b64encode(expected).decode("ascii")
        return hmac.compare_digest(expected_repr, received)
    raise ValueError(f"unsupported encoding {encoding!r}")


def verify_meta_signature(
    *,
    app_secret: str,
    body: bytes,
    header: str | None,
) -> bool:
    """Meta WhatsApp Cloud API uses ``X-Hub-Signature-256: sha256=<hex>``."""

    return verify_hmac_signature(
        secret=app_secret,
        body=body,
        header=header,
        algorithm="sha256",
        encoding="hex",
        prefix="sha256=",
    )


def verify_shopify_signature(
    *,
    api_secret: str,
    body: bytes,
    header: str | None,
) -> bool:
    """Shopify uses ``X-Shopify-Hmac-Sha256`` base64-encoded."""

    return verify_hmac_signature(
        secret=api_secret,
        body=body,
        header=header,
        algorithm="sha256",
        encoding="base64",
        prefix=None,
    )
