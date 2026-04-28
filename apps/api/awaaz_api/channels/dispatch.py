"""Channel-level dispatch — wires FSM + provider + storage."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text

from awaaz_api.fsm import FSMDriver
from awaaz_api.fsm.engine import ToolHandler, ToolOutcome
from awaaz_api.fsm.tools import ToolName
from awaaz_api.language import detect_language, number_to_urdu_words
from awaaz_api.llm import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolCall,
    ToolResultMessage,
    UserMessage,
    build_llm_provider,
)
from awaaz_api.observability import (
    conversation_outcomes_total,
    conversations_started_total,
    cost_usd_total,
    get_logger,
)
from awaaz_api.persistence import AsyncSessionLocal, set_tenant_context
from awaaz_api.settings import get_settings

from .factory import build_wa_provider

_log = get_logger("awaaz.dispatch")
_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "fsm" / "prompts" / "system_ur.md"
)


# ---------------------------------------------------------------------------
async def outbound_first_contact(
    *,
    org_id: UUID,
    store_id: UUID,
    order_id: UUID,
    channel: str,
) -> None:
    """Send the approved utility template that opens the WA service window."""

    if channel != "whatsapp":
        # Voice / SMS go through their own dispatch surface.
        from awaaz_api.observability.logging import get_logger

        get_logger("awaaz.dispatch").info(
            "dispatch.skip_non_wa",
            order_id=str(order_id),
            channel=channel,
        )
        return

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_context(
                session, org_id=org_id, store_id=store_id, bypass=False
            )
            ctx = await _load_order_context(session, order_id=order_id, store_id=store_id)
            if ctx is None:
                _log.warning("dispatch.order_missing", order_id=str(order_id))
                return

            opt_in = (
                await session.execute(
                    text(
                        "SELECT 1 FROM wa_opt_ins "
                        "WHERE store_id = :sid AND phone_hash = :ph "
                        "AND opted_out_at IS NULL"
                    ),
                    {"sid": store_id, "ph": ctx["phone_hash"]},
                )
            ).first()
            if not opt_in:
                _log.warning(
                    "dispatch.no_opt_in",
                    order_id=str(order_id),
                    store_id=str(store_id),
                )
                # Persist for operator review rather than silently dropping.
                await _open_escalation(
                    session,
                    org_id=org_id,
                    store_id=store_id,
                    order_id=order_id,
                    reason="missing_wa_opt_in",
                )
                return

            provider = await _build_provider_for_store(session, store_id=store_id, ctx=ctx)
            template_name = ctx["agent_config"].get(
                "wa_first_contact_template", "order_confirmation_v1"
            )
            language = ctx["customer_language"]

            # Create / reuse a conversation row.
            convo_id = await _ensure_conversation(
                session,
                org_id=org_id,
                store_id=store_id,
                order_id=order_id,
                customer_id=ctx["customer_id"],
                phone_e164=ctx["phone_e164"],
            )

            sent = await provider.send_template(
                to_phone_e164=ctx["phone_e164"],
                template_name=template_name,
                language=language,
                body_params=[
                    ctx["brand_name"],
                    ctx["order_number"],
                    f"{int(ctx['total'])}",
                ],
                idempotency_key=str(order_id),
            )
            await _persist_outbound(
                session,
                org_id=org_id,
                store_id=store_id,
                conversation_id=convo_id,
                template=template_name,
                params=[ctx["brand_name"], ctx["order_number"], str(ctx["total"])],
                provider_message_id=sent.provider_message_id,
            )
            conversations_started_total.labels(
                channel="whatsapp", store_id=str(store_id)
            ).inc()


# ---------------------------------------------------------------------------
async def handle_inbound_event(
    *,
    source: str,
    store_id: UUID | None,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Decode webhook payload → run a single FSM step → reply via provider."""

    if event_type not in {"message", "wa", "order"}:
        return  # status-only updates are handled elsewhere
    if store_id is None:
        # Best effort: try to resolve again (provider-specific)
        return

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await set_tenant_context(session, store_id=store_id, bypass=False)

            store_row = (
                await session.execute(
                    text(
                        """
                        SELECT s.id, s.org_id, s.name, s.brand_name, s.timezone,
                               s.currency, s.wa_provider, s.wa_phone_number_id,
                               app_decrypt_pii(s.wa_access_token_enc) AS wa_token,
                               s.agent_config
                        FROM stores s WHERE s.id = :sid
                        """
                    ),
                    {"sid": store_id},
                )
            ).first()
            if store_row is None:
                _log.warning("inbound.store_missing", store_id=str(store_id))
                return

            provider = build_wa_provider(
                provider_name=store_row.wa_provider,
                access_token=store_row.wa_token or get_settings().meta_wa_access_token.get_secret_value(),
                phone_number_id=store_row.wa_phone_number_id
                or get_settings().meta_wa_phone_number_id,
                api_version=get_settings().meta_wa_api_version,
            )
            inbound_messages = provider.parse_inbound(payload)
            if not inbound_messages:
                return

            llm = _build_llm()
            driver = FSMDriver(llm=llm)

            for inbound in inbound_messages:
                # Find the buyer + active conversation.
                phone_hash = await _hash_phone_via_db(session, inbound.from_phone_e164)
                customer = (
                    await session.execute(
                        text(
                            """
                            SELECT id, language FROM customers
                            WHERE store_id = :sid AND phone_hash = :ph
                            """
                        ),
                        {"sid": store_id, "ph": phone_hash},
                    )
                ).first()
                if customer is None:
                    # Unknown sender — log and ignore (we don't process unsolicited messages).
                    _log.info(
                        "inbound.unknown_sender",
                        store_id=str(store_id),
                        phone_hash=phone_hash,
                    )
                    continue

                convo = (
                    await session.execute(
                        text(
                            """
                            SELECT id, state, history, slots, agent_version_id, opened_at
                            FROM conversations
                            WHERE store_id = :sid AND customer_id = :cid
                              AND channel = 'whatsapp'
                              AND closed_at IS NULL
                            ORDER BY opened_at DESC
                            LIMIT 1
                            """
                        ),
                        {"sid": store_id, "cid": customer.id},
                    )
                ).first()
                if convo is None:
                    _log.info(
                        "inbound.no_open_conversation",
                        store_id=str(store_id),
                    )
                    continue

                inbound_text = inbound.body or ""
                if inbound.content_type == "voice":
                    inbound_text = await _transcribe_voice_note(provider, inbound, session)

                # Persist the inbound message immediately.
                await session.execute(
                    text(
                        """
                        INSERT INTO messages (
                            org_id, store_id, conversation_id, direction, role,
                            content_type, body, body_redacted,
                            channel_message_id, sent_at, created_at
                        ) VALUES (
                            :org, :sid, :cid, 'inbound', 'user',
                            :ct, :body, :body_red, :pm, :ts, now()
                        )
                        """
                    ),
                    {
                        "org": store_row.org_id,
                        "sid": store_id,
                        "cid": convo.id,
                        "ct": inbound.content_type,
                        "body": inbound_text,
                        "body_red": _redact(inbound_text),
                        "pm": inbound.provider_message_id,
                        "ts": inbound.timestamp,
                    },
                )

                history = _decode_history(convo.history or [])
                ctx_vars = await _build_template_vars(
                    session,
                    store_id=store_id,
                    customer_id=customer.id,
                    conversation_id=convo.id,
                    store_row=store_row,
                )
                system_prompt = _materialise_system_prompt(
                    template_vars=ctx_vars,
                    current_state=convo.state,
                )

                tool_handlers = _make_tool_handlers(
                    session=session,
                    store_id=store_id,
                    org_id=store_row.org_id,
                    conversation_id=convo.id,
                )
                step = await driver.step(
                    current_state=convo.state,
                    history=history,
                    latest_user_text=inbound_text,
                    system_prompt=system_prompt,
                    tool_handlers=tool_handlers,
                )

                # Send assistant reply if any.
                provider_msg_id = ""
                if step.assistant_text:
                    sent = await provider.send_text(
                        to_phone_e164=inbound.from_phone_e164,
                        body=step.assistant_text,
                        idempotency_key=f"{convo.id}:{uuid.uuid4()}",
                        reply_to_message_id=inbound.provider_message_id,
                    )
                    provider_msg_id = sent.provider_message_id

                await session.execute(
                    text(
                        """
                        INSERT INTO messages (
                            org_id, store_id, conversation_id, direction, role,
                            content_type, body, body_redacted,
                            channel_message_id, sent_at, created_at
                        ) VALUES (
                            :org, :sid, :cid, 'outbound', 'assistant',
                            'text', :body, :body_red, :pm, now(), now()
                        )
                        """
                    ),
                    {
                        "org": store_row.org_id,
                        "sid": store_id,
                        "cid": convo.id,
                        "body": step.assistant_text,
                        "body_red": _redact(step.assistant_text),
                        "pm": provider_msg_id,
                    },
                )

                outcome_value = _outcome_from_tools(step.tool_outcomes)
                await session.execute(
                    text(
                        """
                        UPDATE conversations
                           SET state = :state,
                               history = :hist::jsonb,
                               last_inbound_at = :now,
                               last_outbound_at = :now,
                               outcome = COALESCE(:oc, outcome),
                               closed_at = CASE WHEN :fin THEN :now ELSE closed_at END
                         WHERE id = :cid
                        """
                    ),
                    {
                        "state": step.next_state,
                        "hist": _encode_history(history),
                        "now": datetime.now(timezone.utc),
                        "oc": outcome_value,
                        "fin": step.finished,
                        "cid": convo.id,
                    },
                )
                if step.finished and outcome_value:
                    conversation_outcomes_total.labels(
                        outcome=outcome_value,
                        channel="whatsapp",
                        store_id=str(store_id),
                    ).inc()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
