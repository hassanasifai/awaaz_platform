"""OpenAI-compatible chat-completions adapter (vLLM, Ollama, llama.cpp server)."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any, Literal

from openai import AsyncOpenAI

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

_log = get_logger("awaaz.llm.openai_compat")


class OpenAICompatLLM:
    name = "openai_compat"

    def __init__(self, *, base_url: str, api_key: str, default_model: str) -> None:
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)
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
        cache_control: Literal["ephemeral", "1h"] | None = None,
    ) -> LLMResponse:
        params = self._build_params(
            system, messages, tools, max_tokens, temperature, model, stream=False
        )
        start = time.perf_counter()
        resp = await self._client.chat.completions.create(**params)
        llm_request_seconds.labels(provider="openai_compat", model=params["model"]).observe(
            time.perf_counter() - start
        )
        choice = resp.choices[0]
        text = choice.message.content or ""
        tool_calls: list[ToolCall] = []
        for tc in choice.message.tool_calls or []:
            tool_calls.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=__import__("orjson").loads(tc.function.arguments or b"{}"),
                )
            )
        usage = resp.usage
        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            cache_read_tokens=0,
            cache_creation_tokens=0,
            model=resp.model,
            finish_reason=choice.finish_reason or "stop",
            raw=resp.model_dump(),
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
        cache_control: Literal["ephemeral", "1h"] | None = None,
    ) -> AsyncIterator[LLMDelta]:
        params = self._build_params(
            system, messages, tools, max_tokens, temperature, model, stream=True
        )
        stream = await self._client.chat.completions.create(**params)
        async for chunk in stream:  # type: ignore[union-attr]
            choice = chunk.choices[0] if chunk.choices else None
            if not choice:
                continue
            delta = choice.delta
            if delta.content:
                yield LLMDelta(text=delta.content)
            if choice.finish_reason:
                yield LLMDelta(finish_reason=choice.finish_reason)

    def _build_params(
        self,
        system: SystemMessage,
        messages: list[Message],
        tools: list[ToolDefinition] | None,
        max_tokens: int,
        temperature: float,
        model: str | None,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        oa_msgs: list[dict[str, Any]] = [{"role": "system", "content": system.text}]
        for m in messages:
            if isinstance(m, UserMessage):
                oa_msgs.append({"role": "user", "content": m.text})
            elif isinstance(m, AssistantMessage):
                if m.tool_calls:
                    oa_msgs.append(
                        {
                            "role": "assistant",
                            "content": m.text or None,
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.name,
                                        "arguments": __import__("orjson").dumps(tc.arguments).decode(),
                                    },
                                }
                                for tc in m.tool_calls
                            ],
                        }
                    )
                else:
                    oa_msgs.append({"role": "assistant", "content": m.text})
            elif isinstance(m, ToolResultMessage):
                oa_msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": m.tool_call_id,
                        "content": m.content,
                    }
                )
        params: dict[str, Any] = {
            "model": model or self._model,
            "messages": oa_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if tools:
            params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]
        return params
