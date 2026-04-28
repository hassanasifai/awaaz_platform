# ROADMAP.md — competitive gaps + post-v0.1 backlog

Synthesised from competitor research (April 2026): Wati, Gupshup, Yellow.ai
(NICE), Haptik (Jio), ManyChat, Tidio (Lyro), Engati, Charles.io, BotPenguin,
Kommunicate, Botsonic, Sendbird, Watermelon, Vapi, Bland.ai, Retell AI,
ElevenLabs Agents, PolyAI, Cognigy, Cresta, Voiceflow, Replicant, Intercom
Fin, Zendesk + Forethought, Ada, Salesforce Agentforce Commerce, Robocall.pk,
bSecure, Saarthi.ai, Vodex.

Awaaz has parity on the core (WA-first, multi-tenant, Urdu LLM, voice channel,
Shopify/Woo, Stripe billing, RLS multi-tenancy, OpenTelemetry/Langfuse). The
gap list below is what separates it from category leaders today.

---

## v0.2 — Speed + customer-service depth (4-6 weeks)

Goal: be measurably faster than Yellow.ai/Wati on Urdu and reduce escalations
by 30% via RAG.

### S0 — Speed engineering for Urdu (strategic moat)
- [ ] **Semantic cache** keyed by paraphrase embedding (cosine ≥ 0.92) →
      serve cached reply, skip LLM. Target: 70% token reduction on top-50
      FAQs. Stack: Redis + pgvector + Claude embeddings.
- [ ] **Tiered prompt-cache prefix**: tier-1 system, tier-2 tenant policy,
      tier-3 KB chunks. Target: cache-hit rate ≥ 85 % per Langfuse.
- [ ] **Speculative classifier path**: distil-Sarvam Urdu intent classifier
      runs in parallel with Haiku call; if confident & low-risk, ship
      classifier reply, cancel LLM. Target: P50 TTFT ≤ 600 ms.
- [ ] **Streaming TTS** with sentence-boundary flush (`۔/.`).
- [ ] **Mid-utterance language switch** (Yellow.ai parity): Deepgram
      `detect_language` per segment + per-segment routing.
- [ ] **Edge inference for STT** in PK: PTCL Smart Cloud Karachi Deepgram
      container (or AWS me-south fallback) for <80 ms RTT.

### S1 — Customer-service depth
- [ ] **Knowledge-base RAG over policies/FAQs**: pgvector on Postgres,
      per-tenant `embeddings` table, cite chunks in cached prefix.
- [ ] **Sentiment + intent classification** surfaced on every message in the
      dashboard. Persist in `messages.metadata`.
- [ ] **Multi-turn long-context summarisation**: Redis store keyed by
      `(store_id, phone_hash)`, summarise after 20 turns, replay prefix as
      cached block.
- [ ] **Order-tracking deep link** integrated with Leopards/TCS/M&P APIs.
- [ ] **Conversation summarisation** at session-end → CRM sync.

### S2 — Operator productivity
- [ ] **Shared inbox UI** with assign / mention / internal notes / SLA timer.
      Extend `escalation_queue` schema; SLA cron writes alerts.
- [ ] **Canned responses + macros + slash-commands**: `snippets` table per
      tenant with `{{customer.name}}`-style substitution.
- [ ] **Mobile operator PWA** with WebPush.

---

## v0.3 — Channel breadth + e-commerce specifics (6-8 weeks)

Goal: parity with ManyChat/Wati on channels, beat Robocall.pk/bSecure on COD
funnel.

### C0 — Channel breadth
- [ ] **Instagram DM**, **Facebook Messenger**, **web chat widget** behind
      the same FSM. Reuse the `Channel` Protocol pattern from
      `channels/base.py`.
- [ ] **TikTok DM** (Sonic-Reasoning style, where allowed).
- [ ] **Voice channel polish**: outbound campaign dialer, CSV upload, IVR
      fallback to human, SIP trunk pool with rate-cap.

### C1 — E-commerce direct-revenue
- [ ] **Cart-abandonment recovery flow**: Shopify `checkouts/create` →
      30/60/120-min WA template chain; Haiku-personalised body. Target:
      30 % recovery (Aurora/Bitespeed benchmark).
- [ ] **Product recommendation / upsell / cross-sell** via Shopify
      `recommendations.json` + WA Catalog carousels.
- [ ] **Post-purchase upsell + review collection + NPS** (Yotpo/Loox).
- [ ] **Address verification**: Google Places + `pk-postal-codes` validator;
      auto-flag mismatched city/postal.
- [ ] **Delivery-time prediction**: LightGBM on TCS/Leopards historicals.
- [ ] **COD-to-prepaid conversion nudge**: WA template offering 5 %
      discount on EasyPaisa prepay.
- [ ] **WhatsApp Catalog "Add-to-Cart"** (Gupshup parity): sync Shopify
      products to WA Cloud `/catalogs`; reply with `interactive product_list`.
