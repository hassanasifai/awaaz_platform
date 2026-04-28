"""Speech-to-text router — picks the configured backend.

For inbound WA voice notes we don't need streaming; ``transcribe`` accepts
the full audio bytes and returns plain text.  Voice-channel STT (real-time)
lives in ``apps/agent/awaaz_agent/providers/``.
"""

from __future__ import annotations

import httpx

from awaaz_api.observability import get_logger
from awaaz_api.settings import get_settings

_log = get_logger("awaaz.stt")


async def transcribe(*, audio_bytes: bytes, mime: str) -> str:
    """Best-effort transcript.  Returns ``""`` on failure."""

    settings = get_settings()
    provider = settings.stt_provider
    if provider == "deepgram":
        return await _deepgram(audio_bytes, mime, settings)
    if provider == "faster_whisper":
        return await _faster_whisper(audio_bytes, mime, settings)
    return ""


async def _deepgram(audio: bytes, mime: str, settings) -> str:  # type: ignore[no-untyped-def]
    api_key = settings.deepgram_api_key.get_secret_value()
    if not api_key:
        return ""
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": mime,
    }
    params = {
        "model": settings.deepgram_model,
        "language": settings.deepgram_language,
        "smart_format": "true",
        "punctuate": "true",
    }
    if settings.deepgram_keyterm_list:
        params["keyterm"] = settings.deepgram_keyterm_list  # type: ignore[assignment]
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(
                "https://api.deepgram.com/v1/listen",
                params=params,
                headers=headers,
                content=audio,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            _log.warning("stt.deepgram.fail", error=str(exc))
            return ""
    body = resp.json()
    try:
        return body["results"]["channels"][0]["alternatives"][0]["transcript"]
    except (KeyError, IndexError):
        return ""


async def _faster_whisper(audio: bytes, mime: str, settings) -> str:  # type: ignore[no-untyped-def]
    base = str(settings.faster_whisper_base_url).rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{base}/v1/audio/transcriptions",
                files={"file": ("audio", audio, mime)},
                data={"model": settings.faster_whisper_model, "language": "ur"},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            _log.warning("stt.faster_whisper.fail", error=str(exc))
            return ""
    body = resp.json()
    return str(body.get("text", ""))
