"""Observability primitives — structured logs, OTel, Sentry."""

from __future__ import annotations

from .logging import bind_request_context, configure_logging, get_logger
from .otel import setup_telemetry, tracer
from .metrics import (
    conversation_latency_seconds,
    conversations_started_total,
    conversation_outcomes_total,
    cost_usd_total,
    webhook_events_total,
)

__all__ = [
    "configure_logging",
    "get_logger",
    "bind_request_context",
    "setup_telemetry",
    "tracer",
    "conversation_latency_seconds",
    "conversations_started_total",
    "conversation_outcomes_total",
    "cost_usd_total",
    "webhook_events_total",
]
