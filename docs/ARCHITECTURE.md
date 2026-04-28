# ARCHITECTURE.md

## 1. Component diagram

```
┌─────────────────┐
│ Shopify / Woo / │
│ CSV / generic   │── HMAC verified webhook ──┐
└─────────────────┘                           │
                                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                  FastAPI control plane (apps/api)                   │
│ ┌────────────┐  ┌────────────┐  ┌───────────┐  ┌────────────────┐  │
│ │ Tenant MW  │  │ Rate-limit │  │ PII redact│  │ OTel middleware │  │
│ └────────────┘  └────────────┘  └───────────┘  └────────────────┘  │
│ ┌────────────┐  ┌────────────────────────────────────────────────┐ │
│ │ Routers    │  │ FSM driver (apps/api/awaaz_api/fsm/engine.py) │ │
│ │ — /v1/...  │  │   states • transitions • slot validation      │ │
│ └────────────┘  └─────────────────────┬──────────────────────────┘ │
│                                       │ tools                       │
│                                       ▼                              │
│        ┌────────────────────────────────────────────────────┐       │
│        │ LLM client (apps/api/awaaz_api/llm/anthropic.py)   │       │
│        │   prompt-cached, streaming, redacted               │       │
│        └────────────────────────────────────────────────────┘       │
└────────────────────────────────────────────────────────────────────┘
        │                                                  │
        │ outbound message                                 │ persist
        ▼                                                  ▼
┌─────────────────┐                              ┌──────────────────┐
│ WA Cloud API /  │                              │ Postgres 16      │
│ 360dialog /     │                              │ (RLS + pgcrypto) │
│ Twilio WA       │                              │ Redis (rate)     │
└─────────────────┘                              │ S3 / MinIO       │
        ▲                                        └──────────────────┘
        │ inbound webhook
        │
┌─────────────────┐
│  Customer       │
└─────────────────┘

       Voice secondary channel (FEATURE_VOICE_CHANNEL=true):

       ┌──────────────┐    SIP    ┌──────────────────────┐
       │ PTCL/Twilio  │──────────▶│ LiveKit Agents       │
       │ trunk        │           │ (apps/agent)         │
       └──────────────┘           │  Deepgram + Haiku +  │
                                  │  Uplift + Silero     │
                                  └──────────────────────┘
```

## 2. Latency budgets

### 2.1 WhatsApp (primary) — user-perceived

| Component | P50 | P95 |
|---|---|---|
| Webhook ingest + sig verify | 30 ms | 80 ms |
| FSM tick + slot validation | 10 ms | 30 ms |
| LLM TTFT (cached prefix) | 400 ms | 700 ms |
| LLM stream completion (~80 tok) | 800 ms | 1500 ms |
| Outbound WA Cloud API | 250 ms | 600 ms |
| **Total** | **~1.5 s** | **~2.9 s** |

For chat the user does not perceive sub-second timing as critical — typing
indicator is shown via WA's mark-as-read API while we generate.

### 2.2 Voice (secondary) — round-trip

Target P50 ≤ 1.4 s, P90 ≤ 2.0 s.

| Component | Budget |
|---|---|
| User stops speaking → Silero VAD silence | 550 ms (`min_silence_duration=0.55`) |
| Deepgram Nova-3 final transcript | 100 ms |
| Anthropic Haiku 4.5 TTFT (cached) | 400 ms |
| Uplift Orator first audio chunk | 250 ms |
| Network egress to Pakistan | 60 ms |
| **Perceived total** | **~1,360 ms** |

## 3. Multi-tenancy isolation

Three layers of isolation, applied in order:

1. **Application-level `store_id` filtering.** Every repository method takes
   a `store_id` and includes it in `WHERE` clauses. Tested.
2. **Postgres RLS with `FORCE ROW LEVEL SECURITY`.** Every tenant-scoped
   table has policies keyed off `current_setting('app.current_store')`.
   Middleware sets the GUC on every request; the `awaaz_app` role cannot
   bypass it (table owner does not bypass when `FORCE` is set).
3. **Per-org KMS CMK for object storage.** S3/MinIO server-side encryption
   uses a different KMS key per organization, so even an exfiltration of one
   bucket does not leak another tenant's data.

Indexes: every `store_id` column is indexed. Every tenant-scoped table has
a composite `(store_id, created_at DESC)` index for time-range queries.

## 4. State machine engine

`apps/api/awaaz_api/fsm/engine.py` implements a deterministic state machine.
Each state is a Python dataclass with:

- `name: str`
- `system_prompt_path: Path`
- `allowed_tools: set[str]`
- `required_slots: set[str]`
- `max_turns: int`
- `transitions: dict[ToolName | "timeout" | "default", State]`

The driver loop is:

```python
while not state.is_terminal:
    user_msg = await channel.next_message(conversation)
    redacted = redact_pii(user_msg)
    llm_response = await llm.chat_stream(
        system=state.system_prompt(),
        messages=[*history, redacted],
        tools=state.tool_schemas(),
    )
    if llm_response.tool_calls:
        outcome = await fsm.apply_tools(llm_response.tool_calls, state)
        state = state.transition(outcome)
    await channel.send(conversation, llm_response.text)
```

