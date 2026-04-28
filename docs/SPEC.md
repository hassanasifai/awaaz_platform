# SPEC.md — Awaaz Functional Specification

**Channel ordering:** WhatsApp Business Cloud API is the **primary** channel.
Voice (LiveKit + Twilio/PTCL SIP) is a **secondary** escalation/fallback
channel, gated by per-store `voice_enabled` flag and the global
`FEATURE_VOICE_CHANNEL` env var.

---

## 1. Personas

| Persona | Description |
|---|---|
| **Merchant Owner** | Signs up, creates org + first store, connects integration, sets billing. Role: `owner`. |
| **Merchant Admin** | Configures agent prompt, voice ID, business hours, retry rules, escalation phone. Role: `admin`. |
| **Merchant Operator** | Reviews conversations, retries, marks outcomes manually, handles escalations. Role: `operator`. |
| **Merchant Viewer** | Read-only access to analytics, conversations, transcripts. Role: `viewer`. |
| **Customer** | Pakistani COD buyer who placed an order. Receives WA message; may reply with text, voice note, sticker, image, etc. |

---

## 2. Channels

### 2.1 WhatsApp (primary)

- **Provider abstraction:** `WAChannelProvider` Protocol → `meta_cloud`,
  `dialog360`, `twilio_wa` implementations.
- **Outbound:** approved utility template (`order_confirmation_v1`) opens the
  24-hour customer service window. Free-form replies allowed within window;
  outside window requires another approved template.
- **Inbound:** customer reply (text / voice note / image / location) →
  webhook → FSM resumes the conversation.
- **Voice notes:** transcribed via Deepgram Nova-3 (`ur` cloud) or
  faster-whisper (local) **before** the LLM sees them.
- **Outbound media:** text by default. Per-store flag enables TTS-to-
  voice-note via Uplift Orator (`MP3_22050_32`).
- **Compliance:** WA Business Policy — opt-in required, approved templates for
  first message, 24-hour service window, marketing templates separately gated.

### 2.2 Voice (secondary, off by default)

- **Provider abstraction:** `STTProvider` / `LLMProvider` / `TTSProvider`
  Protocols (see `apps/agent/awaaz_agent/providers/`).
- **Cloud stack:** Deepgram Nova-3 + Claude Haiku 4.5 + Uplift Orator + Silero
  VAD + LiveKit `MultilingualModel`.
- **Local stack:** faster-whisper + vLLM (Qwen3 / Qalb) + Indic-Parler /
  Piper.
- **Telephony:** Twilio Programmable Voice MVP, PTCL/Nayatel SIP trunk
  production.
- **Compliance:** PTA Spam Regulations 2009 (DNCR scrub), 10:00–20:00 PKT,
  3-attempt cap, recording disclosure as first audio frame, only PTCL/Nayatel-
  allocated CLI.

### 2.3 SMS (fallback only)

- After 3 unsuccessful WA + voice attempts, send SMS via SendPK / Twilio /
  Jazz A2P with a short reschedule link.

---

## 3. Conversation State Machine

States (single FSM shared by both channels):

```
greeting → disclosure → identity_verify → order_recap → confirm_intent
   ├─→ confirmed → closing
   ├─→ objection_cancel → closing
   ├─→ objection_reschedule → closing
   ├─→ objection_change_qty
   │       └─→ flag_change_request → closing
   ├─→ objection_change_address
   │       └─→ flag_change_request → closing
   ├─→ objection_change_item
   │       └─→ flag_change_request → closing
   ├─→ out_of_scope_escalation → closing
   ├─→ wrong_number → closing
   ├─→ proxy_answerer → closing (status=callback)
   └─→ language_fallback ↩ (re-enters greeting in target language)

terminal: closing | voicemail_fallback | retry_pending | failed
```

### 3.1 Tools (LLM may call these; FSM validates)