async def _load_order_context(
    session,  # type: ignore[no-untyped-def]
    *,
    order_id: UUID,
    store_id: UUID,
) -> dict[str, Any] | None:
    row = (
        await session.execute(
            text(
                """
                SELECT
                    o.id AS order_id,
                    o.org_id,
                    o.external_order_number,
                    o.total::float AS total,
                    o.currency,
                    o.line_items,
                    c.id AS customer_id,
                    c.language AS customer_language,
                    c.phone_hash,
                    app_decrypt_pii(c.phone_enc) AS phone_e164,
                    app_decrypt_pii(c.name_enc) AS customer_name,
                    s.brand_name,
                    s.agent_config,
                    s.wa_provider,
                    s.wa_phone_number_id,
                    app_decrypt_pii(s.wa_access_token_enc) AS wa_token
                FROM orders o
                JOIN customers c ON c.id = o.customer_id
                JOIN stores s ON s.id = o.store_id
                WHERE o.id = :oid AND o.store_id = :sid
                """
            ),
            {"oid": order_id, "sid": store_id},
        )
    ).first()
    if row is None:
        return None
    return {
        "order_id": row.order_id,
        "org_id": row.org_id,
        "order_number": row.external_order_number or str(row.order_id)[:8],
        "total": Decimal(row.total or 0),
        "currency": row.currency,
        "items": row.line_items or [],
        "customer_id": row.customer_id,
        "customer_language": row.customer_language,
        "phone_e164": row.phone_e164,
        "phone_hash": row.phone_hash,
        "customer_name": row.customer_name,
        "brand_name": row.brand_name,
        "agent_config": row.agent_config or {},
        "wa_provider": row.wa_provider,
        "wa_phone_number_id": row.wa_phone_number_id,
        "wa_token": row.wa_token,
    }


