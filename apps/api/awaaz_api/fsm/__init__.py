"""Conversation state machine.

Deterministic — the LLM never picks the next state, the FSM does. The LLM
fills slots and chooses tools at the *current* node; tool outcomes drive
transitions.
"""

from __future__ import annotations

from .engine import FSMDriver, FSMResult
from .states import State, build_state_registry, terminal_states
from .tools import TOOL_DEFINITIONS, ToolName, all_tool_names

__all__ = [
    "FSMDriver",
    "FSMResult",
    "State",
    "TOOL_DEFINITIONS",
    "ToolName",
    "all_tool_names",
    "build_state_registry",
    "terminal_states",
]