| Tool | Effect |
|---|---|
| `confirm_order(idempotency_key)` | Set conversation outcome=`confirmed`; tag source order. |
| `cancel_order(idempotency_key, reason)` | Outcome=`cancelled`; persist reason. |
| `reschedule_delivery(idempotency_key, requested_iso, requested_label)` | Outcome=`rescheduled`. |
| `flag_change_request(idempotency_key, field, requested_value)` | Outcome=`change_request`; never modify the order itself. |
| `flag_wrong_number(idempotency_key)` | Outcome=`wrong_number`; increment fake-order counter on phone hash. |
| `flag_proxy_answerer(idempotency_key, callback_label)` | Outcome=`callback`. |
| `escalate_to_human(idempotency_key, reason, urgency)` | Outcome=`escalated`; write to `escalation_queue`. |
| `switch_language(target_language)` | Slot only — FSM transitions to `language_fallback`. |
| `end_conversation(reason)` | Slot only — FSM transitions to `closing`. |

Every tool returns a structured response that the LLM uses for its next
message. Idempotency keys are stored in `conversation_states.tool_idempotency`
JSONB.

### 3.2 State invariants

- A tool call is rejected by the FSM if the current state's allowed tool set
  does not include it.
- Slot fills (`order_id_acknowledged`, `customer_name_match`, etc.) gate
  transitions. The LLM cannot transition with empty required slots.
- Every state has a max-turn budget (default 6). Exceeding it auto-transitions
  to `out_of_scope_escalation`.

---

## 4. Scenarios (each has at least one golden conversation in
`apps/api/awaaz_api/tests/fixtures/golden/`)

| # | Scenario | Final state |
|---|---|---|
| 4.1 | Cooperative customer confirms | `confirmed` |
| 4.2 | Customer cancels (real reason) | `cancelled` |
| 4.3 | Customer cancels (denies placing) | `cancelled` (+ fake-order counter) |
| 4.4 | Reschedule with specific time ("کل شام پانچ بجے") | `rescheduled` |
| 4.5 | Reschedule vague ("بعد میں") | `rescheduled` (label-only) |
| 4.6 | Customer wants quantity change | `change_request` |
| 4.7 | Customer wants address change | `change_request` |
| 4.8 | Customer wants item swap | `change_request` |
| 4.9 | No reply within 24h (WA window) | `failed` (→ retry/SMS) |
| 4.10 | Wrong number (denies any order) | `wrong_number` |
| 4.11 | Relative answers ("وہ گھر پہ نہیں ہے") | `callback` |
| 4.12 | Out-of-scope (returns/refunds) | `escalated` |
| 4.13 | Customer abusive | `escalated` |
| 4.14 | Punjabi/Pashto/Sindhi/English fallback | re-enters greeting in EN |
| 4.15 | Roman Urdu reply | continues in Roman Urdu |
| 4.16 | Sends voice note | transcribed → continues normally |
| 4.17 | Asks payment options (RAAST/JazzCash/EasyPaisa) | answered per store config |

---

## 5. Urdu prompt templates

Full files live in `apps/api/awaaz_api/fsm/prompts/` (and mirrored for the
voice agent in `apps/agent/awaaz_agent/prompts/`).

### `system_ur.md` (excerpt)

