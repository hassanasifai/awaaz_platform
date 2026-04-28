"""Langfuse self-hosted client wrapper.

Used to record every LLM call with prompt, response, latency, tokens, cost.
We *don't* import langfuse at module load — credential-less envs would
otherwise fail to import the whole observability package.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from awaaz_api.observability.logging import get_logger
from awaaz_api.settings import get_settings

_log = get_logger("awaaz.langfuse")


@lru_cache(maxsize=1)
def get_client() -> Any | None:
    settings = get_settings()
    if not settings.langfuse_secret_key.get_secret_value():
        return None
    try:
        from langfuse import Langfuse  # type: ignore[import-not-found]
    except ImportError:
        _log.debug("langfuse.import_skipped")
        return None
    return Langfuse(
        public_key=settings.langfuse_public_key.get_secret_value(),
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        host=str(settings.langfuse_host),
    )


def record_generation(
    *,
    name: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    latency_ms: int,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Best-effort: never raises into the caller's path."""

    client = get_client()
    if client is None:
        return
    try:
        client.generation(  # type: ignore[no-untyped-call]
            name=name,
            model=model,
            usage={
                "input": input_tokens,
                "output": output_tokens,
                "cache_read_tokens": cache_read_tokens,
                "unit": "TOKENS",
            },
            metadata={"latency_ms": latency_ms, **(metadata or {})},
        )
    except Exception as exc:
        _log.debug("langfuse.record_failed", error=str(exc))
