# Awaaz Platform

**Conversational Urdu AI agent platform for Pakistani e-commerce — WhatsApp-first.**

Awaaz handles COD order confirmation, cancellation, rescheduling, change-request triage, and merchant escalation over WhatsApp Business Cloud API, with an optional voice channel layered on top of LiveKit Agents + Twilio/PTCL SIP.

The same code base supports a fully-cloud "zero-hardware" stack and a self-hosted local-LLM stack, swappable per-store via a single config flag.

---

## Why this exists

Existing Pakistani offerings (Robocalls.pk, Robocall.pk, bSecure) are press-1/press-2 IVR with pre-recorded MP3 prompts. Awaaz is a genuine LLM-driven conversational agent in Urdu, on the channel that matters most in Pakistan: WhatsApp.

---

## Architecture at a glance

```
                            ┌─────────────────────────────┐
                            │  Shopify / WooCommerce /    │
                            │  generic webhook / CSV      │
                            └──────────────┬──────────────┘
                                           │ order intake
                                           ▼
┌──────────────┐   webhook    ┌──────────────────────────┐
│ WhatsApp     │ ───────────▶ │   FastAPI control plane  │
│ (Cloud API)  │ ◀─────────── │   • tenant middleware    │
└──────────────┘   send       │   • PGQueuer dispatcher  │
       ▲                      │   • FSM driver           │
       │                      └──────────┬───────────────┘
       │                                 │ tools
       │                                 ▼
       │                  ┌──────────────────────────────┐
       │                  │  LLM (Claude Haiku 4.5)      │
       │                  │   prompt-cached, streaming   │
       │                  └──────────┬───────────────────┘
       │                             │
       │ optional voice-note replies │
       │ ┌──────────┐  ┌──────────┐  │
       └─│ Uplift   │  │ Deepgram │◀─┘ inbound voice notes
         │  TTS     │  │   STT    │
         └──────────┘  └──────────┘

         ┌──────────────────────────────────────────┐
         │  Postgres 16 (RLS + pgcrypto)            │
         │  Redis (PGQueuer, rate limits)           │
         │  S3/MinIO (media, recordings, SSE-KMS)   │
         └──────────────────────────────────────────┘

         ┌──────────────────────────────────────────┐
         │  Voice secondary channel (off by default)│
         │  LiveKit Agents + Twilio → PTCL SIP      │
         └──────────────────────────────────────────┘
```

Full diagram and latency budgets in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Repository layout

```
awaaz_platform/
├── apps/
│   ├── api/                 FastAPI control plane + WA webhook + FSM driver
│   ├── agent/               LiveKit voice agent (secondary channel)
│   ├── dashboard/           Next.js 15 + Better Auth admin UI
│   ├── shopify-app/         Shopify Public OAuth app
│   └── woocommerce-plugin/  WP/WooCommerce PHP plugin
├── packages/
│   ├── shared-types/        Pydantic ↔ Zod generated types
│   └── eval-harness/        LLM-as-customer simulator
├── infra/                   postgres init, livekit, otel, prometheus, grafana, nginx
├── .github/workflows/       CI per app + nightly evals + deploy
└── docs/                    SPEC, ARCHITECTURE, COMPLIANCE, COSTS, DEPLOYMENT, STATUS
```

---

## Getting started (local dev)

```bash
# 1. Toolchain check
python --version    # ≥ 3.11
node --version      # ≥ 20
docker --version    # ≥ 24

# 2. Configure environment
cp .env.example .env
# fill in API keys (Anthropic, Meta WA, etc.) — see docs/DEPLOYMENT.md §1

# 3. Bring up infra
make up
make db-migrate
make db-seed

# 4. Run a test conversation
make test-wa PHONE=+923331234567 ORDER_ID=test-1
```

A first-launch runbook (Meta WA app setup, Shopify Partner app, Stripe billing) lives in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

---

## Documentation

| Doc | Purpose |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Authoritative AI-coding-agent context — read at every session |
| [`docs/SPEC.md`](docs/SPEC.md) | Functional spec, FSM, scenarios, prompts, schemas |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Component diagrams, latency budgets, multi-tenancy isolation |
| [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) | WA Business Policy, PECA, PDPA, PTA voice rules |
| [`docs/COSTS.md`](docs/COSTS.md) | Per-conversation cost breakdown by stack and volume |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Cloud-only / self-hosted / hybrid deployment guides |
| [`docs/STATUS.md`](docs/STATUS.md) | Live status — what is implemented, tested, and pending creds |

---

## Status

Production-grade implementation complete; integration tests with real provider credentials pending merchant credential injection. See [`docs/STATUS.md`](docs/STATUS.md) for the current ship-readiness punch list.

## License

Proprietary — © 2026 Gelecek Solution. All rights reserved.