```
آپ "{{agent_name}}"، {{brand_name}} کی شائستہ اردو بولنے والی کسٹمر سروس ایجنٹ ہیں۔

LANGUAGE RULES (strict):
- ڈیفالٹ: قدرتی محاوراتی اردو، نستعلیق رسم الخط۔
- صارف کے انداز سے میل کھائیں: رومن اردو ان → رومن اردو آؤٹ۔
- عام انگریزی الفاظ (order, delivery, password) انگریزی میں رہنے دیں۔
- اعداد: <100 الفاظ میں؛ ≥100 ہندسوں میں۔ تاریخیں الفاظ میں ("بیس اپریل")۔

RESPONSE LENGTH (critical — read aloud or shown on phone screens):
- ہر ٹرن میں زیادہ سے زیادہ 20 الفاظ، جب تک وضاحت نہ مانگی جائے۔
- ایک ٹرن، ایک سوال۔ صارف کے جواب کا انتظار کریں۔
- مارک ڈاؤن، ستارے، ایموجی استعمال نہ کریں۔

STYLE:
- "آپ" استعمال کریں، "تم" نہیں۔
- پہلے تسلیم، پھر سوال: "جی، میں سمجھ گئی۔ کیا آپ آرڈر کنفرم کرنا چاہتے ہیں؟"
- نمبرز اور پتے ٹول کال سے پہلے دہرائیں۔

TOOL USAGE:
- confirm_order/cancel_order/reschedule_delivery — تمام فیلڈز ضروری۔
- escalate_to_human — جب: 2 ٹرن کے بعد غصہ، انسان کی درخواست، یا
  out-of-scope (returns >Rs.10,000, complaints, legal)۔
```

### `greeting.md`

```
السلام علیکم، میں {{brand_name}} کی جانب سے {{agent_name}} بات کر رہی ہوں۔
کیا میں {{customer_name}} صاحب/صاحبہ سے بات کر رہی ہوں؟
```

### `disclosure.md`

```
آپ کا یہ پیغام آرڈر کی تصدیق کے لیے ہے۔ یہ گفتگو کوالٹی کے لیے محفوظ کی جا
رہی ہے۔
```

### `confirm.md`

```
آپ کا آرڈر نمبر {{order_number}} ہے۔ {{item_count}} اشیاء، کل رقم
{{total_in_words}} روپے۔ پتہ: {{address}}۔ کیا یہ کنفرم کر دوں؟
```

### `cancel.md`

```
ٹھیک ہے، میں سمجھ گئی۔ کیا آپ بتا سکتے ہیں کہ کیوں کینسل کرنا چاہتے ہیں؟
```

### `reschedule.md`

```
کوئی بات نہیں۔ کس وقت دوبارہ رابطہ کروں؟ آج شام، کل صبح، یا کوئی اور وقت؟
```

### `change_request.md`

```
معذرت، میں ابھی آرڈر تبدیل نہیں کر سکتی، لیکن میں نوٹ کر دیتی ہوں۔ ٹیم آپ
کو ایک گھنٹے میں رابطہ کرے گی۔
```

### `escalate.md`

```
اس کے لیے میں آپ کو ہماری سپورٹ ٹیم سے ملواؤں گی۔ مہربانی کر کے ایک لمحے
کے لیے رکیں۔
```

### `language_fallback.md`

```
اگر آپ کو اردو میں آسانی نہیں تو میں انگلش میں بات کر سکتی ہوں۔ آپ کیا
پسند کریں گے؟
```

### `wrong_number.md`

```
معذرت، شاید نمبر غلط لگ گیا۔ آپ کا وقت لینے کے لیے معاف کیجیے گا۔
```

### `voicemail.md` (≤5 sec for voice channel)

```
السلام علیکم، {{brand_name}} کی طرف سے۔ آپ کے آرڈر کی تصدیق کے لیے براہ کرم
ہمیں واٹس ایپ کریں {{whatsapp_number}}۔
```

---

## 6. Generic webhook order intake schema

```json
{
  "merchant_id": "shop_abc",
  "platform": "shopify | woocommerce | custom",
  "order_id": "1001",
  "external_order_id": "gid://shopify/Order/4567890",
  "customer": {
    "name": "Ali Raza",
    "phone": "+923331234567",
    "language": "ur"
  },
  "address": {
    "line1": "...",
    "city": "Karachi",
    "province": "Sindh",
    "postal_code": "75300"
  },
  "items": [{ "name": "Lawn Suit", "qty": 2, "unit_price": 2500 }],
  "subtotal": 5000,
  "shipping": 250,
  "total": 5250,
  "cod_amount": 5250,
  "currency": "PKR",
  "created_at": "2026-04-26T13:14:00+05:00",
  "idempotency_key": "uuid"
}
```