async def _build_provider_for_store(
    session,  # type: ignore[no-untyped-def]
    *,
    store_id: UUID,
    ctx: dict[str, Any],
):
    settings = get_settings()
    return build_wa_provider(
        provider_name=ctx["wa_provider"] or settings.wa_provider,
        access_token=ctx["wa_token"] or settings.meta_wa_access_token.get_secret_value(),
        phone_number_id=ctx["wa_phone_number_id"] or settings.meta_wa_phone_number_id,
        api_version=settings.meta_wa_api_version,
    )


async def _ensure_conversation(
    session,  # type: ignore[no-untyped-def]
    *,
    org_id: UUID,
    store_id: UUID,
    order_id: UUID,
    customer_id: UUID,
    phone_e164: str,
) -> UUID:
    existing = (
        await session.execute(
            text(
                """
                SELECT id FROM conversations
                WHERE store_id = :sid AND order_id = :oid AND closed_at IS NULL
                ORDER BY opened_at DESC LIMIT 1
                """
            ),
            {"sid": store_id, "oid": order_id},
        )
    ).first()
    if existing:
        return existing.id
    convo_id = (
        await session.execute(
            text(
                """
                INSERT INTO conversations (
                    org_id, store_id, customer_id, order_id,
                    channel, channel_provider, channel_thread_id, state, slots, history
                ) VALUES (
                    :org, :sid, :cid, :oid,
                    'whatsapp', 'meta_cloud', :thread, 'greeting', '{}'::jsonb, '[]'::jsonb
                )
                RETURNING id
                """
            ),
            {
                "org": org_id,
                "sid": store_id,
                "cid": customer_id,
                "oid": order_id,
                "thread": phone_e164,
            },
        )
    ).scalar_one()
    return convo_id


