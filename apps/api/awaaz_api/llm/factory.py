"""Resolve the LLM provider from per-store config + env."""

from __future__ import annotations

from .base import LLMProvider


def build_llm_provider(
    *,
    provider_name: str,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> LLMProvider:
    if provider_name == "anthropic":
        from .anthropic import AnthropicLLM

        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY required")
        return AnthropicLLM(api_key=api_key, default_model=model or "claude-haiku-4-5-20251001")
    if provider_name in {"openai_compat", "vllm", "ollama"}:
        from .openai_compat import OpenAICompatLLM

        if not base_url:
            raise ValueError("base_url required for openai-compatible provider")
        return OpenAICompatLLM(
            base_url=base_url,
            api_key=api_key or "not-needed",
            default_model=model or "Qwen/Qwen3-8B-Instruct",
        )
    raise ValueError(f"unknown LLM provider {provider_name!r}")
