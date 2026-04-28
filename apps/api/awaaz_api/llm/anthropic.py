"""Anthropic Messages API adapter — Claude Haiku 4.5 default.

Caches the system prompt with ``cache_control: {type: "ephemeral"}`` and a
1-hour retention to amortise the dominant token cost across a multi-turn
conversation.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any, Literal

import anthropic

from awaaz_api.observability import get_logger
from awaaz_api.observability.metrics import llm_request_seconds

from .base import (
    AssistantMessage,
    LLMDelta,
    LLMResponse,
    Message,
    SystemMessage,
    ToolCall,
    ToolDefinition,
    ToolResultMessage,
    UserMessage,
)

_log = get_logger("awaaz.llm.anthropic")


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, *, api_key: str, default_model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = default_model

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
    ) -> LLMResponse:
        params = self._build_params(
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
            model=model,
            cache_control=cache_control,
            stream=False,
        )

        start = time.perf_counter()
        response = await self._client.messages.create(**params)
        latency = time.perf_counter() - start
        llm_request_seconds.labels(provider="anthropic", model=params["model"]).observe(
            latency
        )

        text = ""
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=dict(block.input or {}),
                    )
                )
        usage = response.usage
        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0),
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            model=response.model,
            finish_reason=response.stop_reason or "end_turn",
            raw=response.model_dump(),
        )

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
        params = self._build_params(
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
            temperature=temperature,
            model=model,
            cache_control=cache_control,
            stream=True,
        )
        async with self._client.messages.stream(**params) as stream:  # type: ignore[arg-type]
            async for chunk in stream.text_stream:
                yield LLMDelta(text=chunk)
            final = await stream.get_final_message()
            for block in final.content:
                if block.type == "tool_use":
                    yield LLMDelta(
                        tool_call_chunk=ToolCall(
                            id=block.id,
                            name=block.name,
                            arguments=dict(block.input or {}),
                        )
                    )
            yield LLMDelta(finish_reason=final.stop_reason or "end_turn")

    def _build_params(
        self,
        *,
        system: SystemMessage,
        messages: list[Message],
        tools: list[ToolDefinition] | None,
        max_tokens: int,
        temperature: float,
        model: str | None,
        cache_control: Literal["ephemeral", "1h"] | None,
        stream: bool,
    ) -> dict[str, Any]:
        # Anthropic system prompt as content blocks lets us mark cache_control.
        system_block: list[dict[str, Any]] = [{"type": "text", "text": system.text}]
        if system.cache and cache_control:
            system_block[0]["cache_control"] = (
                {"type": "ephemeral", "ttl": "1h"}
                if cache_control == "1h"
                else {"type": "ephemeral"}
            )

        msg_payload: list[dict[str, Any]] = []
        for m in messages:
            if isinstance(m, SystemMessage):
                # Should never happen — system goes via the dedicated param.
                continue
            if isinstance(m, UserMessage):
                msg_payload.append({"role": "user", "content": m.text})
            elif isinstance(m, AssistantMessage):
                content: list[dict[str, Any]] = []
                if m.text:
                    content.append({"type": "text", "text": m.text})
                for tc in m.tool_calls:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
                msg_payload.append({"role": "assistant", "content": content or [{"type": "text", "text": ""}]})
            elif isinstance(m, ToolResultMessage):
                msg_payload.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.tool_call_id,
                                "content": m.content,
                                "is_error": m.is_error,
                            }
                        ],
                    }
                )

        params: dict[str, Any] = {
            "model": model or self._model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_block,
            "messages": msg_payload,
        }
        if tools:
            params["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]
        return params
