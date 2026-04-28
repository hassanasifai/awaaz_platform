"""State definitions + transition graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from .tools import ToolName

PROMPTS_DIR: Final[Path] = Path(__file__).parent / "prompts"


@dataclass(frozen=True, slots=True)
class State:
    name: str
    prompt_file: str
    allowed_tools: frozenset[ToolName]
    max_turns: int = 6
    is_terminal: bool = False
    description: str = ""

    def prompt_path(self) -> Path:
        return PROMPTS_DIR / self.prompt_file


_TERMINAL_STATES: Final[frozenset[str]] = frozenset(
    {"closing", "voicemail_fallback", "failed"}
)


def terminal_states() -> frozenset[str]:
    return _TERMINAL_STATES


# Tool → next-state mapping.  Used by the engine after a tool fires.  Sentinel
# 'default' applies when no tool fired in the turn (LLM produced text only).
TRANSITIONS: Final[dict[str, dict[str, str]]] = {
    "greeting":         {"default": "disclosure"},
    "disclosure":       {"default": "identity_verify"},
    "identity_verify":  {
        "flag_wrong_number": "wrong_number",
        "flag_proxy_answerer": "proxy_answerer",
        "switch_language": "language_fallback",
        "default": "order_recap",
    },
    "order_recap":      {"default": "confirm_intent"},
    "confirm_intent":   {
        "confirm_order": "closing",
        "cancel_order": "closing",
        "reschedule_delivery": "closing",
        "flag_change_request": "closing",
        "escalate_to_human": "closing",
        "default": "confirm_intent",  # stay until decision
    },
    "wrong_number":     {"default": "closing"},
    "proxy_answerer":   {"default": "closing"},
    "language_fallback": {"default": "greeting"},
    "out_of_scope":     {"escalate_to_human": "closing", "default": "closing"},
}


def build_state_registry() -> dict[str, State]:
    """Returns the canonical state map.  Pure — call once and cache."""

    return {
        "greeting": State(
            name="greeting",
            prompt_file="greeting.md",
            allowed_tools=frozenset(),
            max_turns=2,
            description="Open the conversation with a polite greeting.",
        ),
        "disclosure": State(
            name="disclosure",
            prompt_file="disclosure.md",
            allowed_tools=frozenset(),
            max_turns=1,
            description="Inform the customer the conversation is recorded.",
        ),
        "identity_verify": State(
            name="identity_verify",
            prompt_file="identity_verify.md",
            allowed_tools=frozenset(
                {"flag_wrong_number", "flag_proxy_answerer", "switch_language"}
            ),
            max_turns=3,
            description="Confirm we are talking to the named buyer.",
        ),
        "order_recap": State(
            name="order_recap",
            prompt_file="order_recap.md",
            allowed_tools=frozenset(),
            max_turns=2,
            description="Read back order details + total.",
        ),
        "confirm_intent": State(
            name="confirm_intent",
            prompt_file="confirm_intent.md",
            allowed_tools=frozenset(
                {
                    "confirm_order",
                    "cancel_order",
                    "reschedule_delivery",
                    "flag_change_request",
                    "escalate_to_human",
                }
            ),
            max_turns=6,
            description="Branch on customer intent.",
        ),
        "wrong_number": State(
            name="wrong_number",
            prompt_file="wrong_number.md",
            allowed_tools=frozenset(),
            max_turns=1,
            description="Apologize and end the conversation.",
        ),
        "proxy_answerer": State(
            name="proxy_answerer",
            prompt_file="proxy_answerer.md",
            allowed_tools=frozenset(),
            max_turns=2,
            description="Capture callback label and end.",
        ),
        "language_fallback": State(
            name="language_fallback",
            prompt_file="language_fallback.md",
            allowed_tools=frozenset({"switch_language"}),
            max_turns=2,
            description="Offer English/regional language and re-enter greeting.",
        ),
        "out_of_scope": State(
            name="out_of_scope",
            prompt_file="out_of_scope.md",
            allowed_tools=frozenset({"escalate_to_human"}),
            max_turns=2,
            description="Hand off to merchant operator.",
        ),
        "closing": State(
            name="closing",
            prompt_file="closing.md",
            allowed_tools=frozenset(),
            max_turns=1,
            is_terminal=True,
            description="Polite goodbye.",
        ),
        "voicemail_fallback": State(
            name="voicemail_fallback",
            prompt_file="voicemail.md",
            allowed_tools=frozenset(),
            max_turns=1,
            is_terminal=True,
            description="Voice channel only — leave a short message.",
        ),
        "failed": State(
            name="failed",
            prompt_file="closing.md",
            allowed_tools=frozenset(),
            max_turns=0,
            is_terminal=True,
            description="Unrecoverable state.",
        ),
    }
