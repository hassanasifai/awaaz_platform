"""Resolve the per-store WA provider from config."""

from __future__ import annotations

from .base import WAChannelProvider


def build_wa_provider(
    *,
    provider_name: str,
    access_token: str,
    phone_number_id: str | None = None,
    api_version: str = "v21.0",
    graph_base: str = "https://graph.facebook.com",
    base_url: str | None = None,
    auth_extra: dict[str, str] | None = None,
) -> WAChannelProvider:
    if provider_name == "meta_cloud":
        from .meta_cloud import MetaCloudWAChannel

        if not phone_number_id:
            raise ValueError("phone_number_id required for meta_cloud")
        return MetaCloudWAChannel(
            access_token=access_token,
            phone_number_id=phone_number_id,
            api_version=api_version,
            graph_base=graph_base,
        )
    if provider_name == "dialog360":
        from .dialog360 import Dialog360WAChannel

        return Dialog360WAChannel(
            api_key=access_token,
            base_url=base_url or "https://waba-v2.360dialog.io",
        )
    if provider_name == "twilio_wa":
        from .twilio_wa import TwilioWAChannel

        if auth_extra is None:
            raise ValueError("twilio_wa needs auth_extra={account_sid, from_}")
        return TwilioWAChannel(
            account_sid=auth_extra["account_sid"],
            auth_token=access_token,
            from_=auth_extra.get("from_", ""),
        )
    raise ValueError(f"unknown WA provider {provider_name!r}")
