# DEPLOYMENT.md

## 0. Prereqs (any deployment)

- Domain (DNS managed): `awaaz.pk` (or yours).
- Meta Business Account → WhatsApp Business App, system user with permanent
  access token, Phone Number ID, Business Account ID, App Secret, Verify
  Token.
- Anthropic API key.
- (Cloud-only) Deepgram API key, Uplift AI API key.
- (Voice channel) Twilio account or PTCL/Nayatel SIP credentials.
- Shopify Partner account (for Public OAuth app).
- Stripe account (for billing).
- AWS account (for KMS, S3 Mumbai) or self-hosted MinIO.

## 1. Configuration

Copy `.env.example` to `.env` and fill in the keys. Never commit `.env`.

For multi-environment deploys, use [Doppler](https://doppler.com), AWS Secrets
Manager, or HashiCorp Vault. The application reads only from `os.environ`;
the secret-store provider injects them at boot.

### 1.1 Required at minimum

```ini
DATABASE_URL=...
REDIS_URL=...
S3_*=...
BETTER_AUTH_SECRET=<32 random bytes>
PII_ENCRYPTION_KEY=<32 random bytes>
PHONE_HASH_KEY=<32 random bytes>
ANTHROPIC_API_KEY=...
META_WA_ACCESS_TOKEN=...
META_WA_PHONE_NUMBER_ID=...
META_WA_BUSINESS_ACCOUNT_ID=...
META_WA_APP_SECRET=...
META_WA_VERIFY_TOKEN=<random>
```

Generate the random keys: `openssl rand -hex 32`.

### 1.2 Webhook URLs to register

| Provider | URL pattern |
|---|---|
| Meta WhatsApp | `https://api.<domain>/v1/webhooks/wa/meta` |
| 360dialog | `https://api.<domain>/v1/webhooks/wa/dialog360` |
| Twilio Voice (if voice channel) | `https://api.<domain>/v1/webhooks/twilio/voice` |
| Twilio AMD callback | `https://api.<domain>/v1/webhooks/twilio/amd` |
| Stripe | `https://api.<domain>/v1/webhooks/stripe` |
| Shopify (set automatically on app install) | `https://api.<domain>/v1/webhooks/shopify/{topic}` |

---

## 2. Option A — Cloud-only zero-hardware ($30–100 / mo MVP)

Single VPS (Hetzner CX22 €4.59/mo, DigitalOcean $6, or PTCL Smart Cloud)
with Docker Compose.

```bash
ssh root@<vps>
git clone https://github.com/hassanasifai/awaaz_platform.git
cd awaaz_platform
cp .env.example .env && vim .env       # fill in
make up                                 # docker compose up -d --build
make db-migrate
```

Then point DNS:

```
api.<domain>     A   <vps-ip>
app.<domain>     A   <vps-ip>
livekit.<domain> A   <vps-ip>     # only if voice channel enabled
```

Reverse-proxy via Caddy or Nginx (config in `infra/nginx/awaaz.conf`).
Letsencrypt auto-issues TLS certs.

S3 recordings: configure either S3 Mumbai (`ap-south-1`) for prod, or run
the bundled MinIO container.

---

## 3. Option B — Self-hosted with local LLM ($1,800 capex + ~$100 / mo)

RTX 3090 24 GB box co-located at PTCL Smart Cloud Karachi or Nayatel
Islamabad.

```bash
# Same as Option A, but:
make up-gpu          # docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

The GPU override starts:
- `vllm` serving `Qwen/Qwen3-8B-Instruct-AWQ`
- `whisperlive` running `kingabzpro/whisper-large-v3-turbo-urdu` CT2 INT8
- `indic-parler` running AI4Bharat Indic-Parler-TTS

In `.env`, set:

```
LLM_PROVIDER=vllm
STT_PROVIDER=faster_whisper
TTS_PROVIDER=indic_parler
FEATURE_LOCAL_STACK=true
```

Per-store override is also possible via the dashboard
(`stores.agent_config.providers` JSONB).

---

## 4. Option C — Hybrid production (recommended at >$2K/mo revenue)

| Component | Where |
|---|---|
| FastAPI API + Next.js dashboard | AWS EKS Mumbai (`ap-south-1`) |
| Postgres | AWS RDS Mumbai |
| Redis | AWS ElastiCache Mumbai |
| S3 (recordings, media) | AWS S3 Mumbai with KMS CMK per org |
| LLM | Anthropic API (US, latency masked by streaming) |
| WhatsApp | Meta Cloud API (no infra) |
| Voice / SIP / LiveKit | PTCL Smart Cloud Karachi (low jitter to PK trunks) |
| Recordings tier-2 | S3 Glacier after 30d |

Terraform stubs in `infra/terraform/` (left as a separate effort — not
required for MVP).

---

## 5. First-launch runbook

1. `make up && make db-migrate`.
2. Visit `https://app.<domain>` → create org → create first store.
3. **Connect Meta WhatsApp:**
   - In Meta Business Manager, create a System User.
   - Generate a permanent token with `whatsapp_business_messaging`,
     `whatsapp_business_management`, `business_management` scopes.
   - Add the token + Phone Number ID + Business Account ID to the store
     settings (or `.env` for single-tenant dev).
   - Submit one utility template `order_confirmation_v1` for approval; wait
     ~5–10 min.
   - Set webhook URL to `https://api.<domain>/v1/webhooks/wa/meta` with
     verify token = `META_WA_VERIFY_TOKEN`. Subscribe to `messages` and
     `message_template_status_update` fields.
4. **Connect Shopify (optional):**
   - In Shopify Partners, create a Public App.
   - App URL: `https://app.<domain>/shopify`.
   - Allowed redirection URL: `https://app.<domain>/api/shopify/auth/callback`.
   - GDPR webhooks: `https://api.<domain>/v1/webhooks/shopify/customers/data_request` (and the redact ones).
   - Submit "Protected Customer Data" application — approval takes ~7 business days.
5. **Run a test conversation** to your own phone:
   ```bash
   make test-wa PHONE=+923331234567 ORDER_ID=test-1
   ```
6. **Verify:** message arrives, reply "ٹھیک ہے" → conversation completes
   with `outcome=confirmed` in the dashboard.
7. Configure Stripe billing — paste `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET`,
   set up product + price in Stripe dashboard.
8. **Go live** with rate-limited ramp:
   - Day 1: max 10 conversations / day.
   - Day 2: max 100.
   - Day 3+: full volume after WA quality rating remains `HIGH`.

---

## 6. CI / CD

- `.github/workflows/ci-api.yml` — ruff, mypy, pytest, alembic check
  (every push).
- `.github/workflows/ci-agent.yml` — same for the voice agent.
- `.github/workflows/ci-dashboard.yml` — typecheck, lint, Playwright e2e.
- `.github/workflows/eval-suite.yml` — nightly full eval (50 golden
  conversations); blocks merge if accuracy/conciseness regress > 5 %.
- `.github/workflows/deploy.yml` — on git tag `v*`, builds images, pushes
  to GHCR, SSH-deploys to `$DEPLOY_HOST`.

Set repository secrets:
- `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_KEY` (SSH).
- `GHCR_PAT` (PAT with `write:packages`).
- `STAGING_*`, `PROD_*` env JSON blobs that get materialized into `.env` on
  the target.

---

## 7. Observability bring-up

- `https://app.<domain>:3001` — Grafana (admin / admin on first login).
- `https://app.<domain>:3002` — Langfuse.
- Provision Loki / Tempo separately if you want full log + trace UI.
- Sentry: paste DSN into `.env`.

Dashboards in `infra/grafana/dashboards/`:
- `awaaz-fleet.json` — fleet-wide traffic, latency, confirmation rate.
- `awaaz-tenant.json` — per-store drill-down.
- `awaaz-cost.json` — cost burn vs budget.

---

## 8. Backup / DR

- **Postgres**: nightly `pg_dump` to S3 with 30-day retention; PITR via WAL
  archiving (RDS handles this automatically; self-hosted use `pgbackrest`).
- **MinIO/S3**: lifecycle rules — recordings 30d → Glacier, transcripts 90d →
  delete.
- **Secrets**: rotate `PII_ENCRYPTION_KEY` quarterly; supports ring of two
  keys for graceful rotation (current + previous).
- **Recovery objective**: RPO = 1h (WAL ship), RTO = 30 min.
