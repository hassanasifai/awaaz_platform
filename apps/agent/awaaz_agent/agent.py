"""LiveKit Agent entrypoint.

Coordinates the per-call session: dial → AMD → if human, run the FSM-driven
agent (Deepgram STT → Claude Haiku LLM → Uplift Orator TTS) → record → close.
"""

from __future__ import annotations

from awaaz_agent.observability import get_logger
from awaaz_agent.settings import get_settings

_log = get_logger("awaaz.agent.entrypoint")


async def entrypoint(ctx) -> None:  # pragma: no cover - LiveKit-driven
    """LiveKit ``WorkerOptions.entrypoint_fnc`` callback.

    Imports are deferred so the test suite (which doesn't install heavy
    LiveKit deps) can import this module for type-checking only.
    """

    from livekit.agents import (
        Agent,
        AgentSession,
        JobContext,
        RoomInputOptions,
    )
    from livekit.plugins import deepgram, anthropic, silero
    from livekit.plugins.turn_detector.multilingual import MultilingualModel
    from livekit.plugins import upliftai  # type: ignore

    settings = get_settings()

    job: JobContext = ctx
    await job.connect()

    # Build the provider stack — cloud defaults; local-stack swap via env.
    stt = deepgram.STT(
        model=settings.deepgram_model,
        language=settings.deepgram_language,
        interim_results=True,
        keyterms=settings.deepgram_keyterm_list,
        api_key=settings.deepgram_api_key.get_secret_value(),
    )
    llm = anthropic.LLM(
        model=settings.anthropic_model_fast,
        api_key=settings.anthropic_api_key.get_secret_value(),
    )
    tts = upliftai.TTS(
        api_key=settings.upliftai_api_key.get_secret_value(),
        voice_id=settings.upliftai_voice_id,
        output_format=settings.upliftai_output_format_telephony,
    )
    vad = silero.VAD.load(min_silence_duration=0.55)

    session = AgentSession(
        vad=vad,
        stt=stt,
        llm=llm,
        tts=tts,
        turn_detection=MultilingualModel(),
    )

    from .flow import build_initial_instructions

    agent = Agent(instructions=build_initial_instructions(job))

    await session.start(
        room=job.room,
        agent=agent,
        room_input_options=RoomInputOptions(),
    )

    # Recording-disclosure must play first.
    await session.say(
        "السلام علیکم۔ یہ کال ریکارڈ کی جا رہی ہے۔",
        allow_interruptions=False,
    )

    _log.info("agent.session_started", room=job.room.name)