async def _persist_outbound(
    session,  # type: ignore[no-untyped-def]
    *,
    org_id: UUID,
    store_id: UUID,
    conversation_id: UUID,
    template: str,
    params: list[str],
    provider_message_id: str,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO messages (
                org_id, store_id, conversation_id, direction, role,
                content_type, body, template_name, template_params,
                channel_message_id, sent_at, created_at
            ) VALUES (
                :org, :sid, :cid, 'outbound', 'assistant',
                'template', NULL, :tpl, :tpl_params::jsonb,
                :pm, now(), now()
            )
            """
        ),
        {
            "org": org_id,
            "sid": store_id,
            "cid": conversation_id,
            "tpl": template,
            "tpl_params": params,
            "pm": provider_message_id,
        },
    )


async def _open_escalation(
    session,  # type: ignore[no-untyped-def]
    *,
    org_id: UUID,
    store_id: UUID,
    order_id: UUID,
    reason: str,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO escalation_queue (
                org_id, store_id, conversation_id, order_id,
                urgency, reason, transcript_excerpt
            )
            SELECT :org, :sid, NULL, :oid, 'normal', :r, NULL
            """
        ),
        {"org": org_id, "sid": store_id, "oid": order_id, "r": reason},
    )


def _build_llm():  # type: ignore[no-untyped-def]
    settings = get_settings()
    return build_llm_provider(
        provider_name=settings.llm_provider,
        api_key=(
            settings.anthropic_api_key.get_secret_value()
            if settings.llm_provider == "anthropic"
            else None
        ),
        base_url=(
            str(settings.vllm_base_url)
            if settings.llm_provider == "vllm"
            else (
                str(settings.ollama_base_url)
                if settings.llm_provider == "ollama"
                else None
            )
        ),
        model=(
            settings.anthropic_model_fast
            if settings.llm_provider == "anthropic"
            else settings.vllm_model
        ),
    )


