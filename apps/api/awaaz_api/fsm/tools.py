"""Tool definitions exposed to the LLM.

Argument schemas are JSON Schema draft-2020-12 — Anthropic and OpenAI both
accept this format unchanged.
"""

from __future__ import annotations

from typing import Final, Literal

from awaaz_api.llm import ToolDefinition

ToolName = Literal[
    "confirm_order",
    "cancel_order",
    "reschedule_delivery",
    "flag_change_request",
    "flag_wrong_number",
    "flag_proxy_answerer",
    "escalate_to_human",
    "switch_language",
    "end_conversation",
]


def _idempotency_field() -> dict[str, object]:
    return {
        "type": "string",
        "minLength": 8,
        "maxLength": 64,
        "description": (
            "Stable client-generated identifier so retries don't double-apply. "
            "Use the conversation_id concatenated with the action name."
        ),
    }


_CONFIRM = ToolDefinition(
    name="confirm_order",
    description=(
        "Mark the COD order as confirmed. Call only after the customer has "
        "explicitly agreed to receive the delivery."
    ),
    input_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {"idempotency_key": _idempotency_field()},
        "required": ["idempotency_key"],
    },
)

_CANCEL = ToolDefinition(
    name="cancel_order",
    description=(
        "Mark the COD order as cancelled. Always include the customer's "
        "stated reason verbatim (translate to English if needed)."
    ),
    input_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "idempotency_key": _idempotency_field(),
            "reason": {
                "type": "string",
                "minLength": 1,
                "maxLength": 500,
                "description": "Customer's reason — verbatim or paraphrase.",
            },
            "reason_category": {
                "type": "string",
                "enum": [
                    "changed_mind",
                    "found_cheaper",
                    "address_wrong",
                    "ordered_by_mistake",
                    "out_of_budget",
                    "delivery_too_slow",
                    "other",
                ],
            },
        },
        "required": ["idempotency_key", "reason"],
    },
)

_RESCHEDULE = ToolDefinition(
    name="reschedule_delivery",
    description=(
        "Reschedule delivery to a customer-specified time. If the customer "
        "gives a vague answer (\"baad mein\"), use the label only and leave "
        "requested_iso null."
    ),
    input_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "idempotency_key": _idempotency_field(),
            "requested_iso": {
                "type": "string",
                "format": "date-time",
                "description": "ISO-8601 with timezone if the customer named a specific time.",
            },
            "requested_label": {
                "type": "string",
                "description": "What the customer literally said (\"کل صبح\")",
                "maxLength": 200,
            },
        },
        "required": ["idempotency_key", "requested_label"],
    },
)

_CHANGE = ToolDefinition(
    name="flag_change_request",
    description=(
        "Flag a change request (qty / item / address). Awaaz does NOT modify "
        "the order itself; the merchant's CS team handles it. Always log "
        "what the customer wants."
    ),
    input_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "idempotency_key": _idempotency_field(),
            "field": {"type": "string", "enum": ["quantity", "item", "address", "other"]},
            "requested_value": {"type": "string", "maxLength": 500},
        },
        "required": ["idempotency_key", "field", "requested_value"],
    },
)

_WRONG = ToolDefinition(
    name="flag_wrong_number",
    description="Customer denies any order. Mark this number as wrong / fake-order.",
    input_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {"idempotency_key": _idempotency_field()},
        "required": ["idempotency_key"],
    },
)

_PROXY = ToolDefinition(
    name="flag_proxy_answerer",
    description="The person on the line is not the buyer. Schedule a callback.",
    input_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "idempotency_key": _idempotency_field(),
            "callback_label": {"type": "string", "maxLength": 200},
        },
        "required": ["idempotency_key", "callback_label"],
    },
)

_ESCALATE = ToolDefinition(
    name="escalate_to_human",
    description=(
        "Escalate to a merchant operator. Use when: customer is angry after "
        "two turns, asks for a human, or the request is out-of-scope "
        "(returns/refunds/legal/large change)."
    ),
    input_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "idempotency_key": _idempotency_field(),
            "reason": {"type": "string", "minLength": 1, "maxLength": 500},
            "urgency": {"type": "string", "enum": ["low", "normal", "high", "critical"]},
        },
        "required": ["idempotency_key", "reason"],
    },
)

_SWITCH_LANG = ToolDefinition(
    name="switch_language",
    description="Change the conversation language going forward.",
    input_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "target_language": {"type": "string", "enum": ["ur", "en", "pa", "sd", "ps", "roman_ur"]},
        },
        "required": ["target_language"],
    },
)

_END = ToolDefinition(
    name="end_conversation",
    description="The conversation has wrapped up; politely close.",
    input_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {"reason": {"type": "string", "maxLength": 200}},
        "required": ["reason"],
    },
)

TOOL_DEFINITIONS: Final[dict[ToolName, ToolDefinition]] = {
    "confirm_order": _CONFIRM,
    "cancel_order": _CANCEL,
    "reschedule_delivery": _RESCHEDULE,
    "flag_change_request": _CHANGE,
    "flag_wrong_number": _WRONG,
    "flag_proxy_answerer": _PROXY,
    "escalate_to_human": _ESCALATE,
    "switch_language": _SWITCH_LANG,
    "end_conversation": _END,
}


def all_tool_names() -> set[ToolName]:
    return set(TOOL_DEFINITIONS)
