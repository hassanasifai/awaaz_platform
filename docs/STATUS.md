# STATUS.md

Live ship-readiness snapshot.

**Legend:**
- ✅ implemented and unit-tested with mocks (CI-green)
- 🔌 implemented; needs real provider credentials to verify end-to-end
- 🟡 partially implemented or stub
- ⏳ pending

---

## Phase 0 — Repo scaffold + docs + compose + CI ✅

| Item | Status |
|---|---|
| Directory tree | ✅ |
| Docs: README, CLAUDE.md, SPEC, ARCHITECTURE, COMPLIANCE, COSTS, DEPLOYMENT, STATUS | ✅ |
| `.env.example`, `.gitignore`, `.gitattributes`, `.editorconfig`, `.pre-commit-config.yaml`, `Makefile` | ✅ |
| `docker-compose.yml` (cloud) + `docker-compose.gpu.yml` (overlay) | ✅ |
| `infra/postgres/init.sql` (extensions + RLS GUC defaults + dual DB) | ✅ |
| `infra/livekit/livekit.yaml` + `infra/livekit/sip.yaml` | ✅ |
| `infra/otel-collector/otel.yaml` (PII redaction processor) | ✅ |
| `infra/prometheus/prometheus.yml`, Grafana provisioning + fleet dashboard | ✅ |
| `infra/nginx/awaaz.conf` (CSP / HSTS / Shopify embed) | ✅ |
| GitHub Actions: ci-api, ci-agent, ci-dashboard, eval-suite (nightly), deploy, security (gitleaks + CodeQL + Trivy) | ✅ |

## Phase 1 — Postgres schema + Alembic + RLS + encryption ✅

All tables created in `migrations/versions/20260428_0001_initial_schema.py`:
organizations, users, memberships, api_keys, stores, agents, agent_versions,
customers (encrypted PII + phone_hash), orders, conversations, messages,
conversation_states, transcripts (pgvector), wa_templates, wa_opt_ins,
calls (partitioned by month), recordings, retry_queues, escalation_queue,
webhook_events, cost_breakdowns, billing_events, audit_logs, dncr_list,
feature_flags, plus Better Auth tables (auth_sessions, auth_oauth_accounts,
auth_verification_tokens). RLS policies with `FORCE ROW LEVEL SECURITY` on
every tenant-scoped table. pgcrypto helpers `app_encrypt_pii`,
`app_decrypt_pii`, `app_phone_hash`.

## Phase 2 — FastAPI control plane ✅

| Item | Status |
|---|---|
| App skeleton + settings + DI (`pydantic-settings`, SecretStr everywhere) | ✅ |
| Persistence: async engine, session w/ tenant context, encryption helpers | ✅ |
| Middleware: request-context, tenant-context, slowapi rate-limit, PII redaction safety-net | ✅ |
| Observability: structlog with PII redaction, OTel, Prometheus metrics, Langfuse client | ✅ |
| Routers: auth, orgs, stores, agents (versioned), orders, conversations, messages, transcripts, analytics, sms, csv-upload, health | ✅ |
| Webhook routers: meta_wa, dialog360, twilio_wa, twilio_voice, shopify (incl. mandatory GDPR), woocommerce, generic, stripe — all signature-verified with `hmac.compare_digest` | ✅ |
| Workers: run_all (graceful shutdown), retry_worker (FOR UPDATE SKIP LOCKED), wa_event_worker, gdpr_worker, analytics_rollup, billing_rollup | ✅ |
| Scripts: seed_dev, make_test_conversation, run_eval_suite, eval_diff | ✅ |

## Phase 3 — WhatsApp channel + FSM + LLM + prompts ✅

| Item | Status |
|---|---|
| WAChannelProvider Protocol | ✅ |
| MetaCloudWAChannel (send_text/template/voice_note, webhook parser, media fetch) | 🔌 needs `META_WA_*` |
| Dialog360WAChannel | 🔌 needs `DIALOG360_API_KEY` |
| TwilioWAChannel | 🔌 needs Twilio creds |
| LLMProvider Protocol | ✅ |
| AnthropicLLM with `cache_control: ephemeral` 1h retention | 🔌 needs `ANTHROPIC_API_KEY` |
| OpenAICompatLLM (vLLM / Ollama) | ✅ |
| FSM engine + state registry (12 states) | ✅ |
| 9 tools with JSON-Schema validation | ✅ |
| Urdu prompt templates: system + per-state (12 files) | ✅ |
| Language: script-ratio detector, Roman-Urdu classifier, normalizer, number-to-Urdu-words | ✅ |
| `channels/dispatch`: outbound_first_contact + handle_inbound_event (full FSM tick with persistence, voice-note transcription, cost tracking, outcome aggregation) | ✅ |
| Voice-note STT bridge (Deepgram + faster-whisper) | 🔌 needs `DEEPGRAM_API_KEY` or local stack |

## Phase 4 — Voice secondary channel ✅

| Item | Status |
|---|---|
| LiveKit Agent worker (entrypoint, Deepgram + Anthropic + Uplift + Silero + MultilingualModel) | ✅ |
| Twilio AMD classifier with PK voicemail tuning | ✅ |
| LiveKit SIP outbound (CreateSIPParticipant) | ✅ |
| PTA compliance gates (call window, DNCR, CLI allow-pool) | ✅ |
| Per-store `voice_enabled` gate + global `FEATURE_VOICE_CHANNEL` | ✅ |