Required header: `X-Awaaz-Signature: sha256=<hex>` over the raw request body
using the per-store HMAC secret. Reject if missing or `compare_digest` fails.

---

## 7. Database schema (DDL in `apps/api/awaaz_api/migrations/versions/`)

Top-level tables:

- `organizations`, `users`, `memberships`, `api_keys`, `audit_logs`
- `stores`, `agents`, `agent_versions`
- `orders`, `customers` (encrypted PII + `phone_hash` HMAC)
- `conversations` (channel = wa | voice | sms), `messages`,
  `conversation_states`, `transcripts` (with `pgvector`)
- `wa_templates`, `wa_opt_ins`
- `calls` (partitioned by month), `recordings`, `call_outcomes`
- `retry_queues`, `escalation_queue`
- `webhook_events` (inbound + outbound idempotency)
- `billing_events`, `cost_breakdowns`
- `dncr_list` (PTA-distributed list, refreshed weekly)
- `feature_flags`

Every tenant-scoped table has:
- `org_id uuid not null` and `store_id uuid not null` (or one of them).
- `RLS POLICY ... FOR ALL TO awaaz_app USING (store_id = current_setting('app.current_store')::uuid)`.
- `FORCE ROW LEVEL SECURITY` so even the table owner cannot bypass.
- Composite index `(store_id, created_at DESC)`.

---

## 8. Onboarding flow

1. Owner signs up (email + password or Google OAuth).
2. Creates organization (slug auto-generated).
3. Creates first store.
4. Connects integration:
   - **Shopify:** OAuth install → app installed → webhooks subscribed → orders sync.
   - **WooCommerce:** install plugin → paste API key → orders sync.
   - **Generic:** copy webhook URL + signing secret → POST orders.
   - **CSV:** upload file → preview → confirm.
5. Imports last 50 orders for review (Shopify/Woo only).
6. Configures agent: brand name, agent name (default "Sahar"), voice (if voice
   channel enabled), business hours per weekday, retry rules, escalation phone
   numbers, payment options accepted (COD / RAAST / JazzCash / EasyPaisa),
   language preference, max-conversation-cost cap.
7. Live preview: types prompt variables, hears Uplift TTS sample (if voice).
8. Test conversation: enters own phone, agent sends WA template, plays full
   FSM end-to-end.
9. Approves recording-consent / opt-in disclosure language (legal gate).
10. Goes live: rate-limited ramp 10 → 100 → 1000 conversations/day over 3
    days.

---

## 9. Latency budget (WhatsApp primary)

User-perceived budget for the round-trip "customer sends → agent replies":

| Component | Budget | Notes |
|---|---|---|
| Webhook ingest + signature verify | 30 ms | FastAPI + `hmac.compare_digest` |
| FSM tick + slot validation | 10 ms | Pure Python, in-process |
| LLM TTFT (cached prefix, ~1.5K input) | 400 ms | Claude Haiku 4.5 with `cache_control` |
| LLM stream completion (~80 output tokens) | 800 ms | 90+ tok/s |
| Outbound WA Cloud API call | 250 ms | Mumbai → Meta edge |
| **Total (typical)** | **~1,490 ms** | well within human-perceived "instant reply" on chat |

Voice channel budgets are tighter (≤1.4s for sub-second perception); see
`docs/ARCHITECTURE.md` §2.

---

## 10. Cost guardrails

- `per_conversation_cost_cap_usd` (default $0.05) — kill the conversation and
  flag for review if cumulative cost exceeds the cap.
- `monthly_budget_usd` per store — alerts at 50/80/100 %.
- Cost breakdown JSONB on `cost_breakdowns` row keyed by `conversation_id`,
  summed nightly into `billing_events`.
