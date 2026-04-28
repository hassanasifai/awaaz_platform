"""Per-call FSM glue.

The voice agent uses the same FSM design as the API (same state names, same
tools) but hosts the LLM loop inside LiveKit's session.  We synthesise the
initial instructions from the job metadata.
"""

from __future__ import annotations

from typing import Any

DEFAULT_AGENT_NAME = "Sahar"


def build_initial_instructions(job: Any) -> str:
    """Read the room/job metadata and inject into the FSM system prompt.

    Job metadata convention (set by ``CreateSIPParticipant`` from the API):
    ``{"order_id": "...", "brand_name": "...", "customer_name": "...",
       "order_number": "...", "total": 1234, "address": "...",
       "language": "ur"}``
    """

    metadata = {}
    try:
        import orjson

        if getattr(job.room, "metadata", None):
            metadata = orjson.loads(job.room.metadata)
    except Exception:
        metadata = {}

    brand = metadata.get("brand_name", "the brand")
    customer = metadata.get("customer_name", "")
    order_no = metadata.get("order_number", "")
    address = metadata.get("address", "")
    total = metadata.get("total", 0)

    return (
        f"You are {DEFAULT_AGENT_NAME}, a polite Urdu-speaking customer service "
        f"agent for {brand}. You are calling to confirm a COD order.\n"
        f"Order #{order_no}, total {total} PKR, address: {address}.\n"
        f"Customer: {customer}.\n\n"
        "RULES:\n"
        "- Speak natural Urdu in Nastaliq when transcribed; speak it aloud naturally.\n"
        "- Max 25 words per turn unless asked to elaborate.\n"
        "- Use آپ (formal). Repeat numbers and addresses before tool calls.\n"
        "- Recording disclosure has already been played; don't repeat it.\n"
        "- If customer is angry after 2 turns, escalate.\n"
    )
