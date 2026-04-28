"""Centralised, validated configuration.

All env vars referenced anywhere else in the API live here.  Importing modules
should never read ``os.environ`` directly — they should depend on
``get_settings()``.

Conventions:
- Anything secret-shaped is annotated as ``SecretStr`` so it stops leaking into
  log messages and ``str(settings)``.
- Defaults are dev-safe (none of them are production-usable secrets).
- Provider-selection knobs live as Literal-typed string fields so we get type
  checking on every dispatch.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

WAProvider = Literal["meta_cloud", "dialog360", "twilio_wa"]
LLMProvider = Literal["anthropic", "openai_compat", "ollama", "vllm"]
STTProvider = Literal["deepgram", "faster_whisper", "indicconformer"]
TTSProvider = Literal["upliftai", "indic_parler", "piper"]
SMSProvider = Literal["sendpk", "twilio", "jazz_a2p"]
SipProvider = Literal["ptcl", "nayatel", "twilio"]
LogFormat = Literal["json", "console"]
Environment = Literal["development", "test", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------------- App ----------------
    environment: Environment = "development"
    app_base_url: AnyHttpUrl = Field(default="http://localhost:3000")  # type: ignore[assignment]
    api_base_url: AnyHttpUrl = Field(default="http://localhost:8000")  # type: ignore[assignment]
    log_level: str = "INFO"
    log_format: LogFormat = "json"
    tz: str = "Asia/Karachi"
    worker_concurrency: int = 4
    awaaz_role: Literal["api", "worker"] = "api"

    # ---------------- DB ----------------
    database_url: str = (
        "postgresql+asyncpg://awaaz:devpassword@postgres:5432/awaaz"
    )
    database_url_sync: str = (
        "postgresql+psycopg://awaaz:devpassword@postgres:5432/awaaz"
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # ---------------- Redis ----------------
    redis_url: str = "redis://redis:6379/0"

    # ---------------- S3 ----------------
    s3_endpoint: str | None = "http://minio:9000"
    s3_region: str = "us-east-1"
    s3_bucket_recordings: str = "awaaz-recordings"
    s3_bucket_media: str = "awaaz-media"
    s3_access_key: SecretStr = SecretStr("minioadmin")
    s3_secret_key: SecretStr = SecretStr("minioadmin")
    s3_use_ssl: bool = False
    s3_kms_key_id: str | None = None

    # ---------------- Auth ----------------
    better_auth_secret: SecretStr = SecretStr(
        "dev-only-replace-me-with-32-byte-random-string-XX"
    )
    better_auth_url: AnyHttpUrl = Field(default="http://localhost:3000")  # type: ignore[assignment]
    auth_session_ttl_seconds: int = 60 * 60 * 24 * 30
    auth_trusted_origins: str = "http://localhost:3000"

    # ---------------- Encryption ----------------
    pii_encryption_key: SecretStr = SecretStr("dev-only-replace-me-32-bytes-pii")
    phone_hash_key: SecretStr = SecretStr("dev-only-replace-me-32-bytes-phone")
    webhook_hmac_default_key: SecretStr = SecretStr(
        "dev-only-replace-me-32-bytes-webhook"
    )

    # ---------------- Provider selection ----------------
    wa_provider: WAProvider = "meta_cloud"
    llm_provider: LLMProvider = "anthropic"
    stt_provider: STTProvider = "deepgram"
    tts_provider: TTSProvider = "upliftai"

    # ---------------- WhatsApp — Meta Cloud ----------------
    meta_wa_access_token: SecretStr = SecretStr("")
    meta_wa_phone_number_id: str = ""
    meta_wa_business_account_id: str = ""
    meta_wa_app_secret: SecretStr = SecretStr("")
    meta_wa_verify_token: SecretStr = SecretStr("dev-verify-token")
    meta_wa_api_version: str = "v21.0"
    meta_wa_graph_base: AnyHttpUrl = Field(default="https://graph.facebook.com")  # type: ignore[assignment]

    # ---------------- WhatsApp — 360dialog ----------------
    dialog360_api_key: SecretStr = SecretStr("")
    dialog360_base_url: AnyHttpUrl = Field(default="https://waba-v2.360dialog.io")  # type: ignore[assignment]

    # ---------------- WhatsApp — Twilio ----------------
    twilio_wa_account_sid: str = ""
    twilio_wa_auth_token: SecretStr = SecretStr("")
    twilio_wa_from: str = "whatsapp:+14155238886"

    # ---------------- Anthropic ----------------
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model_fast: str = "claude-haiku-4-5-20251001"
    anthropic_model_deep: str = "claude-sonnet-4-6"
    anthropic_prompt_cache_ttl: Literal["5m", "1h"] = "1h"

    # ---------------- Deepgram ----------------
    deepgram_api_key: SecretStr = SecretStr("")
    deepgram_model: str = "nova-3"
    deepgram_language: str = "ur"
    deepgram_keyterms: str = ""

    # ---------------- Uplift AI ----------------
    upliftai_api_key: SecretStr = SecretStr("")
    upliftai_voice_id: str = "v_meklc281"
    upliftai_output_format_voice_note: str = "MP3_22050_32"
    upliftai_output_format_telephony: str = "MULAW_8000"
    upliftai_base_url: AnyHttpUrl = Field(default="https://api.upliftai.org")  # type: ignore[assignment]

    # ---------------- Local stack ----------------
    vllm_base_url: AnyHttpUrl = Field(default="http://vllm:8000/v1")  # type: ignore[assignment]
    vllm_model: str = "Qwen/Qwen3-8B-Instruct-AWQ"
    ollama_base_url: AnyHttpUrl = Field(default="http://ollama:11434/v1")  # type: ignore[assignment]
    ollama_model: str = "qwen3:8b-instruct-q4_K_M"
    faster_whisper_base_url: AnyHttpUrl = Field(default="http://whisperlive:9090")  # type: ignore[assignment]
    faster_whisper_model: str = "kingabzpro/whisper-large-v3-turbo-urdu"
    indic_parler_base_url: AnyHttpUrl = Field(default="http://indic-parler:9091")  # type: ignore[assignment]
    indic_parler_model: str = "ai4bharat/indic-parler-tts"
    piper_voice_path: str = "/models/piper/ur_PK-fasih-medium.onnx"

    # ---------------- LiveKit ----------------
    livekit_url: str = "ws://livekit:7880"
    livekit_api_key: SecretStr = SecretStr("devkey")
    livekit_api_secret: SecretStr = SecretStr(
        "devsecret-replace-with-random-32-bytes"
    )
    livekit_sip_inbound_trunk_id: str = ""
    livekit_sip_outbound_trunk_id: str = ""

    # ---------------- Twilio Programmable Voice ----------------
    twilio_account_sid: str = ""
    twilio_auth_token: SecretStr = SecretStr("")
    twilio_from_number: str = ""
    twilio_amd_async: bool = True
    twilio_amd_mode: str = "DetectMessageEnd"
    twilio_amd_speech_end_threshold: int = 2500
    twilio_amd_timeout: int = 45

    # ---------------- SIP ----------------
    sip_provider: SipProvider = "ptcl"
    sip_host: str = ""
    sip_username: str = ""
    sip_password: SecretStr = SecretStr("")
    sip_from_numbers: str = ""

    # ---------------- Shopify ----------------
    shopify_api_key: str = ""
    shopify_api_secret: SecretStr = SecretStr("")
    shopify_scopes: str = (
        "read_orders,write_orders,read_customers,read_products"
    )
    shopify_app_url: AnyHttpUrl = Field(default="http://localhost:3000")  # type: ignore[assignment]
    shopify_webhook_version: str = "2026-01"

    # ---------------- SMS ----------------
    sms_provider: SMSProvider = "sendpk"
    sms_api_key: SecretStr = SecretStr("")
    sms_sender_id: str = "AWAAZ"

    # ---------------- Stripe ----------------
    stripe_secret_key: SecretStr = SecretStr("")
    stripe_publishable_key: str = ""
    stripe_webhook_secret: SecretStr = SecretStr("")
    stripe_price_per_conversation_usd: float = 0.05
    stripe_price_per_voice_min_usd: float = 0.07

    # ---------------- Observability ----------------
    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"
    otel_service_name: str = "awaaz-api"
    otel_resource_attributes: str = (
        "service.namespace=awaaz,deployment.environment=development"
    )
    langfuse_public_key: SecretStr = SecretStr("")
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_host: AnyHttpUrl = Field(default="http://langfuse:3000")  # type: ignore[assignment]
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1

    # ---------------- Compliance ----------------
    pta_dncr_list_path: str = "/var/awaaz/dncr.txt"
    call_window_start_pkt: str = "10:00"
    call_window_end_pkt: str = "20:00"
    wa_service_window_hours: int = 24
    max_retry_attempts: int = 3
    recording_retention_days: int = 30
    transcript_retention_days: int = 90
    per_conversation_cost_cap_usd: float = 0.50
    per_call_cost_cap_usd: float = 0.50

    # ---------------- Rate limits ----------------
    rate_limit_webhook_per_minute: int = 600
    rate_limit_api_per_minute: int = 300
    rate_limit_dispatch_per_minute: int = 60

    # ---------------- Feature flags ----------------
    feature_voice_channel: bool = False
    feature_local_stack: bool = False
    feature_shopify_integration: bool = True
    feature_woocommerce_integration: bool = True

    # ---------------- Validation ----------------
    @field_validator("call_window_start_pkt", "call_window_end_pkt")
    @classmethod
    def _check_window(cls, v: str) -> str:
        h, m = v.split(":")
        if not (0 <= int(h) < 24 and 0 <= int(m) < 60):
            raise ValueError(f"invalid HH:MM time {v!r}")
        return v

    @field_validator("max_retry_attempts")
    @classmethod
    def _cap_retries(cls, v: int) -> int:
        # Hard PECA-driven cap to limit harassment-claim exposure.
        if v > 5:
            raise ValueError(
                "MAX_RETRY_ATTEMPTS must be ≤ 5 (PECA §24 risk cap)"
            )
        if v < 1:
            raise ValueError("MAX_RETRY_ATTEMPTS must be ≥ 1")
        return v

    # ---------------- Convenience ----------------
    @property
    def trusted_origins(self) -> list[str]:
        return [o.strip() for o in self.auth_trusted_origins.split(",") if o.strip()]

    @property
    def sip_caller_pool(self) -> list[str]:
        return [n.strip() for n in self.sip_from_numbers.split(",") if n.strip()]

    @property
    def deepgram_keyterm_list(self) -> list[str]:
        return [k.strip() for k in self.deepgram_keyterms.split(",") if k.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton — call this everywhere."""
    return Settings()
