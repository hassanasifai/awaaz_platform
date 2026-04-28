"""FSM driver — applies LLM tool outputs to advance the conversation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from awaaz_api.llm import (
    AssistantMessage,
    LLMProvider,
    Message,
    SystemMessage,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)
from awaaz_api.observability import get_logger

from .states import State, TRANSITIONS, build_state_registry, terminal_states
from .tools import TOOL_DEFINITIONS, ToolName

_log = get_logger("awaaz.fsm")


@dataclass(slots=True)
class ToolOutcome:
    name: ToolName
    arguments: dict[str, Any]
    text_result: str
    is_error: bool = False
    side_effect_done: bool = True


@dataclass(slots=True)
class FSMResult:
    assistant_text: str
    next_state: str
    tool_outcomes: list[ToolOutcome] = field(default_factory=list)
    finished: bool = False


class FSMDriver:
    """Pure orchestration — IO sits in the channel/storage layers."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm
        self._states = build_state_registry()

    @property
    def states(self) -> dict[str, State]:
        return self._states

    async def step(
        self,
        *,
        current_state: str,
        history: list[Message],
        latest_user_text: str,
        system_prompt: str,
        tool_handlers: dict[ToolName, "ToolHandler"],
        store_template_vars: dict[str, str] | None = None,
    ) -> FSMResult:
        state = self._states.get(current_state) or self._states["greeting"]
        if state.is_terminal:
            return FSMResult(
                assistant_text="",
                next_state=current_state,
                finished=True,
            )

        # Build the tool list visible to the LLM at *this* state only.
        available_tools = [TOOL_DEFINITIONS[t] for t in sorted(state.allowed_tools)]

        history.append(UserMessage(text=latest_user_text))

        response = await self._llm.chat(
            system=SystemMessage(text=system_prompt),
            messages=history,
            tools=available_tools or None,
            max_tokens=320,
            temperature=0.2,
        )

        outcomes: list[ToolOutcome] = []
        next_state_name = state.name

        if response.tool_calls:
            history.append(
                AssistantMessage(text=response.text, tool_calls=tuple(response.tool_calls))
            )
            for call in response.tool_calls:
                if call.name not in state.allowed_tools:
                    msg = (
                        f"Tool {call.name!r} is not allowed in state "
                        f"{state.name!r}. Allowed: "
                        f"{sorted(state.allowed_tools)}"
                    )
                    _log.warning("fsm.tool_rejected", state=state.name, tool=call.name)
                    outcomes.append(
                        ToolOutcome(
                            name=call.name,  # type: ignore[arg-type]
                            arguments=call.arguments,
                            text_result=msg,
                            is_error=True,
                            side_effect_done=False,
                        )
                    )
                    history.append(
                        ToolResultMessage(
                            tool_call_id=call.id, content=msg, is_error=True
                        )
                    )
                    continue
                handler = tool_handlers.get(call.name)  # type: ignore[arg-type]
                if handler is None:
                    msg = f"No handler registered for tool {call.name!r}."
                    outcomes.append(
                        ToolOutcome(
                            name=call.name,  # type: ignore[arg-type]
                            arguments=call.arguments,
                            text_result=msg,
                            is_error=True,
                            side_effect_done=False,
                        )
                    )
                    history.append(
                        ToolResultMessage(
                            tool_call_id=call.id, content=msg, is_error=True
                        )
                    )
                    continue
                outcome = await handler(call)
                outcomes.append(outcome)
                history.append(
                    ToolResultMessage(
                        tool_call_id=call.id,
                        content=outcome.text_result,
                        is_error=outcome.is_error,
                    )
                )
                # First valid tool decides the transition.
                if next_state_name == state.name and not outcome.is_error:
                    next_state_name = TRANSITIONS.get(state.name, {}).get(
                        call.name, next_state_name
                    )
        else:
            history.append(AssistantMessage(text=response.text))
            next_state_name = TRANSITIONS.get(state.name, {}).get(
                "default", state.name
            )

        finished = next_state_name in terminal_states()
        return FSMResult(
            assistant_text=response.text,
            next_state=next_state_name,
            tool_outcomes=outcomes,
            finished=finished,
        )


# Type alias for the per-tool callable signature.
from typing import Awaitable, Callable  # noqa: E402

ToolHandler = Callable[[ToolCall], Awaitable[ToolOutcome]]