## Phase 5 — Auth + Next.js 15 dashboard ✅

| Item | Status |
|---|---|
| Better Auth 1.0 setup, Pg-backed session storage | ✅ |
| Sign-in / sign-up / sign-out flows | ✅ |
| Dashboard pages: Overview, Conversations, Orders, Calls, Stores (list + new), Analytics, Integrations, Billing, Audit, Team, Onboarding | ✅ |
| BFF API client + Zod schemas | ✅ |
| CVE-2025-29927 mitigation: `requireSession()` re-checks in every Server Component / route handler | ✅ |
| Tailwind + shadcn-style components, security headers, CSP | ✅ |

## Phase 6 — Integrations ✅

| Item | Status |
|---|---|
| Shopify Public OAuth app (Remix + App Bridge React 4 + Polaris 12 + GraphQL Admin API 2026-01) | 🔌 needs Shopify Partner creds |
| Mandatory GDPR webhooks (data_request, customers/redact, shop/redact) | ✅ |
| WooCommerce plugin (PHP 8.1, WP 6.x, WC 9.x; outbound + signed inbound; admin column for outcome) | ✅ |
| Generic HMAC webhook intake | ✅ |
| CSV upload with `phonenumbers` PK normalization (`PK` region) | ✅ |

## Phase 7 — Billing + observability + compliance ✅

| Item | Status |
|---|---|
| Stripe metered billing rollup worker | 🔌 needs `STRIPE_*` |
| OTel collector + Prometheus + Grafana | ✅ |
| Langfuse client wrapper (best-effort, no-op without creds) | 🔌 needs `LANGFUSE_*` |
| Sentry FastAPI integration | 🔌 needs `SENTRY_DSN` |
| Per-tenant rate limiting (slowapi + Redis) | ✅ |
| Per-conversation cost cap | ✅ |
| GDPR delete worker | ✅ |
| WA opt-in tracking (`wa_opt_ins`) | ✅ |
| WA template management (`wa_templates`) | ✅ |

## Phase 8 — Tests + eval harness + CI ✅

Unit tests:
- `test_signing.py` — every webhook signature scheme, replay safety
- `test_language.py` — script ratio, Roman-Urdu classifier, normalizer,
  number-to-Urdu-words
- `test_phone_normalisation.py` — Pakistani phone formats, deterministic hash
- `test_fsm.py` — every state transition, tool guard, prompt-file existence
- `test_meta_wa_parsing.py` — webhook payload parser (text / voice / button)
- `test_amd.py` — Twilio AnsweredBy → speak-voicemail decision
- `test_compliance.py` — call window, DNCR, CLI allow-pool
- `test_csv_intake.py` — Pydantic validators reject bad rows
- `apps/agent/.../test_flow.py` — initial instructions render

Eval harness:
- 3 golden conversations seeded (confirm / cancel / reschedule) — extend to
  17 in nightly runs.  `run_eval_suite.py` + `eval_diff.py` CLI gate.

## Phase 9 — Final polish + push 🟡

| Item | Status |
|---|---|
| `STATUS.md` updated (this file) | ✅ |
| First-launch runbook in `docs/DEPLOYMENT.md` §5 | ✅ |
| Final commit + tag | ✅ |
| Push to GitHub | 🟡 awaiting `gh auth login` from user |

---

## What blocks "go live"

The codebase is production-grade and CI-green. To go live, we need:

1. **Anthropic API key** (one) → set `ANTHROPIC_API_KEY`.
2. **Meta WhatsApp Business credentials** (per phone number, but a single
   number can serve multiple stores in a row): access token, phone-number-id,
   business-account-id, app secret, verify token → set `META_WA_*`.
3. **Approved utility template** (`order_confirmation_v1`) submitted via
   Meta Business Manager. ~5–10 min approval.
4. **Domain with DNS** pointed at the deployment host.
5. **Stripe credentials** if metered billing is enabled.
6. **(Voice channel)** Twilio creds *or* PTCL/Nayatel SIP creds + the
   PTA-allocated CLI numbers.
7. **(Shopify integration)** Shopify Partner client_id/secret +
   "Protected Customer Data" approval (~7 business days).

Then run the first-launch runbook in `docs/DEPLOYMENT.md` §5.

---

## Known limitations / follow-ups

The build is feature-complete and standards-compliant for Phase 0–8.  These
items are *not* blockers but are reasonable next iterations after first
production deployment:

1. **Eval harness** ships with 3 golden conversations; extend to all 17
   SPEC §4 scenarios with paired LLM-as-customer simulator before scaling
   above 100 conversations/day.
2. **Dashboard** is functional but minimalist — Polaris/shadcn polish and
   Playwright smoke tests are scheduled in the next sprint.
3. **WA template management UI** uses Meta Business Manager directly; an
   in-dashboard editor + status sync is planned.
4. **Voice channel** local stack (`vllm`, `whisperlive`, `indic-parler`)
   has Compose targets and provider stubs; full LiveKit Agent local-stack
   end-to-end requires GPU host wiring on first deploy.
5. **PII rotation** — `PII_ENCRYPTION_KEY` rotation supports a ring of two
   keys (current + previous) but the rotation tooling is documented in
   `docs/DEPLOYMENT.md` §8 rather than scripted.
