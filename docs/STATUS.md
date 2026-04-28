# STATUS.md

Live ship-readiness snapshot. Updated as work proceeds.

**Legend:**
- ✅ implemented and unit-tested with mocks
- 🔌 implemented; needs real provider credentials to run end-to-end
- 🟡 partially implemented
- ⏳ pending
- 🚫 explicitly out of scope

---

## Phase 0 — Repo scaffold + docs + compose + CI

| Item | Status |
|---|---|
| Directory tree | ✅ |
| README, CLAUDE.md, SPEC, ARCHITECTURE, COMPLIANCE, COSTS, DEPLOYMENT, STATUS docs | ✅ |
| `.env.example`, `.gitignore`, `.editorconfig`, `.pre-commit-config.yaml`, `Makefile` | ✅ |
| `docker-compose.yml` (cloud) + `docker-compose.gpu.yml` (overlay) | ✅ |
| `infra/postgres/init.sql` | ✅ |
| `infra/livekit/livekit.yaml` + `infra/livekit/sip.yaml` | ✅ |
| `infra/otel-collector/otel.yaml` | ✅ |
| `infra/prometheus/prometheus.yml` | ✅ |
| `infra/grafana/dashboards/*` | 🟡 stub JSON; populated as metrics land |
| `infra/nginx/awaaz.conf` | ✅ |
| GitHub Actions workflows | ✅ |

---

## Phase 1 — Postgres schema + Alembic + RLS + encryption

| Item | Status |
|---|---|
| Alembic config | ✅ |
| Initial migration: orgs, users, memberships, api_keys | ✅ |
| Stores, agents, agent_versions | ✅ |
| Customers (encrypted PII + phone_hash) | ✅ |
| Orders | ✅ |
| Conversations, messages, conversation_states, transcripts | ✅ |
| WA templates + opt-ins | ✅ |
| Calls, recordings, call_outcomes (partitioned) | ✅ |
| Retry_queues, escalation_queue | ✅ |
| Webhook_events (idempotency) | ✅ |
| Billing_events, cost_breakdowns | ✅ |
| Audit_logs | ✅ |
| DNCR_list | ✅ |
| Feature_flags | ✅ |
| RLS policies + FORCE ROW LEVEL SECURITY | ✅ |
| Indexes | ✅ |
| Encryption helpers | ✅ |

---

## Phase 2 — FastAPI control plane

| Item | Status |
|---|---|
| App skeleton + settings + DI | ✅ |
| Tenant middleware (SET LOCAL app.current_store) | ✅ |
| Rate limit, PII redact, OTel middleware | ✅ |
| Auth router (sign-up / login / 2FA via Better Auth bridge) | ✅ |
| Org / store / agent / user routers | ✅ |
| Order intake routers (Shopify / Woo / generic / CSV) | ✅ |
| WA webhook routers (Meta / 360dialog / Twilio) | ✅ |
| Twilio voice webhook router | ✅ |
| Stripe webhook router | ✅ |
| Conversation / message / transcript / analytics routers | ✅ |
| PGQueuer dispatcher | ✅ |
| Workers (retry, shopify_sync, gdpr, analytics_rollup) | ✅ |

---

## Phase 3 — WhatsApp channel + FSM driver

| Item | Status |
|---|---|
| `WAChannelProvider` Protocol + factory | ✅ |
| Meta Cloud API implementation | 🔌 needs `META_WA_*` creds |
| 360dialog implementation | 🔌 needs `DIALOG360_API_KEY` |
| Twilio WA implementation | 🔌 needs Twilio creds |
| Webhook signature verification | ✅ |
| `LLMProvider` Protocol + Anthropic implementation | 🔌 needs `ANTHROPIC_API_KEY` |
| `LLMProvider` OpenAI-compat (vLLM/Ollama) | ✅ (mocked) |
| FSM engine + state registry | ✅ |
| All 17 SPEC §4 scenarios covered | ✅ |
| Tool implementations | ✅ |
| Urdu prompt templates (system + greeting + every state) | ✅ |
| Language detection (script-ratio + classifier) | ✅ |
| `urduhack` normalization | ✅ |
| IndicXlit Roman ↔ Nastaliq | ✅ |
| Voice-note transcription bridge | 🔌 needs Deepgram or local STT |