async def _transcribe_voice_note(provider, inbound, session) -> str:  # type: ignore[no-untyped-def]
    """Best-effort transcription.  Returns ``""`` if unavailable."""

    media_id = (inbound.raw.get("audio") or {}).get("id") if isinstance(inbound.raw, dict) else None
    if not media_id:
        return ""
    try:
        audio, mime = await provider.fetch_media(media_id_or_url=media_id)
    except Exception:
        return ""
    # Real STT integration sits in awaaz_api.integrations; the worker
    # context cannot block on a heavy local model, so we delegate.
    try:
        from awaaz_api.integrations.stt_router import transcribe

        return await transcribe(audio_bytes=audio, mime=mime)
    except Exception:
        return ""


def _redact(s: str | None) -> str | None:
    if not s:
        return s
    import re

    return re.sub(r"\+?\d{10,15}", "<phone>", s)


def _decode_history(rows: list[dict[str, Any]]) -> list[Message]:
    out: list[Message] = []
    for r in rows:
        role = r.get("role")
        if role == "user":
            out.append(UserMessage(text=r.get("text", "")))
        elif role == "assistant":
            tcs = tuple(
                ToolCall(id=x["id"], name=x["name"], arguments=x.get("arguments", {}))
                for x in r.get("tool_calls", [])
            )
            out.append(AssistantMessage(text=r.get("text", ""), tool_calls=tcs))
        elif role == "tool":
            out.append(
                ToolResultMessage(
                    tool_call_id=r["tool_call_id"],
                    content=r.get("content", ""),
                    is_error=bool(r.get("is_error")),
                )
            )
        elif role == "system":
            out.append(SystemMessage(text=r.get("text", "")))
    return out


def _encode_history(history: list[Message]) -> str:
    out: list[dict[str, Any]] = []
    for m in history:
        if isinstance(m, UserMessage):
            out.append({"role": "user", "text": m.text})
        elif isinstance(m, AssistantMessage):
            out.append(
                {
                    "role": "assistant",
                    "text": m.text,
                    "tool_calls": [
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in m.tool_calls
                    ],
                }
            )
        elif isinstance(m, ToolResultMessage):
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_call_id,
                    "content": m.content,
                    "is_error": m.is_error,
                }
            )
        elif isinstance(m, SystemMessage):
            out.append({"role": "system", "text": m.text})
    return json.dumps(out, ensure_ascii=False)


async def _build_template_vars(
    session,  # type: ignore[no-untyped-def]
    *,
    store_id: UUID,
    customer_id: UUID,
    conversation_id: UUID,
    store_row,
) -> dict[str, str]:
    row = (
        await session.execute(
            text(
                """
                SELECT
                    o.external_order_number AS order_number,
                    o.total::float AS total,
                    o.currency,
                    o.line_items,
                    o.city, o.province, o.postal_code,
                    app_decrypt_pii(c.name_enc) AS customer_name,
                    app_decrypt_pii(o.address_line1_enc) AS line1
                FROM conversations conv
                JOIN orders o ON o.id = conv.order_id
                JOIN customers c ON c.id = o.customer_id
                WHERE conv.id = :cid
                """
            ),
            {"cid": conversation_id},
        )
    ).first()
    if row is None:
        return {
            "agent_name": store_row.agent_config.get("agent_name", "Sahar"),
            "brand_name": store_row.brand_name,
            "current_state": "greeting",
            "order_number": "",
            "item_count": "0",
            "total_in_words": "0",
            "address": "",
            "customer_name": "",
        }
    items = row.line_items or []
    return {
        "agent_name": store_row.agent_config.get("agent_name", "Sahar"),
        "brand_name": store_row.brand_name,
        "current_state": "",  # filled by _materialise_system_prompt
        "order_number": row.order_number or "",
        "item_count": str(sum(int(i.get("qty", 1)) for i in items) or len(items)),
        "total_in_words": number_to_urdu_words(int(row.total or 0)),
        "address": ", ".join(
            x for x in [row.line1, row.city, row.province, row.postal_code] if x
        ),
        "customer_name": row.customer_name or "",
    }


