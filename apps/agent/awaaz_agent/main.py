"""LiveKit Agent worker entry-point.

The agent registers with LiveKit Cloud / OSS and waits for ``CreateSIPParticipant``
dispatches.  Per-call orchestration lives in ``awaaz_agent.agent``.
"""

from __future__ import annotations

import asyncio

from awaaz_agent.observability import configure_logging, get_logger, setup_telemetry
from awaaz_agent.settings import get_settings


def _import_lazy():  # pragma: no cover - lazy to keep CI light
    """LiveKit pulls in heavy deps; only import when actually running."""
    from livekit.agents import WorkerOptions, cli
    from awaaz_agent.agent import entrypoint

    return WorkerOptions, cli, entrypoint


async def _async_main() -> None:
    log = get_logger("awaaz.agent")
    settings = get_settings()
    log.info(
        "agent.startup",
        provider=settings.llm_provider,
        stt=settings.stt_provider,
        tts=settings.tts_provider,
    )

    WorkerOptions, cli, entrypoint = _import_lazy()
    options = WorkerOptions(
        entrypoint_fnc=entrypoint,
        ws_url=settings.livekit_url,
        api_key=settings.livekit_api_key.get_secret_value(),
        api_secret=settings.livekit_api_secret.get_secret_value(),
    )
    await cli.run_app(options)


def main() -> None:
    configure_logging()
    setup_telemetry()
    asyncio.run(_async_main())


if __name__ == "__main__":  # pragma: no cover
    main()
