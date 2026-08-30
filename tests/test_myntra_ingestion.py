from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from models.base import Base
from services.auth import get_current_user_id


def event_payload(event_id=None, *, product_id="12345", event_type="product_view"):
    return {
        "event_id": event_id or str(uuid4()),
        "platform": "myntra",
        "event_type": event_type,
        "occurred_at": "2026-08-30T10:00:00+05:30",
        "page_url": "https://www.myntra.com/shirts/example/12345/buy",
        "product": {
            "platform": "myntra",
            "product_id": product_id,
            "brand": "Example Brand",
            "title": "Example Shirt",
            "category": "shirts",
            "price": 1299,
            "currency": "INR",
            "source": "dom_or_structured_page_data",
        },
        "extension_version": "1.0.0",
        "parser_version": "myntra-1",
    }


@pytest.fixture
def client():
    from routers.myntra import router

    app = FastAPI()
    app.include_router(router)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user_id] = lambda: "myntra-user-a"
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def test_health_is_public(client):
    response = client.get("/myntra/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "myntra"}


def test_single_event_is_persisted_and_idempotent(client):
    payload = event_payload()

    first = client.post("/myntra/events", json=payload)
    second = client.post("/myntra/events", json=payload)

    assert first.status_code == 201
    assert first.json()["inserted"] is True
    assert second.status_code == 201
    assert second.json()["inserted"] is False
    assert client.get("/myntra/events/status").json()["total_events"] == 1


def test_batch_deduplicates_and_history_is_user_scoped(client):
    duplicate_id = str(uuid4())
    response = client.post(
        "/myntra/events/batch",
        json={"events": [event_payload(duplicate_id), event_payload(duplicate_id), event_payload(product_id="99999")]},
    )
    assert response.status_code == 200
    assert response.json()["accepted"] == 2
    assert response.json()["duplicates"] == 1

    history = client.get("/myntra/history?brand=Example%20Brand")
    assert history.status_code == 200
    assert history.json()["total"] == 2
    assert {item["product_id"] for item in history.json()["events"]} == {"12345", "99999"}

    products = client.get("/myntra/history/products")
    assert products.status_code == 200
    assert {item["product_id"] for item in products.json()["products"]} == {"12345", "99999"}


def test_ingestion_requires_authentication(client):
    client.app.dependency_overrides.pop(get_current_user_id)
    response = client.post("/myntra/events", json=event_payload())
    assert response.status_code == 401


def test_event_id_cannot_be_replayed_by_another_user(client):
    payload = event_payload()
    assert client.post("/myntra/events", json=payload).status_code == 201

    client.app.dependency_overrides[get_current_user_id] = lambda: "myntra-user-b"
    response = client.post("/myntra/events", json=payload)
    assert response.status_code == 409


def test_connection_feedback_export_and_data_deletion(client):
    assert client.post("/myntra/connection", json={"enabled": True, "collect_product_views": True, "collect_search": False, "collect_wishlist": True, "collect_cart": True, "collect_orders": False}).json()["enabled"] is True
    assert client.get("/myntra/connection").json()["collect_search"] is False
    assert client.post("/myntra/events", json=event_payload()).status_code == 201
    assert client.post("/myntra/feedback", json={"product_id": "12345", "feedback": "like"}).status_code == 201
    csv_response = client.get("/myntra/export.csv")
    assert csv_response.status_code == 200
    assert csv_response.text.startswith("event_id,user_id,event_type")
    assert client.delete("/myntra/data").status_code == 204
    assert client.get("/myntra/events/status").json()["total_events"] == 0


def test_profile_and_recommendations_are_derived_from_events(client):
    payload = event_payload(product_id="12345")
    assert client.post("/myntra/events", json=payload).status_code == 201
    profile = client.post("/myntra/profile/rebuild")
    assert profile.status_code == 200
    assert profile.json()["brands"]["example brand"] > 0
    recommendations = client.get("/myntra/recommendations")
    assert recommendations.status_code == 200
    # Already strongly interacted-with products are not re-suggested.
    assert recommendations.json()["recommendations"] == []