- [ ] **Fraud-risk score on COD orders**: gradient-boost on past return
      rate per phone+address+IP; gate auto-confirm.
- [ ] **Lost-package handling state-machine**.

### C2 — South Asian internationalisation (defensible moat)
- [ ] **Code-switching fluency** (Urdu↔English↔Roman-Urdu mid-sentence).
- [ ] **Regional dialects**: Saraiki, Hindko, Balochi voice routing.
- [ ] **PKR formatting**: `Rs / ₨ / PKR` + "lakh/crore" parser.
- [ ] **Hijri / Gregorian dual calendar** in confirmations.
- [ ] **Festival-aware messaging**: suppress non-urgent broadcasts during
      iftar / Friday prayer / Independence Day; auto-greet on Eid.
- [ ] **Pakistan address parser** (mohalla / sector / phase) →
      Plus-Codes.
- [ ] **Voice-note transcription auto-handling** (already built; promote in
      onboarding so merchants enable it from day one).

---

## v0.4 — AI safety + enterprise readiness (8-10 weeks)

Goal: pass first $10k MRR enterprise procurement; avoid PECA / EU-AI-Act
exposure.

### A0 — AI safety & quality
- [ ] **Jailbreak / prompt-injection filter** at input layer. Lightweight
      classifier (Anthropic content filter or Cleanlab TLM) before Haiku
      call; OWASP LLM Top-10 logging.
- [ ] **Hallucination guardrails**: RAG-required mode — refuse + escalate
      below similarity 0.6.
- [ ] **PECA-aware content filter**: deterministic regex + Claude
      classifier for blasphemy / defamation / financial-advice.
- [ ] **Conversation classifier for risk scoring**, surfaced in dashboard.
- [ ] **Adversarial test-suite / red-team CI**: nightly JBFuzz prompts vs
      staging; fail build on >5 % bypass.

### A1 — Enterprise compliance
- [ ] **SOC 2 Type II + ISO 27001** roadmap (Vanta or open-source Comp AI
      wired to GitHub/AWS/Postgres).
- [ ] **GDPR-style DSR endpoints** (export + delete tenant data).
- [ ] **PDPB-PK 2023 readiness** docs + per-tenant data-flow diagrams.
- [ ] **SSO / SAML / SCIM** via WorkOS or Auth0; SCIM provisioning to
      Postgres `users`.
- [ ] **Custom RBAC roles** beyond owner/admin/operator/viewer.
- [ ] **EU AI Act high-risk readiness** (kicks in 2026-08-02): model card +
      risk assessment per deployment.
- [ ] **Audit-trail UX** with operator-readable timeline.

### A2 — Developer ecosystem
- [ ] **Public REST API + OpenAPI spec** for everything operators can do.
- [ ] **Webhooks for every event**: `webhook_subscriptions` table + Celery
      dispatcher with HMAC.
- [ ] **No-code flow builder**: React-Flow front-end persisting to
      `flow_graphs(json)`; runtime evaluator in FastAPI.
- [ ] **Zapier / Make / n8n integrations**.
- [ ] **TS / Python SDK** auto-generated from OpenAPI.
- [ ] **Plugin marketplace**: signed `.awaazpkg` bundles (flow + prompts +
      schema) with revenue share.
- [ ] **`awaaz-cli`** Click app over the REST API.

---

## v0.5 — Personalisation + analytics (4-6 weeks)

- [ ] **Customer-360 panel**: orders, AOV, RFM, last issues. Materialised
      view joining `orders`, `escalation_queue`, `messages`.
- [ ] **A/B testing of prompts and templates**: `prompt_variants` table +
      bucket-by-tenant_user hash; Langfuse experiment tag.
- [ ] **Prompt-versioning UX in dashboard**: Git-backed prompts in S3 +
      Langfuse linkage; diff-view in Next.js.
- [ ] **NPS / CSAT detection from text** with auto-trigger of NPS template.
- [ ] **Bulk reply, filter by SLA-breach, queue view**.

---

## Top-10 do-this-next (impact × effort, copy-paste into a tracker)

1. **Semantic cache + tiered prompt-cache for Urdu FAQ** — biggest latency +
   cost win, days of work.
2. **Cart-abandonment recovery + COD-to-prepaid flow** — direct GMV uplift,
   weeks.
3. **Knowledge-base RAG with pgvector** — unlocks support depth and reduces
   escalations.
4. **Shared inbox UI with assign / SLA / canned replies** — table-stakes vs
   Wati / Haptik.
5. **Voice-note STT auto-handling** — already shipped; surface in onboarding.
6. **Public REST API + webhooks + no-code flow builder** — opens ISV
   ecosystem.
7. **Jailbreak / hallucination guardrail layer** — required for PECA + EU-AI-
   Act readiness.
