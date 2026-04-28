"""structlog setup + PII-redaction processor + request-context binder."""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import Mapping
from typing import Any

import structlog
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    merge_contextvars,
    unbind_contextvars,
)

from awaaz_api.settings import get_settings

# Sensitive value patterns scrubbed from every log line.
_PHONE_RE = re.compile(r"\+?\d{10,15}")
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}", re.IGNORECASE)
_LONG_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]{32,}")
_SECRET_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "password_hash",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "auth_token",
        "api_key",
        "authorization",
        "cookie",
        "set-cookie",
        "phone",
        "customer_phone",
        "phone_number",
        "address",
        "address_line1",
        "address_line2",
        "name_enc",
        "phone_enc",
        "address_line1_enc",
        "wa_access_token",
        "wa_app_secret",
        "stripe_secret_key",
        "anthropic_api_key",
        "deepgram_api_key",
        "upliftai_api_key",
        "meta_wa_access_token",
        "meta_wa_app_secret",
        "pii_encryption_key",
        "phone_hash_key",
    }
)


def _redact(value: Any) -> Any:
    """Recursive redaction for dict values and strings."""
    if isinstance(value, str):
        v = _BEARER_RE.sub("Bearer <redacted>", value)
        v = _PHONE_RE.sub("<phone>", v)
        v = _LONG_TOKEN_RE.sub("<token>", v)
        return v
    if isinstance(value, Mapping):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _redaction_processor(
    _logger: Any, _name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in event_dict.items():
        if k.lower() in _SECRET_KEYS:
            out[k] = "<redacted>"
            continue
        out[k] = _redact(v)
    return out


def configure_logging() -> None:
    """Install structlog + stdlib bridge, formatted per ``LOG_FORMAT``."""

    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    processors: list[structlog.types.Processor] = [
        merge_contextvars,
        structlog.processors.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        _redaction_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib loggers (uvicorn, sqlalchemy) through structlog.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level)

    # Quiet down a few extremely chatty libraries by default.
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[return-value]


def bind_request_context(**fields: Any) -> None:
    """Attach request-scoped fields to every subsequent log line."""

    bind_contextvars(**{k: v for k, v in fields.items() if v is not None})


def clear_request_context() -> None:
    clear_contextvars()


def unbind_request_context(*keys: str) -> None:
    unbind_contextvars(*keys)