The LLM **never** receives a "next state" choice. It only chooses tools.
The FSM picks the next state from the tool outcome.

## 5. Provider abstraction

Every external integration is behind a `Protocol` interface.  Drop-in
swappable per-store via `stores.agent_config.providers` JSONB or via env.

```python
class WAChannelProvider(Protocol):
    async def send_text(self, to: str, text: str, *, idempotency_key: str) -> SentMessage: ...
    async def send_template(self, to: str, template: str, params: list[str]) -> SentMessage: ...
    async def send_voice_note(self, to: str, audio_url: str) -> SentMessage: ...
    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool: ...
    def parse_inbound(self, body: bytes) -> InboundMessage: ...

class LLMProvider(Protocol):
    async def chat_stream(self, *, system, messages, tools, cache_control) -> AsyncIterator[LLMDelta]: ...

class STTProvider(Protocol):
    async def transcribe_audio(self, audio: bytes, *, language: str) -> Transcript: ...

class TTSProvider(Protocol):
    async def synthesize(self, text: str, *, voice_id: str, format: str) -> bytes: ...
```

Implementations live in `apps/api/awaaz_api/channels/`,
`apps/api/awaaz_api/llm/`, `apps/api/awaaz_api/integrations/`, and the voice-
specific stack in `apps/agent/awaaz_agent/providers/`.

## 6. Data flow — inbound message lifecycle

1. Meta WhatsApp Cloud API POSTs webhook to `/v1/webhooks/wa/meta`.
2. Middleware verifies `X-Hub-Signature-256` HMAC against `META_WA_APP_SECRET`.
3. Idempotency: payload `entry[].id` checked against `webhook_events` table.
4. Tenant resolution: `meta_wa_phone_number_id` → `stores.wa_phone_number_id`.
5. Tenant context set: `SET LOCAL app.current_store = '<uuid>'`.
6. Conversation looked up by `(store_id, customer_phone_hash)`.
7. Inbound message persisted to `messages`.
8. Voice notes downloaded → transcribed (Deepgram cloud / faster-whisper local) → text persisted.
9. PII redaction middleware strips phone numbers / addresses from the version sent to the LLM.
10. FSM driver reads current state, calls LLM with cached system prompt + history + tool schemas.
11. LLM streams response; tool calls are validated against `state.allowed_tools`; rejected calls are echoed back to the LLM as an error.
12. Tool side-effects fire (DB writes, Shopify GraphQL mutations) with idempotency keys.
13. Final assistant message sent via WA channel provider.
14. Cost breakdown row written from OTel span attributes (`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`).
15. Outcome event published to `escalation_queue` if `escalate_to_human` was called.

## 7. Deployment topology

### 7.1 Cloud-only (MVP)

Single Hetzner CX22 / DigitalOcean / PTCL Smart Cloud VPS (~$12/mo). Docker
Compose runs Postgres, Redis, MinIO, FastAPI API, Next.js dashboard, OTel
collector, Prometheus, Grafana, Langfuse. All AI calls to managed APIs.

### 7.2 Self-hosted (price-sensitive merchants)

RTX 3090 24 GB box, vLLM + faster-whisper + Indic-Parler in containers,
LiveKit OSS SFU also self-hosted. CPU+1 GPU = ~$1,800 capex, ~$100/mo opex.

### 7.3 Hybrid (recommended at scale)

App + DB on AWS Mumbai (`ap-south-1`), media/SIP server in Pakistan (PTCL
Smart Cloud or Data Vault Pakistan H100 cluster), LLM via Anthropic API.

## 8. Observability

- **Single `trace_id`** propagated webhook → FSM → LLM → outbound provider.
- **OTel collector** receives spans + metrics from API, Agent, Dashboard. Exports to Tempo (traces) and Prometheus (metrics).
- **Langfuse** receives every LLM call with prompt, response, latency, cost, model, version. Drives prompt iteration and eval gating.
- **Sentry** captures unhandled exceptions and slow transactions.
- **Grafana dashboards** ship in `infra/grafana/dashboards/`:
  - `awaaz-fleet.json` — aggregated traffic, latency, confirmation rate.
  - `awaaz-tenant.json` — per-store drill-down.
  - `awaaz-cost.json` — cost burn vs budget, anomaly detection.
- **structlog JSON** with mandatory fields: `tenant_id`, `store_id`,
  `conversation_id` or `call_id`, `trace_id`, `span_id`, `level`, `event`.

## 9. Failure modes

| Failure | Detection | Mitigation |
|---|---|---|
| WA Cloud API 5xx | provider retry (jittered exp backoff up to 60s) | After 3 failures, mark conversation `provider_failure`, surface in operator queue. |
| LLM rate limit | `anthropic.RateLimitError` | Token-bucket per-tenant; queue requests, 4xx the user with retry-after if depth > 100. |
| Webhook flood | rate-limit middleware + circuit breaker | Per-tenant cap; reject with 429. |
| Postgres failover | asyncpg pool reconnects + retries idempotent writes | Sentry alert; no message loss because PGQueuer rows persisted. |
| Eval suite regression > 5 % | nightly GHA workflow | Block merge; page on-call. |
| Cost cap exceeded | DB trigger + worker | Auto-pause store (+ email/WA alert to owner). |
