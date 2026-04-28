"""Test fixtures — async DB session, fake LLM, sample tenant."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest_asyncio

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PII_ENCRYPTION_KEY", "0123456789abcdef0123456789abcdef")
os.environ.setdefault("PHONE_HASH_KEY", "fedcba9876543210fedcba9876543210")
os.environ.setdefault("WEBHOOK_HMAC_DEFAULT_KEY", "deadbeefdeadbeefdeadbeefdeadbeef")
os.environ.setdefault("BETTER_AUTH_SECRET", "testsecrettestsecrettestsecret32")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("META_WA_APP_SECRET", "testappsecret")
os.environ.setdefault("META_WA_VERIFY_TOKEN", "testverify")


@pytest_asyncio.fixture
async def fixture_uuid() -> AsyncIterator[uuid.UUID]:
    yield uuid.uuid4()
