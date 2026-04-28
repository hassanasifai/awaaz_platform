"""FSM tests — every state transition + tool guard."""

from __future__ import annotations

from typing import Any

import pytest

from awaaz_api.fsm.engine import FSMDriver, ToolOutcome
from awaaz_api.fsm.states import build_state_registry, terminal_states
from awaaz_api.fsm.tools import TOOL_DEFINITIONS, all_tool_names
from awaaz_api.llm.base import (
    AssistantMessage,
    LLMProvider,
    LLMResponse,
    Message,
    SystemMessage,
    ToolCall,
)


class _FakeLLM:
    """Returns a programmable response for each `chat` call."""

    name = "fake"

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)

    async def chat(
        self,
        *,
        system: SystemMessage,
        messages: list[Message],
        tools=None,
        max_tokens: int = 800,
        temperature: float = 0.2,
        model: str | None = None,
        cache_control=None,
    ) -> LLMResponse:
        if not self._responses:
            raise RuntimeError("no scripted responses left")
        return self._responses.pop(0)

    async def chat_stream(self, **_kwargs: Any):  # pragma: no cover
        if False:
            yield None


def _resp(text: str = "", *tool_calls: ToolCall) -> LLMResponse:
    return LLMResponse(
        text=text,
        tool_calls=list(tool_calls),
        input_tokens=100,
        output_tokens=20,
        cache_read_tokens=80,
        cache_creation_tokens=0,
        model="fake",
        finish_reason="end_turn",
    )


@pytest.mark.asyncio
async def test_greeting_advances_to_disclosure():
    driver = FSMDriver(_FakeLLM([_resp("Salam")]))
    result = await driver.step(
        current_state="greeting",
        history=[],
        latest_user_text="ji",
        system_prompt="dummy",
        tool_handlers={},
    )
    assert result.next_state == "disclosure"
    assert not result.finished


@pytest.mark.asyncio
async def test_confirm_intent_with_confirm_tool_closes_conversation():
    async def handler(call: ToolCall) -> ToolOutcome:
        return ToolOutcome(name="confirm_order", arguments=call.arguments, text_result="ok")

    driver = FSMDriver(
        _FakeLLM(
            [
                _resp(
                    "great",
                    ToolCall(
                        id="t1",
                        name="confirm_order",
                        arguments={"idempotency_key": "abc12345"},
                    ),
                )
            ]
        )
    )
    result = await driver.step(
        current_state="confirm_intent",
        history=[],
        latest_user_text="haan ji",
        system_prompt="dummy",
        tool_handlers={"confirm_order": handler},
    )
    assert result.next_state == "closing"
    assert result.finished
    assert result.tool_outcomes[0].name == "confirm_order"


@pytest.mark.asyncio
async def test_disallowed_tool_in_state_is_rejected():
    """Calling a tool not in the state's allowed set must NOT transition."""

    async def handler(call: ToolCall) -> ToolOutcome:  # pragma: no cover
        raise AssertionError("must not be invoked")

    # Try to call confirm_order from greeting (where no tools are allowed).
    driver = FSMDriver(
        _FakeLLM(
            [
                _resp(
                    "",
                    ToolCall(id="t1", name="confirm_order", arguments={"idempotency_key": "x" * 8}),
                )
            ]
        )
    )
    result = await driver.step(
        current_state="greeting",
        history=[],
        latest_user_text="hi",
        system_prompt="dummy",
        tool_handlers={"confirm_order": handler},
    )
    assert result.tool_outcomes[0].is_error
    assert result.next_state == "greeting"


def test_every_state_has_a_prompt_file():
    states = build_state_registry()
    for name, st in states.items():
        assert st.prompt_path().exists(), f"missing prompt for {name}: {st.prompt_path()}"


def test_terminal_states_match_state_flags():
    states = build_state_registry()
    flagged = {n for n, s in states.items() if s.is_terminal}
    assert flagged == terminal_states()


def test_all_tools_have_definitions():
    assert set(TOOL_DEFINITIONS) == all_tool_names()
    for name, t in TOOL_DEFINITIONS.items():
        assert t.name == name
        assert "type" in t.input_schema
        assert "properties" in t.input_schema
