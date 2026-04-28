"""initial schema — all tables, RLS, encryption helpers

Revision ID: 0001
Revises:
Create Date: 2026-04-28
"""

from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ---------------------------------------------------------------------------
# Helper SQL fragments
# ---------------------------------------------------------------------------
TIMESTAMPS = """
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
"""

# RLS predicate macros — keep in one place so policies are uniform.
RLS_STORE_PREDICATE = (
    "store_id = nullif(current_setting('app.current_store', true), '')::uuid "
    "OR current_setting('app.bypass_rls', true) = 'on'"
)
RLS_ORG_PREDICATE = (
    "org_id = nullif(current_setting('app.current_org', true), '')::uuid "
    "OR current_setting('app.bypass_rls', true) = 'on'"
)


def _enable_rls(table: str, predicate: str, *, name: str | None = None) -> None:
    """Apply the standard RLS pattern: enable, FORCE, single ALL policy."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    pol = name or f"{table}_tenant_isolation"
    op.execute(
        f"CREATE POLICY {pol} ON {table} FOR ALL "
        f"USING ({predicate}) "
        f"WITH CHECK ({predicate});"
    )


def _updated_at_trigger(table: str) -> None:
    op.execute(
        f"""
        CREATE TRIGGER {table}_set_updated_at
        BEFORE UPDATE ON {table}
        FOR EACH ROW EXECUTE FUNCTION app_set_updated_at();
        """
    )


# ---------------------------------------------------------------------------
def upgrade() -> None:
    # ------------------------------------------------------------------ utility
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_set_updated_at()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$;
        """
    )

    # PII helpers — symmetric encryption with pgcrypto.  Keys live as session
    # GUCs (set by app middleware), never in the DB.  The HMAC helper produces
    # a deterministic 32-byte hex digest that we use for equality lookups.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_encrypt_pii(p_plain text)
        RETURNS bytea LANGUAGE plpgsql AS $$
        DECLARE
            k text := current_setting('app.pii_key', true);
        BEGIN
            IF p_plain IS NULL THEN
                RETURN NULL;
            END IF;
            IF k IS NULL OR k = '' THEN
                RAISE EXCEPTION 'app.pii_key not set';
            END IF;
            RETURN pgp_sym_encrypt(p_plain, k);
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_decrypt_pii(p_cipher bytea)
        RETURNS text LANGUAGE plpgsql AS $$
        DECLARE
            k text := current_setting('app.pii_key', true);
        BEGIN
            IF p_cipher IS NULL THEN
                RETURN NULL;
            END IF;
            IF k IS NULL OR k = '' THEN
                RAISE EXCEPTION 'app.pii_key not set';
            END IF;
            RETURN pgp_sym_decrypt(p_cipher, k);
        END;
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_phone_hash(p_phone text)
        RETURNS text LANGUAGE plpgsql IMMUTABLE AS $$
        DECLARE
            k text := current_setting('app.phone_hash_key', true);
        BEGIN
            IF p_phone IS NULL THEN
                RETURN NULL;
            END IF;
            IF k IS NULL OR k = '' THEN
                RAISE EXCEPTION 'app.phone_hash_key not set';
            END IF;
            RETURN encode(hmac(p_phone, k, 'sha256'), 'hex');
        END;
        $$;
        """
    )

    # ---------------------------------------------------------------- tenancy
    op.execute(
        """
        CREATE TABLE organizations (
            id           uuid primary key default gen_random_uuid(),
            slug         text not null unique,
            name         text not null,
            country_code text not null default 'PK',
            timezone     text not null default 'Asia/Karachi',
            stripe_customer_id text,
            settings     jsonb not null default '{}'::jsonb,
            status       text not null default 'active'
                check (status in ('active','suspended','deleted')),
            """
        + TIMESTAMPS
        + """
        );

        CREATE INDEX idx_orgs_status ON organizations (status);
        """
    )
    _updated_at_trigger("organizations")

    op.execute(
        """
        CREATE TABLE users (
            id            uuid primary key default gen_random_uuid(),
            email         citext,
            email_lower   text generated always as (lower(email::text)) stored,
            email_verified_at timestamptz,
            name          text,
            avatar_url    text,
            password_hash text,
            mfa_enabled   boolean not null default false,
            mfa_secret_enc bytea,
            last_login_at timestamptz,
            """
        + TIMESTAMPS
        + """
        );
        """
    )
    op.execute("CREATE EXTENSION IF NOT EXISTS citext;")
    op.execute("CREATE UNIQUE INDEX users_email_lower_uq ON users(email_lower);")
    _updated_at_trigger("users")

    op.execute(
        """
        CREATE TABLE memberships (
            id        uuid primary key default gen_random_uuid(),
            org_id    uuid not null references organizations(id) on delete cascade,
            user_id   uuid not null references users(id) on delete cascade,
            role      text not null check (role in ('owner','admin','operator','viewer')),
            invited_by uuid references users(id),
            invited_at timestamptz,
            accepted_at timestamptz,
            """
        + TIMESTAMPS
        + """,
            unique (org_id, user_id)
        );
        CREATE INDEX idx_memberships_user ON memberships (user_id);
        """
    )
    _updated_at_trigger("memberships")
    _enable_rls("memberships", RLS_ORG_PREDICATE)

    op.execute(
        """
        CREATE TABLE api_keys (
            id         uuid primary key default gen_random_uuid(),
            org_id     uuid not null references organizations(id) on delete cascade,
            store_id   uuid,
            name       text not null,
            key_prefix text not null,
            key_hash   bytea not null,
            scopes     text[] not null default '{}',
            last_used_at timestamptz,
            expires_at  timestamptz,
            revoked_at  timestamptz,
            created_by uuid references users(id),
            """
        + TIMESTAMPS
        + """
        );
        CREATE UNIQUE INDEX api_keys_prefix_uq ON api_keys (key_prefix);
        CREATE INDEX idx_api_keys_org ON api_keys (org_id);
        """
    )
    _updated_at_trigger("api_keys")
    _enable_rls("api_keys", RLS_ORG_PREDICATE)

    # ---------------------------------------------------------------- stores
    op.execute(
        """
        CREATE TABLE stores (
            id              uuid primary key default gen_random_uuid(),
            org_id          uuid not null references organizations(id) on delete cascade,
            slug            text not null,
            name            text not null,
            brand_name      text not null,
            platform        text not null
                check (platform in ('shopify','woocommerce','custom','manual')),
            platform_shop_domain text,
            platform_access_token_enc bytea,
            timezone        text not null default 'Asia/Karachi',
            currency        text not null default 'PKR',
            -- WhatsApp config
            wa_provider     text not null default 'meta_cloud'
                check (wa_provider in ('meta_cloud','dialog360','twilio_wa')),
            wa_phone_number_id     text,
            wa_business_account_id text,
            wa_access_token_enc    bytea,
            wa_app_secret_enc      bytea,
            wa_verify_token_enc    bytea,
            -- Voice channel (off by default)
            voice_enabled    boolean not null default false,
            voice_caller_id  text,
            -- Agent default config (per-agent_versions overrides this)
            agent_config     jsonb not null default '{}'::jsonb,
            -- Cost guardrails
            per_conversation_cost_cap_usd numeric(8,4) not null default 0.05,
            per_call_cost_cap_usd         numeric(8,4) not null default 0.50,
            monthly_budget_usd            numeric(10,2),
            -- Webhook signing
            webhook_secret_enc bytea,
            status text not null default 'active'
                check (status in ('active','paused','suspended','deleted')),
            """
        + TIMESTAMPS
        + """,
            unique (org_id, slug)
        );
        CREATE INDEX idx_stores_org ON stores (org_id);
        CREATE INDEX idx_stores_wa_phone ON stores (wa_phone_number_id);
        CREATE INDEX idx_stores_platform ON stores (platform, platform_shop_domain);
        """
    )
    _updated_at_trigger("stores")
    op.execute("ALTER TABLE stores ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE stores FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"CREATE POLICY stores_tenant_isolation ON stores FOR ALL "
        f"USING ({RLS_ORG_PREDICATE}) WITH CHECK ({RLS_ORG_PREDICATE});"
    )

    # ---------------------------------------------------------------- agents
    op.execute(
        """
        CREATE TABLE agents (
            id        uuid primary key default gen_random_uuid(),
            org_id    uuid not null references organizations(id) on delete cascade,
            store_id  uuid not null references stores(id) on delete cascade,
            name      text not null,
            description text,
            status    text not null default 'draft'
                check (status in ('draft','active','archived')),
            current_version_id uuid,
            """
        + TIMESTAMPS
        + """
        );
        CREATE INDEX idx_agents_store ON agents (store_id);
        """
    )
    _updated_at_trigger("agents")
    _enable_rls("agents", RLS_STORE_PREDICATE)

    op.execute(
        """
        CREATE TABLE agent_versions (
            id        uuid primary key default gen_random_uuid(),
            org_id    uuid not null references organizations(id) on delete cascade,
            store_id  uuid not null references stores(id) on delete cascade,
            agent_id  uuid not null references agents(id) on delete cascade,
            version   integer not null,
            -- Agent runtime config (provider matrix, prompt vars, FSM tweaks)
            config    jsonb not null,
            prompt_overrides jsonb not null default '{}'::jsonb,
            published_at timestamptz,
            published_by uuid references users(id),
            """
        + TIMESTAMPS
        + """,
            unique (agent_id, version)
        );
        CREATE INDEX idx_agent_versions_agent ON agent_versions (agent_id, version DESC);
        """
    )
    _updated_at_trigger("agent_versions")
    _enable_rls("agent_versions", RLS_STORE_PREDICATE)

    op.execute(
        "ALTER TABLE agents ADD CONSTRAINT agents_current_version_fk "
        "FOREIGN KEY (current_version_id) REFERENCES agent_versions(id) ON DELETE SET NULL "
        "DEFERRABLE INITIALLY DEFERRED;"
    )

    # ---------------------------------------------------------------- customers (encrypted PII)
    op.execute(
        """
        CREATE TABLE customers (
            id           uuid primary key default gen_random_uuid(),
            org_id       uuid not null references organizations(id) on delete cascade,
            store_id     uuid not null references stores(id) on delete cascade,
            phone_hash   text not null,
            phone_enc    bytea not null,
            name_enc     bytea,
            email_enc    bytea,
            language     text not null default 'ur',
            -- behaviour
            fake_order_count    integer not null default 0,
            blocked_at          timestamptz,
            opted_out_at        timestamptz,
            last_seen_at        timestamptz,
            """
        + TIMESTAMPS
        + """,
            unique (store_id, phone_hash)
        );
        CREATE INDEX idx_customers_store_hash ON customers (store_id, phone_hash);
        CREATE INDEX idx_customers_blocked ON customers (store_id) WHERE blocked_at IS NOT NULL;
        """
    )
    _updated_at_trigger("customers")
    _enable_rls("customers", RLS_STORE_PREDICATE)

    # ---------------------------------------------------------------- orders
    op.execute(
        """
        CREATE TABLE orders (
            id                   uuid primary key default gen_random_uuid(),
            org_id               uuid not null references organizations(id) on delete cascade,
            store_id             uuid not null references stores(id) on delete cascade,
            customer_id          uuid not null references customers(id) on delete cascade,
            external_order_id    text not null,
            external_order_number text,
            address_line1_enc    bytea,
            address_line2_enc    bytea,
            city                 text,
            province             text,
            postal_code          text,
            subtotal             numeric(12,2),
            shipping             numeric(12,2),
            total                numeric(12,2) not null,
            currency             text not null default 'PKR',
            cod_amount           numeric(12,2),
            payment_method       text not null default 'cod',
            line_items           jsonb not null default '[]'::jsonb,
            placed_at            timestamptz not null,
            -- conversation state
            confirmation_status text not null default 'pending'
                check (confirmation_status in (
                    'pending','dispatched','confirmed','cancelled','rescheduled',
                    'change_request','wrong_number','escalated','failed','blocked'
                )),
            attempt_count        integer not null default 0,
            next_attempt_at      timestamptz,
            tags                 text[] not null default '{}',
            metadata             jsonb not null default '{}'::jsonb,
            idempotency_key      text not null,
            """
        + TIMESTAMPS
        + """,
            unique (store_id, idempotency_key),
            unique (store_id, external_order_id)
        );
        CREATE INDEX idx_orders_store_status ON orders (store_id, confirmation_status, next_attempt_at);
        CREATE INDEX idx_orders_store_created ON orders (store_id, created_at DESC);
        CREATE INDEX idx_orders_customer ON orders (customer_id);
        CREATE INDEX idx_orders_tags ON orders USING gin (tags);
        """
    )
    _updated_at_trigger("orders")
    _enable_rls("orders", RLS_STORE_PREDICATE)

    # ---------------------------------------------------------------- conversations
    op.execute(
        """
        CREATE TABLE conversations (
            id                uuid primary key default gen_random_uuid(),
            org_id            uuid not null references organizations(id) on delete cascade,
            store_id          uuid not null references stores(id) on delete cascade,
            customer_id       uuid not null references customers(id) on delete cascade,
            order_id          uuid references orders(id) on delete set null,
            agent_version_id  uuid references agent_versions(id),
            channel           text not null
                check (channel in ('whatsapp','voice','sms')),
            channel_provider  text not null,
            channel_thread_id text,
            state             text not null default 'greeting',
            slots             jsonb not null default '{}'::jsonb,
            history           jsonb not null default '[]'::jsonb,
            outcome           text
                check (outcome in (
                    'confirmed','cancelled','rescheduled','change_request',
                    'wrong_number','callback','escalated','no_response','failed'
                )),
            outcome_reason    text,
            opened_at         timestamptz not null default now(),
            last_inbound_at   timestamptz,
            last_outbound_at  timestamptz,
            closed_at         timestamptz,
            cost_usd          numeric(10,5) not null default 0,
            tokens_input      integer not null default 0,
            tokens_output     integer not null default 0,
            tokens_cache_read integer not null default 0,
            attempt_index     integer not null default 0,
            """
        + TIMESTAMPS
        + """
        );
        CREATE INDEX idx_conversations_store_created
            ON conversations (store_id, created_at DESC);
        CREATE INDEX idx_conversations_order
            ON conversations (order_id);
        CREATE INDEX idx_conversations_thread
            ON conversations (channel, channel_thread_id);
        CREATE INDEX idx_conversations_open
            ON conversations (store_id, last_inbound_at)
            WHERE closed_at IS NULL;
        """
    )
    _updated_at_trigger("conversations")
    _enable_rls("conversations", RLS_STORE_PREDICATE)

    op.execute(
        """
        CREATE TABLE messages (
            id              uuid primary key default gen_random_uuid(),
            org_id          uuid not null references organizations(id) on delete cascade,
            store_id        uuid not null references stores(id) on delete cascade,
            conversation_id uuid not null references conversations(id) on delete cascade,
            direction       text not null check (direction in ('inbound','outbound')),
            role            text not null check (role in ('user','assistant','system','tool')),
            content_type    text not null default 'text'
                check (content_type in ('text','voice','image','sticker','document','location','template','interactive','tool_call','tool_result')),
            body            text,
            body_redacted   text,
            media_s3_key    text,
            media_mime      text,
            media_duration_ms integer,
            template_name   text,
            template_params jsonb,
            tool_name       text,
            tool_arguments  jsonb,
            tool_result     jsonb,
            channel_message_id text,
            channel_status     text,
            tokens_input    integer,
            tokens_output   integer,
            cost_usd        numeric(10,6),
            sent_at         timestamptz,
            delivered_at    timestamptz,
            read_at         timestamptz,
            """
        + TIMESTAMPS
        + """
        );
        CREATE INDEX idx_messages_conv_created
            ON messages (conversation_id, created_at);
        CREATE INDEX idx_messages_channel_id
            ON messages (channel_message_id) WHERE channel_message_id IS NOT NULL;
        CREATE INDEX idx_messages_store_created
            ON messages (store_id, created_at DESC);
        """
    )
    _enable_rls("messages", RLS_STORE_PREDICATE)

    op.execute(
        """
        CREATE TABLE conversation_states (
            conversation_id uuid primary key references conversations(id) on delete cascade,
            org_id          uuid not null references organizations(id) on delete cascade,
            store_id        uuid not null references stores(id) on delete cascade,
            current_state   text not null,
            previous_state  text,
            slots           jsonb not null default '{}'::jsonb,
            tool_idempotency jsonb not null default '{}'::jsonb,
            turn_count      integer not null default 0,
            """
        + TIMESTAMPS
        + """
        );
        """
    )
    _updated_at_trigger("conversation_states")
    _enable_rls("conversation_states", RLS_STORE_PREDICATE)

    op.execute(
        """
        CREATE TABLE transcripts (
            id              uuid primary key default gen_random_uuid(),
            org_id          uuid not null references organizations(id) on delete cascade,
            store_id        uuid not null references stores(id) on delete cascade,
            conversation_id uuid not null references conversations(id) on delete cascade,
            full_text       text not null,
            summary         text,
            language        text not null default 'ur',
            embedding       vector(1024),
            """
        + TIMESTAMPS
        + """
        );
        CREATE INDEX idx_transcripts_conv ON transcripts (conversation_id);
        CREATE INDEX idx_transcripts_emb ON transcripts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
        """
    )
    _enable_rls("transcripts", RLS_STORE_PREDICATE)

    # ---------------------------------------------------------------- WA templates + opt-ins
    op.execute(
        """
        CREATE TABLE wa_templates (
            id                uuid primary key default gen_random_uuid(),
            org_id            uuid not null references organizations(id) on delete cascade,
            store_id          uuid not null references stores(id) on delete cascade,
            provider          text not null,
            template_name     text not null,
            language          text not null default 'ur',
            category          text not null check (category in ('UTILITY','MARKETING','AUTHENTICATION')),
            status            text not null default 'PENDING'
                check (status in ('PENDING','APPROVED','REJECTED','PAUSED','DISABLED')),
            body              text not null,
            example_params    jsonb,
            external_template_id text,
            quality_rating    text,
            last_synced_at    timestamptz,
            """
        + TIMESTAMPS
        + """,
            unique (store_id, template_name, language)
        );
        CREATE INDEX idx_wa_templates_store ON wa_templates (store_id);
        """
    )
    _updated_at_trigger("wa_templates")
    _enable_rls("wa_templates", RLS_STORE_PREDICATE)

    op.execute(
        """
        CREATE TABLE wa_opt_ins (
            id            uuid primary key default gen_random_uuid(),
            org_id        uuid not null references organizations(id) on delete cascade,
            store_id      uuid not null references stores(id) on delete cascade,
            customer_id   uuid not null references customers(id) on delete cascade,
            phone_hash    text not null,
            source        text not null
                check (source in ('checkout','plugin_form','csv_attestation','wa_button','operator_manual')),
            evidence_url  text,
            opted_in_at   timestamptz not null default now(),
            opted_out_at  timestamptz,
            marketing_opted_in_at timestamptz,
            marketing_opted_out_at timestamptz,
            """
        + TIMESTAMPS
        + """,
            unique (store_id, phone_hash)
        );
        CREATE INDEX idx_wa_opt_ins_store ON wa_opt_ins (store_id);
        """
    )
    _enable_rls("wa_opt_ins", RLS_STORE_PREDICATE)

    # ---------------------------------------------------------------- voice (calls partitioned)
    op.execute(
        """
        CREATE TABLE calls (
            id              uuid not null default gen_random_uuid(),
            org_id          uuid not null references organizations(id) on delete cascade,
            store_id        uuid not null references stores(id) on delete cascade,
            conversation_id uuid not null references conversations(id) on delete cascade,
            customer_id     uuid not null references customers(id) on delete cascade,
            order_id        uuid references orders(id) on delete set null,
            sip_provider    text not null,
            from_number     text not null,
            to_number_hash  text not null,
            direction       text not null check (direction in ('outbound','inbound')),
            status          text not null default 'queued'
                check (status in ('queued','dialing','ringing','in_progress','completed','failed','voicemail','no_answer','busy','cancelled')),
            amd_result      text,
            recording_s3_key text,
            disclosure_played_at timestamptz,
            duration_ms     integer,
            cost_usd        numeric(10,5) not null default 0,
            attempt_index   integer not null default 1,
            started_at      timestamptz,
            answered_at     timestamptz,
            ended_at        timestamptz,
            end_reason      text,
            metadata        jsonb not null default '{}'::jsonb,
            """
        + TIMESTAMPS
        + """,
            primary key (id, created_at)
        ) PARTITION BY RANGE (created_at);
        """
    )
    op.execute(
        """
        -- Three months of partitions; pg_partman or app code rolls them.
        CREATE TABLE calls_2026_04 PARTITION OF calls FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
        CREATE TABLE calls_2026_05 PARTITION OF calls FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
        CREATE TABLE calls_2026_06 PARTITION OF calls FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
        CREATE TABLE calls_2026_07 PARTITION OF calls FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
        CREATE TABLE calls_default PARTITION OF calls DEFAULT;
        """
    )
    op.execute(
        "CREATE INDEX idx_calls_store_created ON calls (store_id, created_at DESC);"
    )
    op.execute(
        "CREATE INDEX idx_calls_conversation ON calls (conversation_id);"
    )
    op.execute(
        "CREATE INDEX idx_calls_status ON calls (store_id, status, created_at DESC);"
    )
    _enable_rls("calls", RLS_STORE_PREDICATE)

    # ---------------------------------------------------------------- queues
    op.execute(
        """
        CREATE TABLE retry_queues (
            id              uuid primary key default gen_random_uuid(),
            org_id          uuid not null references organizations(id) on delete cascade,
            store_id        uuid not null references stores(id) on delete cascade,
            order_id        uuid not null references orders(id) on delete cascade,
            channel         text not null check (channel in ('whatsapp','voice','sms')),
            attempt         integer not null default 1,
            scheduled_for   timestamptz not null,
            picked_up_at    timestamptz,
            completed_at    timestamptz,
            error           text,
            payload         jsonb not null default '{}'::jsonb,
            """
        + TIMESTAMPS
        + """
        );
        CREATE INDEX idx_retry_pending
            ON retry_queues (scheduled_for)
            WHERE picked_up_at IS NULL AND completed_at IS NULL;
        """
    )
    _enable_rls("retry_queues", RLS_STORE_PREDICATE)

    op.execute(
        """
        CREATE TABLE escalation_queue (
            id              uuid primary key default gen_random_uuid(),
            org_id          uuid not null references organizations(id) on delete cascade,
            store_id        uuid not null references stores(id) on delete cascade,
            conversation_id uuid not null references conversations(id) on delete cascade,
            order_id        uuid references orders(id) on delete set null,
            urgency         text not null default 'normal' check (urgency in ('low','normal','high','critical')),
            reason          text not null,
            transcript_excerpt text,
            assigned_to     uuid references users(id),
            resolved_at     timestamptz,
            resolution_note text,
            """
        + TIMESTAMPS
        + """
        );
        CREATE INDEX idx_escalation_pending
            ON escalation_queue (store_id, created_at DESC)
            WHERE resolved_at IS NULL;
        """
    )
    _enable_rls("escalation_queue", RLS_STORE_PREDICATE)

    op.execute(
        """
        CREATE TABLE webhook_events (
            id            uuid primary key default gen_random_uuid(),
            org_id        uuid,
            store_id      uuid,
            source        text not null,
            event_id      text not null,
            event_type    text,
            received_at   timestamptz not null default now(),
            processed_at  timestamptz,
            error         text,
            payload       jsonb not null,
            response_status integer,
            unique (source, event_id)
        );
        CREATE INDEX idx_webhook_events_received ON webhook_events (received_at DESC);
        """
    )
    op.execute("ALTER TABLE webhook_events ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE webhook_events FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY webhook_events_tenant_isolation ON webhook_events FOR ALL
        USING (
            store_id IS NULL
            OR {RLS_STORE_PREDICATE}
            OR current_setting('app.bypass_rls', true) = 'on'
        )
        WITH CHECK (
            store_id IS NULL
            OR {RLS_STORE_PREDICATE}
            OR current_setting('app.bypass_rls', true) = 'on'
        );
        """
    )

    # ---------------------------------------------------------------- billing
    op.execute(
        """
        CREATE TABLE cost_breakdowns (
            id              uuid primary key default gen_random_uuid(),
            org_id          uuid not null references organizations(id) on delete cascade,
            store_id        uuid not null references stores(id) on delete cascade,
            conversation_id uuid references conversations(id) on delete cascade,
            call_id         uuid,
            component       text not null,
            provider        text not null,
            units           numeric(12,4) not null,
            unit_cost_usd   numeric(12,8) not null,
            total_cost_usd  numeric(12,6) generated always as (units * unit_cost_usd) stored,
            occurred_at     timestamptz not null default now(),
            metadata        jsonb,
            """
        + TIMESTAMPS
        + """
        );
        CREATE INDEX idx_cost_store_date ON cost_breakdowns (store_id, occurred_at DESC);
        CREATE INDEX idx_cost_conv ON cost_breakdowns (conversation_id);
        """
    )
    _enable_rls("cost_breakdowns", RLS_STORE_PREDICATE)

    op.execute(
        """
        CREATE TABLE billing_events (
            id              uuid primary key default gen_random_uuid(),
            org_id          uuid not null references organizations(id) on delete cascade,
            store_id        uuid references stores(id) on delete cascade,
            event_type      text not null,
            stripe_event_id text,
            stripe_usage_record_id text,
            quantity        integer not null,
            unit            text not null,
            period_start    timestamptz not null,
            period_end      timestamptz not null,
            reported_at     timestamptz,
            metadata        jsonb,
            """
        + TIMESTAMPS
        + """,
            unique (org_id, event_type, period_start)
        );
        CREATE INDEX idx_billing_store_period ON billing_events (store_id, period_start DESC);
        """
    )
    op.execute("ALTER TABLE billing_events ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE billing_events FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"CREATE POLICY billing_events_tenant_isolation ON billing_events FOR ALL "
        f"USING ({RLS_ORG_PREDICATE}) WITH CHECK ({RLS_ORG_PREDICATE});"
    )

    # ---------------------------------------------------------------- compliance
    op.execute(
        """
        CREATE TABLE dncr_list (
            phone_hash text primary key,
            source     text not null default 'pta',
            added_at   timestamptz not null default now()
        );
        CREATE INDEX idx_dncr_added ON dncr_list (added_at DESC);
        """
    )
    # No RLS — global compliance list, read-only for app role.

    op.execute(
        """
        CREATE TABLE audit_logs (
            id        uuid primary key default gen_random_uuid(),
            org_id    uuid references organizations(id) on delete cascade,
            store_id  uuid references stores(id) on delete cascade,
            actor_user_id uuid references users(id),
            actor_api_key_id uuid references api_keys(id),
            actor_kind  text not null check (actor_kind in ('user','api_key','system','webhook')),
            action      text not null,
            target_type text,
            target_id   text,
            ip_address  inet,
            user_agent  text,
            metadata    jsonb,
            occurred_at timestamptz not null default now()
        );
        CREATE INDEX idx_audit_org_date ON audit_logs (org_id, occurred_at DESC);
        CREATE INDEX idx_audit_store_date ON audit_logs (store_id, occurred_at DESC);
        """
    )
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY audit_logs_tenant_isolation ON audit_logs FOR ALL
        USING (
            (org_id IS NULL AND current_setting('app.bypass_rls', true) = 'on')
            OR {RLS_ORG_PREDICATE}
        )
        WITH CHECK (
            (org_id IS NULL AND current_setting('app.bypass_rls', true) = 'on')
            OR {RLS_ORG_PREDICATE}
        );
        """
    )

    op.execute(
        """
        CREATE TABLE feature_flags (
            id        uuid primary key default gen_random_uuid(),
            scope     text not null check (scope in ('global','org','store')),
            scope_id  uuid,
            key       text not null,
            value     jsonb not null,
            """
        + TIMESTAMPS
        + """,
            unique (scope, scope_id, key)
        );
        """
    )
    _updated_at_trigger("feature_flags")
    # No RLS — read by app for tenant-resolution; write only via admin role.

    # ---------------------------------------------------------------- recordings & opt-out events
    op.execute(
        """
        CREATE TABLE recordings (
            id              uuid primary key default gen_random_uuid(),
            org_id          uuid not null references organizations(id) on delete cascade,
            store_id        uuid not null references stores(id) on delete cascade,
            call_id         uuid not null,
            s3_key          text not null,
            duration_ms     integer,
            kms_key_id      text,
            sha256          text,
            disclosure_played_at timestamptz,
            retention_until timestamptz,
            """
        + TIMESTAMPS
        + """
        );
        CREATE INDEX idx_recordings_store ON recordings (store_id, created_at DESC);
        CREATE INDEX idx_recordings_retention ON recordings (retention_until) WHERE retention_until IS NOT NULL;
        """
    )
    _enable_rls("recordings", RLS_STORE_PREDICATE)

    # ---------------------------------------------------------------- session table for Better Auth
    op.execute(
        """
        CREATE TABLE auth_sessions (
            id          text primary key,
            user_id     uuid not null references users(id) on delete cascade,
            expires_at  timestamptz not null,
            ip_address  inet,
            user_agent  text,
            """
        + TIMESTAMPS
        + """
        );
        CREATE INDEX idx_sessions_user ON auth_sessions (user_id);
        CREATE INDEX idx_sessions_expires ON auth_sessions (expires_at);
        """
    )

    op.execute(
        """
        CREATE TABLE auth_oauth_accounts (
            id             text primary key,
            user_id        uuid not null references users(id) on delete cascade,
            provider       text not null,
            provider_account_id text not null,
            access_token_enc bytea,
            refresh_token_enc bytea,
            expires_at     timestamptz,
            scope          text,
            id_token_enc   bytea,
            """
        + TIMESTAMPS
        + """,
            unique (provider, provider_account_id)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE auth_verification_tokens (
            id          text primary key,
            identifier  text not null,
            value       text not null,
            expires_at  timestamptz not null,
            created_at  timestamptz not null default now()
        );
        CREATE INDEX idx_verification_identifier ON auth_verification_tokens (identifier);
        """
    )

    # ---------------------------------------------------------------- grant execute on PII helpers
    op.execute("GRANT EXECUTE ON FUNCTION app_encrypt_pii(text) TO awaaz_app;")
    op.execute("GRANT EXECUTE ON FUNCTION app_decrypt_pii(bytea) TO awaaz_app;")
    op.execute("GRANT EXECUTE ON FUNCTION app_phone_hash(text) TO awaaz_app;")


# ---------------------------------------------------------------------------
def downgrade() -> None:
    # Single-shot drop — initial migration owns everything.
    op.execute(
        """
        DROP TABLE IF EXISTS auth_verification_tokens CASCADE;
        DROP TABLE IF EXISTS auth_oauth_accounts CASCADE;
        DROP TABLE IF EXISTS auth_sessions CASCADE;
        DROP TABLE IF EXISTS recordings CASCADE;
        DROP TABLE IF EXISTS feature_flags CASCADE;
        DROP TABLE IF EXISTS audit_logs CASCADE;
        DROP TABLE IF EXISTS dncr_list CASCADE;
        DROP TABLE IF EXISTS billing_events CASCADE;
        DROP TABLE IF EXISTS cost_breakdowns CASCADE;
        DROP TABLE IF EXISTS webhook_events CASCADE;
        DROP TABLE IF EXISTS escalation_queue CASCADE;
        DROP TABLE IF EXISTS retry_queues CASCADE;
        DROP TABLE IF EXISTS calls CASCADE;
        DROP TABLE IF EXISTS wa_opt_ins CASCADE;
        DROP TABLE IF EXISTS wa_templates CASCADE;
        DROP TABLE IF EXISTS transcripts CASCADE;
        DROP TABLE IF EXISTS conversation_states CASCADE;
        DROP TABLE IF EXISTS messages CASCADE;
        DROP TABLE IF EXISTS conversations CASCADE;
        DROP TABLE IF EXISTS orders CASCADE;
        DROP TABLE IF EXISTS customers CASCADE;
        DROP TABLE IF EXISTS agent_versions CASCADE;
        DROP TABLE IF EXISTS agents CASCADE;
        DROP TABLE IF EXISTS stores CASCADE;
        DROP TABLE IF EXISTS api_keys CASCADE;
        DROP TABLE IF EXISTS memberships CASCADE;
        DROP TABLE IF EXISTS users CASCADE;
        DROP TABLE IF EXISTS organizations CASCADE;
        DROP FUNCTION IF EXISTS app_phone_hash(text);
        DROP FUNCTION IF EXISTS app_decrypt_pii(bytea);
        DROP FUNCTION IF EXISTS app_encrypt_pii(text);
        DROP FUNCTION IF EXISTS app_set_updated_at();
        """
    )
