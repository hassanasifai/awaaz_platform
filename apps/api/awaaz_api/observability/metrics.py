"""Prometheus metrics — declared once, imported wherever needed."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

# ---- traffic
conversations_started_total = Counter(
    "awaaz_conversations_total",
    "Conversations started, by channel + tenant.",
    labelnames=("channel", "store_id"),
)

conversation_outcomes_total = Counter(
    "awaaz_conversation_outcomes_total",
    "Final conversation outcomes.",
    labelnames=("outcome", "channel", "store_id"),
)

conversation_latency_seconds = Histogram(
    "awaaz_response_latency_seconds",
    "User-perceived turn-around latency, by channel.",
    labelnames=("channel",),
    buckets=(0.1, 0.25, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0),
)

llm_request_seconds = Histogram(
    "awaaz_llm_request_seconds",
    "LLM call duration end-to-end.",
    labelnames=("provider", "model"),
    buckets=(0.1, 0.25, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0),
)

cost_usd_total = Counter(
    "awaaz_cost_usd_total",
    "Running USD cost by component.",
    labelnames=("component", "provider", "store_id"),
)

webhook_events_total = Counter(
    "awaaz_webhook_events_total",
    "Inbound webhook events processed.",
    labelnames=("source", "result"),
)

dispatcher_queue_depth = Histogram(
    "awaaz_dispatcher_queue_depth",
    "Snapshots of the retry queue depth.",
    buckets=(0, 10, 50, 100, 500, 1000, 5000, 10000),
)
