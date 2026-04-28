"""Meta WA Cloud API webhook payload parser."""

from __future__ import annotations

from datetime import datetime, timezone

from awaaz_api.channels.meta_cloud import MetaCloudWAChannel


def _make_provider() -> MetaCloudWAChannel:
    return MetaCloudWAChannel(access_token="t", phone_number_id="1")


def test_parse_text_message():
    p = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"display_phone_number": "923001112233"},
                            "messages": [
                                {
                                    "id": "wamid.abc",
                                    "from": "923331234567",
                                    "timestamp": "1714400000",
                                    "type": "text",
                                    "text": {"body": "ji"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    msgs = _make_provider().parse_inbound(p)
    assert len(msgs) == 1
    msg = msgs[0]
    assert msg.body == "ji"
    assert msg.from_phone_e164 == "+923331234567"
    assert msg.to_phone_e164 == "+923001112233"
    assert msg.content_type == "text"
    assert msg.timestamp == datetime.fromtimestamp(1714400000, tz=timezone.utc)


def test_parse_voice_note_creates_media_block():
    p = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"display_phone_number": "923001112233"},
                            "messages": [
                                {
                                    "id": "wamid.audio",
                                    "from": "923331234567",
                                    "timestamp": "0",
                                    "type": "audio",
                                    "audio": {
                                        "id": "media-id",
                                        "mime_type": "audio/ogg",
                                        "sha256": "abc",
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    msg = _make_provider().parse_inbound(p)[0]
    assert msg.content_type == "voice"
    assert msg.media is not None
    assert msg.media.mime == "audio/ogg"


def test_parse_button_reply():
    p = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"display_phone_number": "1"},
                            "messages": [
                                {
                                    "id": "x",
                                    "from": "923331234567",
                                    "timestamp": "0",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {
                                            "id": "confirm",
                                            "title": "Confirm",
                                        },
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    msg = _make_provider().parse_inbound(p)[0]
    assert msg.content_type == "button_reply"
    assert msg.body == "Confirm"


def test_parse_empty_payload():
    assert _make_provider().parse_inbound({}) == []
