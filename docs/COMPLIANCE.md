# COMPLIANCE.md

Awaaz operates under multiple overlapping regulatory regimes. This document
states each in plain language and maps it to product / code-level controls.

---

## 1. WhatsApp Business Policy (primary channel)

Awaaz's primary channel is the WhatsApp Business Cloud API; merchants must
abide by Meta's WhatsApp Business Policy and Commerce Policy.

| Rule | Awaaz control |
|---|---|
| **Opt-in required** before sending any business-initiated message. | `wa_opt_ins` table; first WA template gated on a verified opt-in event from one of: Shopify checkout consent, WooCommerce checkbox, manual upload with merchant signed attestation. |
| **Approved utility templates** required outside the 24-hour customer service window. | `wa_templates` table tracks template names + Meta approval status; outbound dispatcher refuses to send a template that is not in `status='APPROVED'`. |
| **24-hour service window** for free-form replies. | FSM driver checks `last_inbound_at`; outside the window it falls back to the `order_confirmation_followup` template. |
| **No marketing without explicit marketing opt-in.** | Marketing templates are gated by a separate `marketing_opt_in_at` column. |
| **Quality rating** maintained (`HIGH` / `MEDIUM` / `LOW`). | Daily job pulls quality from Graph API; if `LOW`, automatically pauses outbound for that phone number. |

---

## 2. Pakistan Electronic Crimes Act (PECA) 2016 + 2025 Amendment

| Rule | Awaaz control |
|---|---|
| §13 (electronic forgery) — must not impersonate. | Agent introduces itself as automated, names the brand explicitly. |
| §24 (cyberstalking / harassment) — repeated unwanted contact. | Hard cap of 3 retry attempts per order; `dncr_list` honoured; opt-out keyword (`بند کریں`, `STOP`) suppresses all future contact for that hash. |
| §26A (2025) — false-info dissemination. | Agent never asserts unverifiable claims; tool outputs are quoted verbatim from store data. |

---

## 3. Pakistan Telecommunication Authority (PTA) — voice channel only

These apply **only when `FEATURE_VOICE_CHANNEL=true` and a store has
`voice_enabled=true`**.

| Rule | Awaaz control |
|---|---|
| **Spam Regulations 2009** + DNCR (Do-Not-Call Register, short-code 3627). | Weekly pull of DNCR list to `dncr_list` table; pre-dispatch lookup by phone hash; reject any number on the list. |
| **Time-of-day**: hard default 10:00–20:00 PKT; never 22:00–09:00. | `CALL_WINDOW_START_PKT` / `CALL_WINDOW_END_PKT` env + per-store override; dispatcher refuses to schedule outside window. |
| **Two-party consent recording** (PECA §13/§24, Constitution Art 14, *Benazir Bhutto v. President* 1997 SC). | Recording disclosure played as the first audio frame of every call; transcript persisted in `recordings.disclosure_played_at`. |
| **CVAS Voice License** (PTA suspended new applications since 22-Oct-2019; still suspended Apr 2026). | Awaaz operates as **a SaaS app on top of the merchant's licensed access provider**. Merchant T&Cs: merchant is the calling party. |
| **Caller ID**: only PTCL/Nayatel-allocated numbers; no spoofing. | `SIP_FROM_NUMBERS` env validated at startup against a whitelist; merchants cannot supply arbitrary CLI. |
| **Penalties**: PTA Re-org Act §31 — up to 3 years imprisonment, up to PKR 10M fine. | Strict opt-in + DNCR + 3-attempt cap drastically reduce exposure. |
| **Max 3 attempts per order**. | `MAX_RETRY_ATTEMPTS=3`; thereafter the order goes to `escalation_queue` for manual review. |

---

## 4. Personal Data Protection Act (PDPA) — Pakistan

The PDPA was tabled in 2025 and is **not yet enacted as of April 2026**.
Awaaz architects for compliance from day one:

| Anticipated rule | Awaaz control |
|---|---|
| Lawful basis for processing. | Opt-in event recorded for every WA contact; legitimate-interest justification documented for transactional voice. |
| Data minimisation. | Only phone, name, address, order details ingested. No DOB, CNIC, payment instruments. |
| In-country storage option. | Hybrid deployment supports Postgres + S3 in Pakistan (PTCL Smart Cloud); cloud-only defaults to AWS Mumbai (`ap-south-1`) which the bill currently treats as "approved jurisdiction". |
| Right to deletion. | `DELETE /v1/customers/{phone_hash}` async pseudonymizer. |
| Right of access. | Operator dashboard exposes per-customer transcript export. |
| Encryption at rest. | `pgcrypto pgp_sym_encrypt` for phone + address; SSE-KMS one-CMK-per-org for media. |
| Encryption in transit. | TLS 1.3 enforced on every external endpoint. |

---

## 5. GDPR (Shopify mandatory webhooks)

Shopify enforces GDPR-style webhooks on all public apps regardless of
merchant geography:

- `POST /webhooks/customers/data_request` → respond within 30 days with all
  data held about the customer.
- `POST /webhooks/customers/redact` → 10 days to delete customer data.
- `POST /webhooks/shop/redact` → 30 days after app uninstall, delete shop
  data.

All three are implemented in `apps/shopify-app/app/routes/webhooks.*` and
backed by background jobs in `apps/api/awaaz_api/workers/gdpr_worker.py`.

---

## 6. Data flow PII summary

| Field | Stored as | Sent to LLM? | Sent to STT? |
|---|---|---|---|
| Customer phone E.164 | `pgp_sym_encrypt(phone, key)` + `hmac_sha256(phone, hash_key)` | **No** — redacted (`<PHONE>`). | Allowed in audio (cannot redact at audio level pre-transcription). |
| Customer name | `pgp_sym_encrypt(name, key)` | Yes — first name only. | Yes (name is in audio anyway). |
| Address line | `pgp_sym_encrypt(line1+postal, key)` | City + province only after redaction. | Allowed in audio. |
| Order total | Plaintext (not PII). | Yes. | Yes. |
| Order line items | Plaintext (not PII). | Yes. | Yes. |
| Free-form customer reply | Persisted plaintext in `messages.body` *only if* PII redaction confidence ≥ 0.95; else stored encrypted. | Redacted form. | Raw audio retained encrypted, transcript redacted. |

---

## 7. Security review checklist (block release if any unchecked)

- [ ] All env-driven secrets (no hardcoded keys, tokens, phone numbers).
- [ ] Every webhook route verifies signature with `hmac.compare_digest`.
- [ ] Every tenant-scoped table has RLS + `FORCE ROW LEVEL SECURITY`.
- [ ] Every tenant-scoped query also filters by `store_id` at app level.
- [ ] PII columns encrypted with `pgp_sym_encrypt`.
- [ ] Phone lookups use `phone_hash`, never plaintext phone.
- [ ] LLM prompts redact phone, full name, full address.
- [ ] Outbound logs scrub PII via `structlog` processor.
- [ ] CSP headers + HSTS + X-Frame-Options on dashboard.
- [ ] Dependency scan green (Snyk / GitHub Dependabot).
- [ ] No use of `eval`, `exec`, or shell=True with user input.
- [ ] Rate limits per-tenant on every public endpoint.
- [ ] CVE-2025-29927: dashboard re-checks auth in Server Components and route handlers.
- [ ] Recording-consent disclosure plays as first audio frame on voice calls.
- [ ] Merchant cannot supply arbitrary CLI on voice channel.
- [ ] Opt-in event recorded before any WA template send.
- [ ] DNCR scrub passes before voice dispatch.
- [ ] Cost cap kills runaway conversations.
