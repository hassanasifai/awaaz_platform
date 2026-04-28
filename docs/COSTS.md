# COSTS.md

All figures USD unless noted. Last updated April 2026.

---

## 1. Per-conversation cost — WhatsApp primary channel

A "conversation" is one inbound + assistant round-trip session, lasting up to
24 hours of WA service window. Average production conversation: ~5 turns
(2 user + 3 assistant) + 1 outbound utility template.

### 1.1 Cloud stack (zero-hardware)

| Component | Per conversation | Notes |
|---|---|---|
| WA Cloud API utility template (Pakistan) | $0.0190 | Meta business-initiated category, PK rate Apr 2026 |
| WA Cloud API service messages (free) | $0.0000 | Within 24h window |
| Anthropic Claude Haiku 4.5 (cached, ~3K in / 400 out total) | $0.0050 | `cache_read=$0.10/MTok`, `output=$5/MTok`, ~75% cache hit |
| Deepgram Nova-3 (only if customer sends voice notes, ~10s avg) | $0.0013 | $0.0077/min |
| Uplift Orator (only if voice-note replies enabled, ~50 chars) | $0.0010 | Hobby tier; Pro tier amortizes lower |
| OTel + Langfuse + Sentry (allocation) | $0.0005 | Self-hosted infra cost, amortized |
| **Total** | **≈ $0.027** | **≈ Rs. 7.5 per conversation** |

### 1.2 Self-hosted local stack

| Component | Per conversation |
|---|---|
| WA Cloud API utility template | $0.0190 |
| Local LLM (Qwen3-8B AWQ on RTX 3090, ~50ms TTFT, amortized) | $0.0006 |
| faster-whisper (only voice notes, amortized) | $0.0001 |
| Indic-Parler (only voice-note replies, amortized) | $0.0002 |
| Infra amortized ($100/mo / 50K conv) | $0.0020 |
| **Total** | **≈ $0.022** | **≈ Rs. 6.1 per conversation** |

The WA Cloud API utility template is the dominant cost — local stack only
saves ~$0.005 per conversation. **Local stack pays off only at high volumes
where merchants want zero per-token markup or in-country data-residency
guarantees.**

---

## 2. Per-call cost — voice secondary channel (PK mobile, 60s avg)

### 2.1 Twilio MVP

| Component | $/min | $/call (60s) |
|---|---|---|
| Twilio PK mobile termination | 0.180 | 0.180 |
| Twilio Media Streams | 0.004 | 0.004 |
| Twilio Async AMD (engaged) | 0.0075 | 0.0075 |
| Deepgram Nova-3 streaming | 0.0077 | 0.0077 |
| Anthropic Haiku 4.5 (cached) | 0.0035 | 0.0035 |
| Uplift Orator (Hobby) | 0.05/min | 0.050 |
| LiveKit Cloud (or self-hosted, $0) | 0.01 | 0.010 |
| **Total** | — | **≈ $0.26 / call** |

### 2.2 PTCL/Nayatel SIP + paid Uplift tier

| Component | $/min | $/call (60s) |
|---|---|---|
| PTCL termination (Rs. 2/min @ 280 PKR/USD) | 0.0071 | 0.0071 |
| Deepgram Nova-3 streaming | 0.0077 | 0.0077 |
| Anthropic Haiku 4.5 (cached) | 0.0035 | 0.0035 |
| Uplift Orator (Pro tier, amortized) | 0.020 | 0.020 |
| LiveKit OSS self-hosted | 0 | 0 |
| **Total** | — | **≈ $0.038 / call** |

### 2.3 Self-hosted everything

| Component | $/call (60s) |
|---|---|
| PTCL termination | 0.0071 |
| Local LLM/STT/TTS (amortized) | 0.0009 |
| Infra amortized | 0.0040 |
| **Total** | **≈ $0.012 / call (≈ Rs. 3.4)** |

---

## 3. Monthly projections — typical Pakistani DTC store

Assume 1,000 orders/mo, 70 % attempt rate, 30 % go through voice escalation.

| Volume profile | Cloud-only cost | PTCL+Pro cost | Self-hosted cost |
|---|---|---|---|
| 700 conversations + 210 voice-call escalations | $19 + $55 = **$74** | $19 + $8 = **$27** | $15 + $3 = **$18** |

Pricing tiers (recommended):

| Tier | $/mo | Conversations | Voice mins included | Margin (cloud) |
|---|---|---|---|---|
| Starter | $29 | 500 | 0 | $16 |
| Growth | $99 | 2,500 | 500 | $35 |
| Scale | $299 | 10,000 | 3,000 | $90 |
| Enterprise | custom | — | — | — |

Pakistan-rupee retail target: Rs. 8–12 per conversation (still 30–50 %
under incumbent voice IVR pricing).

---

## 4. Cost guardrails (enforced in code)

| Variable | Default | Behavior on breach |
|---|---|---|
| `PER_CONVERSATION_COST_CAP_USD` | $0.05 | FSM moves to `closing` with a templated message. |
| `PER_CALL_COST_CAP_USD` | $0.50 | Voice agent hangs up; voice channel marked `cost_cap`. |
| Per-store monthly budget | merchant-set | 50 % alert (email), 80 % alert (email + WA), 100 % auto-pause. |
| Anomaly detection | rolling 7-day P95 × 3 | Page on-call. |

---

## 5. Cost telemetry pipeline

Every external call writes a row to `cost_breakdowns`:

```sql
CREATE TABLE cost_breakdowns (
    id            uuid primary key default gen_random_uuid(),
    org_id        uuid not null,
    store_id      uuid not null,
    conversation_id uuid,
    call_id       uuid,
    component     text not null,    -- 'wa_template' | 'llm' | 'stt' | 'tts' | 'sip' | ...
    provider      text not null,    -- 'meta_cloud' | 'anthropic' | 'deepgram' | 'upliftai' | 'twilio' | 'ptcl'
    units         numeric not null, -- e.g. tokens, minutes, characters
    unit_cost_usd numeric not null,
    total_cost_usd numeric generated always as (units * unit_cost_usd) stored,
    occurred_at   timestamptz not null default now(),
    metadata      jsonb
);
```

Hourly job rolls these into `billing_events` per (org_id, hour). Stripe usage
records reported once per hour. OTel attributes
`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
`gen_ai.cache_read_tokens`, `gen_ai.cache_creation_tokens` feed the LLM rows.
