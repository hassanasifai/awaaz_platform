"""OpenTelemetry bootstrap.

Idempotent: safe to call ``setup_telemetry()`` from both API and worker entry
points.  Exports are silently no-op if ``OTEL_EXPORTER_OTLP_ENDPOINT`` is
unset (test environments).
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer

from awaaz_api.settings import get_settings

_INSTALLED = False


def setup_telemetry(*, instrument_fastapi_app=None) -> None:  # type: ignore[no-untyped-def]
    """Configure tracer + auto-instrumentations once.

    Pass the FastAPI app via ``instrument_fastapi_app`` to enable HTTP
    auto-instrumentation.  Idempotent.
    """

    global _INSTALLED
    if _INSTALLED:
        if instrument_fastapi_app is not None:
            _instrument_app(instrument_fastapi_app)
        return

    settings = get_settings()

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.namespace": "awaaz",
            "deployment.environment": settings.environment,
        }
    )

    provider = TracerProvider(resource=resource)
    if settings.otel_exporter_otlp_endpoint and not _is_test_env():
        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Auto-instrument the libraries we use everywhere.
    if instrument_fastapi_app is not None:
        _instrument_app(instrument_fastapi_app)

    _INSTALLED = True


def _instrument_app(app) -> None:  # type: ignore[no-untyped-def]
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    if not getattr(app.state, "_otel_instrumented", False):
        FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz,readyz,metrics")
        app.state._otel_instrumented = True


def _is_test_env() -> bool:
    return os.environ.get("ENVIRONMENT", "").lower() == "test"


def tracer(name: str = "awaaz") -> Tracer:
    return trace.get_tracer(name)