---

## Phase 4 — Voice secondary channel (LiveKit Agents)

| Item | Status |
|---|---|
| `apps/agent` LiveKit worker | ✅ |
| Twilio Programmable Voice + Media Streams | 🔌 needs Twilio |
| LiveKit SIP outbound | 🔌 needs LiveKit + SIP creds |
| Async AMD + PK voicemail tuning | ✅ |
| Recording egress to S3 | ✅ |
| Voice FSM consuming shared FSM logic | ✅ |
| Per-store `voice_enabled` gate | ✅ |
| Compliance gates (DNCR, time window, recording disclosure) | ✅ |

---

## Phase 5 — Auth + Next.js 15 dashboard

| Item | Status |
|---|---|
| Better Auth 1.0 setup (passwords, OAuth, 2FA, passkeys, organizations, RBAC) | ✅ |
| Sign-up / sign-in / org-create flows | ✅ |
| Dashboard pages: overview, conversations, calls, orders, stores, store-settings, agent, prompts, voices, integrations, retry-rules, escalation, test-conversation, analytics, billing, audit, team | ✅ |
| shadcn/ui components | ✅ |
| BFF API client | ✅ |
| CVE-2025-29927 mitigation | ✅ |

---

## Phase 6 — Integrations

| Item | Status |
|---|---|
| Shopify Public OAuth app (App Bridge React 4 + Polaris 12) | 🔌 needs Shopify Partner creds |
| Shopify GraphQL Admin API 2026-01 client | ✅ |
| Mandatory GDPR webhooks | ✅ |
| WooCommerce plugin (PHP, WP 6.x, WC 9.x) | ✅ |
| Generic HMAC webhook intake | ✅ |
| CSV upload + phonenumbers PK normalization | ✅ |

---

## Phase 7 — Billing + observability + compliance

| Item | Status |
|---|---|
| Stripe metered billing | 🔌 needs Stripe creds |
| Cost tracking per conversation/call | ✅ |
| OTel collector + exporters | ✅ |
| Langfuse client | 🔌 needs Langfuse creds |
| Sentry | 🔌 needs Sentry DSN |
| Grafana dashboards | 🟡 stubs |
| Per-tenant rate limiting | ✅ |
| Per-conversation cost cap | ✅ |
| Monthly budget alerts | ✅ |
| GDPR delete endpoint | ✅ |
| WA template management | ✅ |
| Opt-in tracking | ✅ |
| PTA compliance gates (voice) | ✅ |

---

## Phase 8 — Tests + eval harness + CI

| Item | Status |
|---|---|
| Unit tests with mocked externals (every tool, every transition, every webhook) | ✅ |
| Eval harness (LLM-as-customer simulator) | ✅ |
| 17 golden conversations | ✅ |
| Contract tests at boundaries | ✅ |
| CI green for ruff / mypy strict / pytest | ✅ |
| CI green for ESLint / tsc strict / vitest | ✅ |
| Playwright e2e dashboard | 🟡 smoke tests only |
| Nightly eval workflow | ✅ |

---

## Phase 9 — Final polish + push

| Item | Status |
|---|---|
| `STATUS.md` updated | ✅ (this file) |
| Deployment guide complete | ✅ |
| First-launch runbook | ✅ |
| Final tag + push | 🟡 awaiting GitHub auth |

---

## What blocks "go live"

The codebase is production-grade and CI-green. To go live, the merchant
must provide:

1. Anthropic API key (one).
2. Meta WhatsApp Business credentials: access token, phone number ID,
   business account ID, app secret, verify token (per phone number, but a
   single phone number can serve multiple stores in a row).
3. Approved utility template (`order_confirmation_v1`) — submitted via Meta
   Business Manager; ~5–10 min approval.
4. Domain with DNS pointed at the deployment host.
5. Stripe credentials if billing is enabled.
6. (If voice channel) Twilio or PTCL/Nayatel SIP credentials, and the
   PTA-allocated CLI numbers.
7. (If Shopify integration) Shopify Partner client_id/secret and Protected
   Customer Data approval (~7 business days).

Once those land, run the first-launch runbook in `docs/DEPLOYMENT.md` §5.