def _materialise_system_prompt(
    *, template_vars: dict[str, str], current_state: str
) -> str:
    raw = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    template_vars["current_state"] = current_state
    for k, v in template_vars.items():
        raw = raw.replace("{{" + k + "}}", str(v))
    return raw


def _make_tool_handlers(
    *,
    session,  # type: ignore[no-untyped-def]
    store_id: UUID,
    org_id: UUID,
    conversation_id: UUID,
) -> dict[ToolName, ToolHandler]:
    """Bind tool side-effects to a session + conversation.

    Tool calls within a single FSM step share the same DB transaction.
    """

    async def _common_outcome(name: ToolName, message: str, *, error: bool = False) -> ToolOutcome:
        return ToolOutcome(
            name=name,
            arguments={},
            text_result=message,
            is_error=error,
        )

    async def confirm(call: ToolCall) -> ToolOutcome:
        await session.execute(
            text(
                """
                UPDATE orders o
                SET confirmation_status = 'confirmed', tags = array_append(tags, 'cod-confirmed')
                FROM conversations c
                WHERE c.id = :cid AND o.id = c.order_id
                """
            ),
            {"cid": conversation_id},
        )
        return ToolOutcome(
            name="confirm_order",
            arguments=call.arguments,
            text_result="Order marked as confirmed.",
        )

    async def cancel(call: ToolCall) -> ToolOutcome:
        await session.execute(
            text(
                """
                UPDATE orders o
                SET confirmation_status = 'cancelled',
                    tags = array_append(tags, 'cod-cancelled'),
                    metadata = jsonb_set(metadata, '{cancel_reason}', to_jsonb(:r))
                FROM conversations c
                WHERE c.id = :cid AND o.id = c.order_id
                """
            ),
            {"cid": conversation_id, "r": call.arguments.get("reason", "")},
        )
        return ToolOutcome(
            name="cancel_order",
            arguments=call.arguments,
            text_result="Order marked as cancelled.",
        )

    async def reschedule(call: ToolCall) -> ToolOutcome:
        await session.execute(
            text(
                """
                UPDATE orders o
                SET confirmation_status = 'rescheduled',
                    tags = array_append(tags, 'cod-callback'),
                    metadata = metadata || jsonb_build_object(
                        'reschedule_label', :lbl,
                        'reschedule_iso', :iso
                    )
                FROM conversations c
                WHERE c.id = :cid AND o.id = c.order_id
                """
            ),
            {
                "cid": conversation_id,
                "lbl": call.arguments.get("requested_label", ""),
                "iso": call.arguments.get("requested_iso"),
            },
        )
        return ToolOutcome(
            name="reschedule_delivery",
            arguments=call.arguments,
            text_result="Delivery rescheduled.",
        )

    async def change_request(call: ToolCall) -> ToolOutcome:
        await session.execute(
            text(
                """
                INSERT INTO escalation_queue
                    (org_id, store_id, conversation_id, order_id, urgency, reason, transcript_excerpt)
                SELECT :org, :sid, :cid, c.order_id, 'normal', :r, NULL
                FROM conversations c WHERE c.id = :cid
                """
            ),
            {
                "org": org_id,
                "sid": store_id,
                "cid": conversation_id,
                "r": f"change_request:{call.arguments.get('field')}={call.arguments.get('requested_value')}",
            },
        )
        await session.execute(
            text(
                """
                UPDATE orders o
                SET confirmation_status = 'change_request',
                    tags = array_append(tags, 'cod-change-request')
                FROM conversations c
                WHERE c.id = :cid AND o.id = c.order_id
                """
            ),
            {"cid": conversation_id},
        )
        return ToolOutcome(
            name="flag_change_request",
            arguments=call.arguments,
            text_result="Change request logged for merchant review.",
        )

    async def wrong_number(call: ToolCall) -> ToolOutcome:
        await session.execute(
            text(
                """
                UPDATE orders o
                SET confirmation_status = 'wrong_number',
                    tags = array_append(tags, 'cod-fake-address')
                FROM conversations c
                WHERE c.id = :cid AND o.id = c.order_id
                """
            ),
            {"cid": conversation_id},
        )
        await session.execute(
            text(
                """
                UPDATE customers SET fake_order_count = fake_order_count + 1
                WHERE id = (SELECT customer_id FROM conversations WHERE id = :cid)
                """
            ),
            {"cid": conversation_id},
        )
        return ToolOutcome(
            name="flag_wrong_number",
            arguments=call.arguments,
            text_result="Marked wrong number.",
        )

    async def proxy(call: ToolCall) -> ToolOutcome:
        await session.execute(
            text(
                """
                UPDATE orders o
                SET confirmation_status = 'rescheduled',
                    metadata = jsonb_set(metadata, '{proxy_callback}', to_jsonb(:lbl))
                FROM conversations c
                WHERE c.id = :cid AND o.id = c.order_id
                """
            ),
            {"cid": conversation_id, "lbl": call.arguments.get("callback_label", "")},
        )
        return ToolOutcome(
            name="flag_proxy_answerer",
            arguments=call.arguments,
            text_result="Callback scheduled with proxy answerer.",
        )

    async def escalate(call: ToolCall) -> ToolOutcome:
        await session.execute(
            text(
                """
                INSERT INTO escalation_queue
                    (org_id, store_id, conversation_id, order_id, urgency, reason, transcript_excerpt)
                SELECT :org, :sid, :cid, c.order_id, :urg, :r, NULL
                FROM conversations c WHERE c.id = :cid
                """
            ),
            {
                "org": org_id,
                "sid": store_id,
                "cid": conversation_id,
                "urg": call.arguments.get("urgency", "normal"),
                "r": call.arguments.get("reason", ""),
            },
        )
        await session.execute(
            text(
                """
                UPDATE orders o
                SET confirmation_status = 'escalated'
                FROM conversations c
                WHERE c.id = :cid AND o.id = c.order_id
                """
            ),
            {"cid": conversation_id},
        )
        return ToolOutcome(
            name="escalate_to_human",
            arguments=call.arguments,
            text_result="Escalated to merchant operator.",
        )

    async def switch_lang(call: ToolCall) -> ToolOutcome:
        return ToolOutcome(
            name="switch_language",
            arguments=call.arguments,
            text_result=f"Switched to {call.arguments.get('target_language')}.",
        )

    async def end_convo(call: ToolCall) -> ToolOutcome:
        return ToolOutcome(
            name="end_conversation",
            arguments=call.arguments,
            text_result="Conversation closing.",
        )

    return {
        "confirm_order": confirm,
        "cancel_order": cancel,
        "reschedule_delivery": reschedule,
        "flag_change_request": change_request,
        "flag_wrong_number": wrong_number,
        "flag_proxy_answerer": proxy,
        "escalate_to_human": escalate,
        "switch_language": switch_lang,
        "end_conversation": end_convo,
    }


def _outcome_from_tools(outcomes: list) -> str | None:  # type: ignore[no-untyped-def]
    mapping = {
        "confirm_order": "confirmed",
        "cancel_order": "cancelled",
        "reschedule_delivery": "rescheduled",
        "flag_change_request": "change_request",
        "flag_wrong_number": "wrong_number",
        "flag_proxy_answerer": "callback",
        "escalate_to_human": "escalated",
    }
    for o in outcomes:
        if not o.is_error and o.name in mapping:
            return mapping[o.name]
    return None


async def _hash_phone_via_db(session, phone_e164: str) -> str:  # type: ignore[no-untyped-def]
    return (
        await session.execute(
            text("SELECT app_phone_hash(:p)"),
            {"p": phone_e164},
        )
    ).scalar_one()
