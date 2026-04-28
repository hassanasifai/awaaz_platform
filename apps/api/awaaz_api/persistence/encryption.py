"""Application-side helpers for the PII columns.

The DB-side functions ``app_encrypt_pii`` / ``app_decrypt_pii`` /
``app_phone_hash`` are the source of truth — these helpers just wrap them so
callers can write idiomatic Python.

The same helpers also produce a deterministic ``phone_hash`` we can compute in
Python without a DB round-trip (e.g. for ingest workers that need to fan out
many lookups).
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

import phonenumbers
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from awaaz_api.settings import get_settings


def normalize_phone(raw: str, *, default_region: str = "PK") -> str:
    """Return E.164 (`+923XXXXXXXXX`) or raise ``ValueError``."""

    try:
        parsed = phonenumbers.parse(raw, default_region)
    except phonenumbers.NumberParseException as exc:  # pragma: no cover - defensive
        raise ValueError(f"unparseable phone number {raw!r}: {exc}") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError(f"invalid phone number {raw!r}")
    return phonenumbers.format_number(
        parsed, phonenumbers.PhoneNumberFormat.E164
    )


def hash_phone(phone_e164: str, *, key: bytes | None = None) -> str:
    """HMAC-SHA256 hex digest, identical to the DB-side ``app_phone_hash``."""

    secret = key or get_settings().phone_hash_key.get_secret_value().encode("utf-8")
    digest = hmac.new(secret, phone_e164.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


async def encrypt_pii(session: AsyncSession, plaintext: str | None) -> bytes | None:
    """Server-side pgcrypto encryption.  Caller must already have a tx open."""

    if plaintext is None:
        return None
    row = await session.execute(
        text("SELECT app_encrypt_pii(:p) AS cipher"),
        {"p": plaintext},
    )
    return row.scalar_one()


async def decrypt_pii(session: AsyncSession, ciphertext: bytes | None) -> str | None:
    if ciphertext is None:
        return None
    row = await session.execute(
        text("SELECT app_decrypt_pii(:c) AS plain"),
        {"c": ciphertext},
    )
    return row.scalar_one()


@dataclass(frozen=True, slots=True)
class PIIVault:
    """Convenience wrapper used by the customer-ingest path.

    >>> vault = PIIVault.for_customer(name="Ali Raza", phone_e164="+923331234567")
    >>> vault.phone_hash         # deterministic
    '4f2c…'
    """

    name_plaintext: str | None
    phone_e164: str

    @classmethod
    def for_customer(
        cls, *, name: str | None, phone_e164: str
    ) -> "PIIVault":
        return cls(
            name_plaintext=name.strip() if name else None,
            phone_e164=normalize_phone(phone_e164),
        )

    @property
    def phone_hash(self) -> str:
        return hash_phone(self.phone_e164)

    async def encrypt(self, session: AsyncSession) -> "EncryptedPII":
        return EncryptedPII(
            name_enc=await encrypt_pii(session, self.name_plaintext),
            phone_enc=await encrypt_pii(session, self.phone_e164),  # type: ignore[arg-type]
            phone_hash=self.phone_hash,
        )


@dataclass(frozen=True, slots=True)
class EncryptedPII:
    name_enc: bytes | None
    phone_enc: bytes
    phone_hash: str
