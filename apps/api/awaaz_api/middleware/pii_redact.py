"""Outbound PII redaction safety-net.

This is defense-in-depth — every JSON payload passing through the dashboard
should already have decrypted via the application; we still scrub a small
allowlist of obviously-PII fields in case a developer accidentally returns a
raw column.  Production redaction is the ``logging`` processor; this is the
HTTP layer.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import orjson
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "password_hash",
        "secret",
        "phone_enc",
        "name_enc",
        "email_enc",
        "address_line1_enc",
        "address_line2_enc",
        "wa_access_token_enc",
        "wa_app_secret_enc",
        "platform_access_token_enc",
        "webhook_secret_enc",
        "key_hash",
        "mfa_secret_enc",
    }
)


def _scrub(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            k: ("<redacted>" if k in _FORBIDDEN_KEYS else _scrub(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


class PIIRedactionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        ctype = response.headers.get("content-type", "")
        if "application/json" not in ctype.lower():
            return response
        # Stream out otherwise.
        if isinstance(response, StreamingResponse):
            return response
        body = b""
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            body += chunk
        try:
            payload = orjson.loads(body)
        except orjson.JSONDecodeError:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=ctype,
            )
        scrubbed = _scrub(payload)
        out_body = orjson.dumps(scrubbed)
        headers = dict(response.headers)
        headers["content-length"] = str(len(out_body))
        return Response(
            content=out_body,
            status_code=response.status_code,
            headers=headers,
            media_type=ctype,
        )
