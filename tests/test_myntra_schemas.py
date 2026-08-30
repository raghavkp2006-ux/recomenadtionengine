from uuid import uuid4

import pytest
from pydantic import ValidationError

from schemas.myntra import MyntraBatchEventRequest, MyntraEventPayload, MyntraProductPayload


def valid_event(**overrides):
    event = {
        "event_id": str(uuid4()),
        "platform": "myntra",
        "event_type": "product_view",
        "occurred_at": "2026-08-30T10:00:00+05:30",
        "page_url": "https://www.myntra.com/shirts/example/12345/buy",
        "extension_version": "1.0.0",
    }
    event.update(overrides)
    return event


def test_product_accepts_missing_page_fields_and_normalizes_currency():
    product = MyntraProductPayload(
        product_id="12345",
        title="Minimal Shirt",
        currency="inr",
        sizes=["M", "L"],
    )

    assert product.platform == "myntra"
    assert product.brand is None
    assert product.price is None
    assert product.currency == "INR"


def test_product_rejects_invalid_rating():
    with pytest.raises(ValidationError):
        MyntraProductPayload(rating=5.1)


def test_event_requires_timezone_and_does_not_accept_client_user_id():
    with pytest.raises(ValidationError):
        MyntraEventPayload(**valid_event(occurred_at="2026-08-30T10:00:00"))

    with pytest.raises(ValidationError):
        MyntraEventPayload(**valid_event(user_id="another-user"))


def test_batch_accepts_at_most_one_hundred_events():
    batch = MyntraBatchEventRequest(events=[valid_event(), valid_event()])
    assert len(batch.events) == 2

    with pytest.raises(ValidationError):
        MyntraBatchEventRequest(events=[valid_event() for _ in range(101)])
