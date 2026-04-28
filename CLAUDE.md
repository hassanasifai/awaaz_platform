# CLAUDE.md — Awaaz Platform

This file is read by Claude Code at the start of every session.  Keep it
authoritative; keep it tight.

## What this project is

Awaaz is a **multi-tenant conversational Urdu AI agent platform for Pakistani
e-commerce, WhatsApp-first**, with an optional voice channel layered on top of
LiveKit Agents + Twilio/PTCL SIP.

The agent handles COD order confirmation, cancellation, rescheduling, change
requests, voicemail/no-answer fallback, language fallback, wrong-number, and
human-escalation scenarios.  Merchants onboard via Shopify, WooCommerce,
generic webhook, or CSV upload.

## Architectural decisions (do not reopen)

- **Primary channel: WhatsApp Business Cloud API (Meta direct).**  Provider
  abstraction supports `meta_cloud`, `dialog360`, `twilio_wa` as drop-in
  alternatives via the `WA_PROVIDER` env var.
- **Conversation engine: deterministic FSM** in `apps/api/awaaz_api/fsm/`.
  States and transitions are coded; the LLM only fills slots and chooses tools
  at the current node.  *The LLM never picks the next state directly.*
- **LLM: Claude Haiku 4.5** (`claude-haiku-4-5-20251001`).  Promote to Sonnet
  4.6 only for tool-orchestration nodes that need deeper reasoning.  System
  prompt cached with `cache_control: ephemeral` + 1-hour retention.
- **Voice (secondary channel, off by default):** LiveKit Agents 1.5.6+,
  Deepgram Nova-3 STT (`language=ur`), Uplift AI Orator TTS
  (`v_meklc281`, `MULAW_8000` telephony), Silero VAD v6.2.1, LiveKit
  `MultilingualModel` turn detector with Hindi proxy.  Twilio Programmable
  Voice MVP → PTCL/Nayatel SIP production.  Gated by per-store
  `voice_enabled` flag *and* global `FEATURE_VOICE_CHANNEL` env.
- **Local stack (toggle):** faster-whisper
  (`kingabzpro/whisper-large-v3-turbo-urdu` CT2 INT8) + vLLM
  (`Qwen/Qwen3-8B-Instruct-AWQ` or `enstazao/Qalb-1.0-8B-Instruct`) +
  Indic-Parler-TTS (Apache-2.0).  Piper "fasih" Urdu CPU fallback.
  **Inference engine:** vLLM for production (continuous batching, PagedAttention,
  OpenAI-compatible).  Ollama for dev only.  **Never** TGI (maintenance mode
  since 2025-12-11).
- **Backend:** FastAPI 0.115+ + Postgres 16 + Redis.  Postgres extensions:
  `pgcrypto`, `uuid-ossp`, `pgvector`, `pg_partman`, `pg_cron`.  RLS with
  `FORCE ROW LEVEL SECURITY` *plus* application-level `store_id` filtering
  (defense in depth).
- **Retry queue:** **PGQueuer** (Postgres `LISTEN/NOTIFY` + `FOR UPDATE SKIP
  LOCKED`).  No Celery / Redis broker — keep it transactionally consistent
  with order updates.
- **Dashboard:** Next.js 15 App Router + TypeScript strict + Tailwind +
  shadcn/ui + **Better Auth 1.0+**.  Polaris only inside the Shopify embedded
  admin.  **CVE-2025-29927 mitigation:** never trust Next.js middleware-only
  auth; always re-check session in Server Components and route handlers.
- **Observability:** OpenTelemetry across the full conversation (single
  `trace_id` from webhook → FSM → LLM → outbound) + Langfuse self-hosted +
  Sentry + structlog JSON logs + Grafana/Prometheus.
- **Storage:** S3-compatible (AWS S3 Mumbai prod / MinIO dev) with SSE-KMS,
  one CMK per organization.

## Hard rules — every PR must respect these

1. The **LLM never drives state transitions**.  The FSM does.  LLM tool calls
   produce slot updates and edge selections only.
2. **Never** use Phi-4 (English-only), Aya Expanse (CC-BY-NC), XTTS-v2 (CPML),
   or Deepgram Flux (no Urdu) in commercial paths.
3. **Never** send raw audio with PII to Anthropic — only redacted/transcribed
   text.
4. **Never** spoof CLI on the voice channel — only PTCL/Nayatel-allocated
   numbers.
5. **Always** verify webhook signatures with `hmac.compare_digest`.
6. **Always** encrypt phone + address at rest with `pgcrypto`; use the
   `phone_hash` HMAC column for lookups.
7. **Always** tag every log line and span with `tenant_id`, `conversation_id`
   or `call_id`, and `trace_id`.
8. **Always** use idempotency keys on side-effecting tools.
9. **Always** record an opt-in event before sending the first WA template.
10. **Never** trust Next.js middleware-only auth — re-check in Server
    Components and API route handlers (CVE-2025-29927).
11. Voice channel obeys 10:00–20:00 PKT calling window, 3-attempt cap, DNCR
    scrub.  The WA channel obeys WhatsApp's 24-hour customer service window
    and template-message rules outside it.
12. **No hardcoded tenant IDs, secrets, phone numbers, or business rules.**
    Everything is env-driven or per-store JSONB config.

## Code style

- **Python 3.11+**, ruff (line length 100), black, mypy strict, pytest-asyncio.
- **TypeScript strict**, no `any`, Zod runtime validation at boundaries.
- **Conventional Commits.**  Branches: `feat/<scope>-<short>`, `fix/...`, etc.
- **Comments only when WHY is non-obvious.**  Don't narrate WHAT.
- **Tests required** for every tool, every state transition, every webhook
  signature path, every provider implementation.

## When asking the user

Batch business questions at end-of-phase, not mid-phase.  Architecture is
fixed.  If you need API keys, ask in a single message.

## Definition of Done per phase

See `docs/STATUS.md` for the ship-readiness punch list.  CI must be green
before merge.
