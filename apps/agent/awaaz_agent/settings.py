"""Voice-agent worker settings — narrower than the API but mirrors keys."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    # LiveKit
    livekit_url: str = "ws://livekit:7880"
    livekit_api_key: SecretStr = SecretStr("devkey")
    livekit_api_secret: SecretStr = SecretStr("devsecret")
    livekit_sip_outbound_trunk_id: str = ""

    # Provider selection (mirrors API)
    llm_provider: Literal["anthropic", "openai_compat", "ollama", "vllm"] = "anthropic"
    stt_provider: Literal["deepgram", "faster_whisper"] = "deepgram"
    tts_provider: Literal["upliftai", "indic_parler", "piper"] = "upliftai"

    # API keys
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model_fast: str = "claude-haiku-4-5-20251001"
    deepgram_api_key: SecretStr = SecretStr("")
    deepgram_model: str = "nova-3"
    deepgram_language: str = "ur"
    deepgram_keyterms: str = ""
    upliftai_api_key: SecretStr = SecretStr("")
    upliftai_voice_id: str = "v_meklc281"
    upliftai_output_format_telephony: str = "MULAW_8000"
    upliftai_base_url: AnyHttpUrl = Field(default="https://api.upliftai.org")  # type: ignore[assignment]

    # Local
    vllm_base_url: AnyHttpUrl = Field(default="http://vllm:8000/v1")  # type: ignore[assignment]
    vllm_model: str = "Qwen/Qwen3-8B-Instruct-AWQ"
    faster_whisper_model: str = "kingabzpro/whisper-large-v3-turbo-urdu"
    faster_whisper_compute_type: str = "int8_float16"
    faster_whisper_device: str = "cuda"
    indic_parler_model: str = "ai4bharat/indic-parler-tts"
    piper_voice_path: str = "/models/piper/ur_PK-fasih-medium.onnx"

    # Twilio (for outbound dial / AMD)
    twilio_account_sid: str = ""
    twilio_auth_token: SecretStr = SecretStr("")
    twilio_from_number: str = ""
    twilio_amd_async: bool = True
    twilio_amd_mode: str = "DetectMessageEnd"
    twilio_amd_speech_end_threshold: int = 2500
    twilio_amd_timeout: int = 45

    # SIP (production)
    sip_provider: Literal["ptcl", "nayatel", "twilio"] = "ptcl"
    sip_host: str = ""
    sip_username: str = ""
    sip_password: SecretStr = SecretStr("")
    sip_from_numbers: str = ""

    # Compliance
    call_window_start_pkt: str = "10:00"
    call_window_end_pkt: str = "20:00"
    max_retry_attempts: int = 3
    per_call_cost_cap_usd: float = 0.50

    # OTel
    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"
    otel_service_name: str = "awaaz-agent"

    @property
    def deepgram_keyterm_list(self) -> list[str]:
        return [k.strip() for k in self.deepgram_keyterms.split(",") if k.strip()]


@lru_cache(maxsize=1)
def get_settings() -> AgentSettings:
    return AgentSettings()