8. **Instagram DM + web-chat widget** — cheap channel-breadth parity.
9. **SOC 2 Type II + SSO / SAML / SCIM** — gates >$10k MRR enterprise PK
   deals.
10. **Hijri calendar + festival-aware scheduling + Saraiki / Punjabi dialect
    TTS** — defensible local moat no global player will build.

---

## Sources (April 2026)

- Wati pricing: <https://chatarmin.com/en/blog/wati-pricing>,
  <https://www.flowcart.ai/blog/wati-pricing>
- Yellow.ai G2: <https://www.g2.com/products/yellow-ai/reviews>
- Conversational AI India 2026:
  <https://www.caller.digital/blog/conversational-ai-india-2026-enterprise-guide>
- Voice AI 2026 ranking:
  <https://mihup.ai/blog/best-voice-ai-agents-for-enterprise-in-2026-independent-ranking-india-global>
- Yellow.ai alternatives:
  <https://www.robylon.ai/blog/11-yellow-ai-alternatives-2026>
- Gupshup: <https://www.gupshup.ai/en/>
- Haptik / Jio: <https://www.haptik.ai/>
- Vapi 2026: <https://www.cloudtalk.io/blog/vapi-ai-pricing/>,
  <https://www.lindy.ai/blog/vapi-ai>
- Bland.ai vs Retell: <https://www.retellai.com/blog/bland-ai-reviews>,
  <https://www.retellai.com/comparisons/retell-vs-bland>
- AI voice pricing 2026:
  <https://www.retellai.com/blog/ai-voice-agent-pricing-full-cost-breakdown-platform-comparison-roi-analysis>
- ElevenLabs Agents Urdu:
  <https://www.sacesta.com/our-work/blog/elevenlabs-agents-conversational-ai-guide-2026>,
  <https://elevenlabs.io/text-to-speech/urdu>
- Intercom Fin: <https://fin.ai/pricing>,
  <https://myaskai.com/blog/intercom-fin-ai-agent-complete-guide-2026>
- Zendesk + Forethought 2026:
  <https://www.twig.so/blog/zendesk-acquisition-forethought-ai-support-market>,
  <https://chatarmin.com/en/blog/forethought-pricing>
- Ada: <https://myaskai.com/blog/ada-ai-agent-complete-guide-2026>
- Salesforce Agentforce Commerce:
  <https://www.salesforce.com/news/stories/agentforce-commerce-capabilities-announcement/>
- Voiceflow review 2026:
  <https://blog.dograh.com/voiceflow-review-2026-pros-cons-pricing-and-features/>
- ManyChat review 2026: <https://www.tidio.com/blog/manychat-review/>
- Tidio Lyro pricing: <https://www.tidio.com/blog/chatbot-pricing/>
- BotPenguin 2026: <https://botpenguin.com/blogs/whatsapp-ai-agents>
- Engati: <https://www.engati.ai/>
- Sendbird: <https://sendbird.com/products/business-messaging/whatsapp>
- bSecure: <https://www.bsecure.pk/>
- Robocall.pk: <https://robocall.pk/>
- Saarthi.ai: <https://www.saasworthy.com/product/saarthi-ai>
- Vodex: <https://www.vodex.ai/>
- Anthropic prompt caching:
  <https://docs.claude.com/en/docs/build-with-claude/prompt-caching>,
  <https://www.aimagicx.com/blog/prompt-caching-claude-api-cost-optimization-2026>
- Speculative decoding (vLLM):
  <https://developers.redhat.com/articles/2026/04/16/performance-improvements-speculative-decoding-vllm-gpt-oss>
- Sarvam AI Indian languages:
  <https://entrepreneurloop.com/sarvam-ai-llms-voice-optimized-indian-language-models/>
- WA cart recovery 2026:
  <https://m.aisensy.com/blog/recover-abandoned-carts-with-whatsapp/>,
  <https://www.aurorainbox.com/en/2026/02/22/recover-abandoned-carts-whatsapp/>
- Enterprise AI auth:
  <https://customgpt.ai/authentication-methods-enterprise-ai-knowledge-hubs/>
- SOC 2 + AI 2026:
  <https://medium.com/the-ai-clarity-report/soc-2-iso-27001-and-ai-13061024b479>,
  <https://finance.yahoo.com/sectors/technology/articles/boost-ai-achieves-soc-2-120500471.html>
- LLM guardrails 2026:
  <https://appsecsanta.com/nemo-guardrails>,
  <https://developer.nvidia.com/blog/prevent-llm-hallucinations-with-the-cleanlab-trustworthy-language-model-in-nvidia-nemo-guardrails/>,
  <https://www.getmaxim.ai/articles/the-complete-ai-guardrails-implementation-guide-for-2026/>
- LLM jailbreak techniques:
  <https://startup-house.com/blog/llm-jailbreak-techniques>
