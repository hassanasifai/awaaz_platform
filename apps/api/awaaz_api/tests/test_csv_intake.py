"""CSV row → OrderIntake parsing logic."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from awaaz_api.schemas.order import OrderIntake


def _make_payload(**overrides) -> OrderIntake:  # type: ignore[no-untyped-def]
    base = {
        "merchant_id": "store-1",
        "platform": "custom",
        "order_id": "1001",
        "external_order_id": "1001",
        "customer": {"name": "Ali Raza", "phone": "0300-1234567", "language": "ur"},
        "address": {
            "line1": "Main St 1",
            "city": "Karachi",
            "province": "Sindh",
            "postal_code": "75300",
        },
        "items": [{"name": "Lawn Suit", "qty": 2, "unit_price": Decimal("2500")}],
        "total": Decimal("5000"),
        "currency": "PKR",
        "placed_at": datetime(2026, 4, 28, 12, 0, 0),
        "idempotency_key": "test-1234",
    }
    base.update(overrides)
    return OrderIntake.model_validate(base)


def test_intake_normalises_phone() -> None:
    p = _make_payload()
    assert p.customer.phone == "+923001234567"


def test_intake_rejects_invalid_phone() -> None:
    with pytest.raises(Exception):
        _make_payload(customer={"name": "x", "phone": "not-a-phone", "language": "ur"})


def test_intake_rejects_zero_items() -> None:
    with pytest.raises(Exception):
        _make_payload(items=[])


def test_intake_total_must_be_non_negative() -> None:
    with pytest.raises(Exception):
        _make_payload(total=Decimal("-1"))
