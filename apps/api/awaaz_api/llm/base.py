"""LLM provider Protocol + canonical message types."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True, slots=True)
class SystemMessage:
    text: str
    cache: bool = True


@dataclass(frozen=True, slots=True)
class UserMessage:
    text: str


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    text: str
    tool_calls: tuple["ToolCall", ...] = ()


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResultMessage:
    tool_call_id: str
    content: str
    is_error: bool = False


Message = SystemMessage | UserMessage | AssistantMessage | ToolResultMessage


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(slots=True)
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    model: str
    finish_reason: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LLMDelta:
    text: str = ""
    tool_call_chunk: ToolCall | None = None
    finish_reason: str | None = None


class LLMProvider(Protocol):
    name: str

    async def chat(
        self,
        *,
        system: SystemMessage,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        max_tokens: int = 800,
        temperature: float = 0.2,
        model: str | None = None,
        cache_control: Literal["ephemeral", "1h"] | None = "1h",
    ) -> LLMResponse: ...

    async def chat_stream(
        self,
        *,
        system: SystemMessage,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        max_tokens: int = 800,
        temperature: float = 0.2,
        model: str | None = None,
        cache_control: Literal["ephemeral", "1h"] | None = "1h",
    ) -> AsyncIterator[LLMDelta]:
        if False:  # pragma: no cover - typing scaffold
            yield LLMDelta()
