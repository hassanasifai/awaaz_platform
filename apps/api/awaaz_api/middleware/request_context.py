"""Stamp every request with an id + trace id; bind structlog context."""

from __future__ import annotations

import time
import uuid
from typing import Final

from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from awaaz_api.observability import (
    bind_request_context,
    get_logger,
)
from awaaz_api.observability.logging import clear_request_context

_log = get_logger("awaaz.http")
_REQUEST_ID_HEADER: Final = "X-Request-Id"
_TRACE_ID_HEADER: Final = "X-Trace-Id"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())
        span = trace.get_current_span()
        trace_id = (
            f"{span.get_span_context().trace_id:032x}"
            if span.get_span_context().is_valid
            else ""
        )
        bind_request_context(
            request_id=request_id,
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            _log.exception("http.error", error=str(exc))
            raise
        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers[_REQUEST_ID_HEADER] = request_id
        if trace_id:
            response.headers[_TRACE_ID_HEADER] = trace_id
        _log.info(
            "http.request",
            status=response.status_code,
            duration_ms=duration_ms,
        )
        clear_request_context()
        return response
