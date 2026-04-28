"""LiveKit SIP outbound dial."""

from __future__ import annotations

from typing import Any

from awaaz_agent.observability import get_logger
from awaaz_agent.settings import get_settings

_log = get_logger("awaaz.sip_outbound")


async def create_sip_participant(
    *,
    room_name: str,
    to_number: str,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Initiates an outbound SIP call to ``to_number`` joining ``room_name``."""

    from livekit import api

    settings = get_settings()
    if not settings.livekit_sip_outbound_trunk_id:
        raise RuntimeError("LIVEKIT_SIP_OUTBOUND_TRUNK_ID not configured")

    lk = api.LiveKitAPI(
        settings.livekit_url,
        settings.livekit_api_key.get_secret_value(),
        settings.livekit_api_secret.get_secret_value(),
    )
    request = api.CreateSIPParticipantRequest(
        sip_trunk_id=settings.livekit_sip_outbound_trunk_id,
        sip_call_to=to_number,
        room_name=room_name,
        participant_identity=f"sip-{to_number.replace('+', '')}",
        participant_name="customer",
        participant_metadata=__import__("orjson").dumps(metadata or {}).decode(),
    )
    resp = await lk.sip.create_sip_participant(request)
    _log.info("sip.outbound.created", room=room_name, to=to_number)
    return resp.participant_id
