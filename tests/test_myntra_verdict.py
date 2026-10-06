"""Tests for services/fashion_crosswalk.py, services/myntra_verdict.py, and verdict endpoints."""

from datetime import datetime, timezone
import json
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from models.base import Base
from models.myntra import MyntraEvent, MyntraFeedback, MyntraProduct
from services.auth import get_current_user_id
from services.fashion_crosswalk import FASHION_CROSSWALK, crosswalk_affinity
from services.myntra_profile import rebuild_profile
from services.myntra_verdict import (
    BUY_PCT,
    MIN_BUY_FIT,
    SKIP_PCT,
    W_CROSS,
    W_DIRECT,
    W_PRICE,
    _compute_fit,
    score_feed,
    score_single,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def api_client(db_session):
    from routers.myntra import check_ingestion_rate, router

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user_id] = lambda: "test-verdict-user"
    app.dependency_overrides[check_ingestion_rate] = lambda: "test-verdict-user"

    return TestClient(app)


def test_crosswalk_affinity_calculation():
    taste = {
        "profile": {"action": 80.0, "romance": 20.0},
        "breakdown": {"anilist": {"action": 80.0}, "spotify": {"romance": 20.0}},
    }
    # Matching product for action (colours: black/red/grey, categories: shirts/tops)
    product = {
        "product_id": "p1",
        "colour": "Black",
        "category": "Shirts",
        "occasion": "Casual",
        "pattern": "Solid",
    }
    score, evidence = crosswalk_affinity(product, taste)
    assert score is not None
    assert 0.0 <= score <= 1.0
    assert len(evidence) > 0
    domains = {e["domain"] for e in evidence}
    assert "anilist" in domains or "spotify" in domains


def test_crosswalk_none_when_no_media_signal():
    taste_empty = {"profile": {}, "breakdown": {}}
    product = {"colour": "Black", "category": "Shirts"}
    score, evidence = crosswalk_affinity(product, taste_empty)
    assert score is None
    assert evidence == []


def test_component_none_renormalization():
    # Hand-computed verification:
    # W_DIRECT=0.5, W_CROSS=0.3, W_PRICE=0.2, W_REDUNDANCY=0.25
    # If direct=0.8, crosswalk=None, price=None, redundancy=0.0:
    # Available is only direct (weight 0.5), so normalized base_fit = 0.8
    # fit = 0.8 - (0.25 * 0.0) = 0.8
    fit_direct_only = _compute_fit(direct=0.8, crosswalk=None, price_fit_val=None, redundancy=0.0)
    assert fit_direct_only == pytest.approx(0.8, rel=1e-3)

    # If direct=0.6, crosswalk=0.4, price=None, redundancy=0.0:
    # Available weights: 0.5 + 0.3 = 0.8
    # base_fit = (0.6*0.5 + 0.4*0.3) / 0.8 = (0.3 + 0.12) / 0.8 = 0.42 / 0.8 = 0.525
    fit_two = _compute_fit(direct=0.6, crosswalk=0.4, price_fit_val=None, redundancy=0.0)
    assert fit_two == pytest.approx(0.525, rel=1e-3)

    # If all positive components are None:
    fit_none = _compute_fit(direct=None, crosswalk=None, price_fit_val=None, redundancy=0.0)
    assert fit_none is None


def test_cold_start_empty_feed(db_session):
    user_id = "cold-user"
    taste_empty = {"profile": {}, "breakdown": {}}
    result = score_feed(db_session, user_id, taste_empty)
    assert result["items"] == []
    assert result["counts"] == {"buy": 0, "consider": 0, "skip": 0}
    assert result["summary"]["signals"]["myntra"] is False
    assert result["summary"]["signals"]["spotify"] is False
    assert result["summary"]["signals"]["anilist"] is False


def test_kids_items_never_appear(db_session):
    user_id = "user-kids-test"
    # Seed adult and kids items
    db_session.add(MyntraProduct(
        product_id="adult-1",
        title="Men Casual Shirt",
        gender="Men",
        category="Shirts",
        price=1000.0,
    ))
    db_session.add(MyntraProduct(
        product_id="kid-1",
        title="Boys Kurta Set",
        gender="Boys",
        category="Kurta Sets",
        price=800.0,
    ))
    db_session.add(MyntraProduct(
        product_id="kid-2",
        title="Girls Floral Dress",
        gender="Girls",
        category="Dresses",
        price=900.0,
    ))
    db_session.commit()

    taste = {
        "profile": {"action": 50.0},
        "breakdown": {"anilist": {"action": 50.0}},
    }
    feed = score_feed(db_session, user_id, taste, gender="all")
    item_ids = [it["product_id"] for it in feed["items"]]
    assert "adult-1" in item_ids
    assert "kid-1" not in item_ids
    assert "kid-2" not in item_ids


def test_determinism(db_session):
    user_id = "user-det"
    for i in range(10):
        db_session.add(MyntraProduct(
            product_id=f"det-{i}",
            title=f"Cotton Shirt {i}",
            brand="BrandX",
            category="Shirts",
            colour="Black" if i % 2 == 0 else "Blue",
            gender="Men",
            price=1000.0 + i * 100,
        ))
    db_session.commit()

    taste = {
        "profile": {"action": 60.0, "drama": 40.0},
        "breakdown": {"anilist": {"action": 60.0, "drama": 40.0}},
    }

    feed1 = score_feed(db_session, user_id, taste)
    feed2 = score_feed(db_session, user_id, taste)

    assert feed1["counts"] == feed2["counts"]
    assert len(feed1["items"]) == len(feed2["items"])
    for it1, it2 in zip(feed1["items"], feed2["items"]):
        assert it1["product_id"] == it2["product_id"]
        assert it1["fit"] == it2["fit"]
        assert it1["verdict"] == it2["verdict"]


def test_verdict_bands_and_grounded_reasons(db_session):
    user_id = "user-bands"

    # Add 20 catalog products spanning diverse categories/colours/prices
    for i in range(20):
        db_session.add(MyntraProduct(
            product_id=f"p-{i}",
            title=f"Item {i}",
            brand="FavBrand" if i < 5 else "OtherBrand",
            category="Shirts" if i < 8 else ("Kurtas" if i < 15 else "Bedsheets"),
            colour="Black" if i < 5 else ("Navy" if i < 10 else "Yellow"),
            gender="Men",
            price=1000.0 + (i * 200.0),
        ))

    # Add a user browsing event for FavBrand black shirts
    ev_payload = {
        "brand": "FavBrand",
        "category": "Shirts",
        "colour": "Black",
        "title": "FavBrand Black Shirt",
        "price": 1000.0,
    }
    db_session.add(MyntraEvent(
        event_id="ev-1",
        user_id=user_id,
        event_type="product_view",
        occurred_at=datetime.now(timezone.utc),
        extension_version="1.0.0",
        product_id="p-0",
        product_json=json.dumps(ev_payload),
    ))
    db_session.commit()
    rebuild_profile(db_session, user_id)

    taste = {
        "profile": {"action": 80.0, "drama": 20.0},
        "breakdown": {"anilist": {"action": 80.0, "drama": 20.0}},
    }

    feed = score_feed(db_session, user_id, taste, limit=50)
    assert len(feed["items"]) > 0

    verdicts = {it["verdict"] for it in feed["items"]}
    assert "BUY" in verdicts
    assert "SKIP" in verdicts

    for it in feed["items"]:
        if it["verdict"] == "BUY":
            assert it["fit"] >= MIN_BUY_FIT

        # Grounding check: verify evidence is non-empty
        for r in it["reasons"]:
            assert r["domain"] in ("myntra", "spotify", "anilist", "movies")
            assert len(r["text"]) > 0
            assert isinstance(r["evidence"], dict)
            assert len(r["evidence"]) > 0


def test_wishlist_cart_purchase_exclusions_and_single_status(db_session):
    user_id = "user-exclusions"

    db_session.add(MyntraProduct(
        product_id="p-wish",
        title="Wishlist Shirt",
        category="Shirts",
        gender="Men",
        price=1500.0,
    ))
    db_session.add(MyntraProduct(
        product_id="p-cart",
        title="Cart Shirt",
        category="Shirts",
        gender="Men",
        price=1500.0,
    ))
    db_session.add(MyntraProduct(
        product_id="p-regular",
        title="Regular Shirt",
        category="Shirts",
        gender="Men",
        price=1500.0,
    ))

    # Add wishlist and cart events
    db_session.add(MyntraEvent(
        event_id="ev-wish",
        user_id=user_id,
        event_type="wishlist_add",
        occurred_at=datetime.now(timezone.utc),
        extension_version="1.0.0",
        product_id="p-wish",
        product_json=json.dumps({"product_id": "p-wish", "category": "Shirts"}),
    ))
    db_session.add(MyntraEvent(
        event_id="ev-cart",
        user_id=user_id,
        event_type="cart_add",
        occurred_at=datetime.now(timezone.utc),
        extension_version="1.0.0",
        product_id="p-cart",
        product_json=json.dumps({"product_id": "p-cart", "category": "Shirts"}),
    ))
    db_session.commit()

    taste = {"profile": {"action": 50.0}, "breakdown": {"anilist": {"action": 50.0}}}

    # Feed must exclude p-wish and p-cart
    feed = score_feed(db_session, user_id, taste)
    feed_pids = [it["product_id"] for it in feed["items"]]
    assert "p-wish" not in feed_pids
    assert "p-cart" not in feed_pids
    assert "p-regular" in feed_pids

    # score_single for p-wish returns status="in_wishlist"
    single_wish = score_single(db_session, user_id, taste, {"product_id": "p-wish"})
    assert single_wish["status"] == "in_wishlist"

    # score_single for p-cart returns status="in_cart"
    single_cart = score_single(db_session, user_id, taste, {"product_id": "p-cart"})
    assert single_cart["status"] == "in_cart"

    # score_single for regular returns status="evaluated"
    single_reg = score_single(db_session, user_id, taste, {"product_id": "p-regular", "category": "Shirts"})
    assert single_reg["status"] == "evaluated"


def test_api_endpoints_verdicts_and_verdict(api_client, db_session):
    db_session.add(MyntraProduct(
        product_id="api-p1",
        title="Api Product",
        category="Shirts",
        gender="Men",
        price=1200.0,
    ))
    db_session.commit()

    # GET /myntra/verdicts
    res = api_client.get("/myntra/verdicts")
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data
    assert "counts" in data
    assert "items" in data

    # POST /myntra/verdict with valid product_id
    post_res = api_client.post("/myntra/verdict", json={"product_id": "api-p1"})
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["product_id"] == "api-p1"
    assert post_data["status"] == "evaluated"


def test_post_verdict_422_on_empty_body(api_client):
    # Calling POST /myntra/verdict with empty dict must fail validation
    res = api_client.post("/myntra/verdict", json={})
    assert res.status_code == 422


def test_unauthenticated_returns_401():
    from routers.myntra import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    res_get = client.get("/myntra/verdicts")
    assert res_get.status_code == 401

    res_post = client.post("/myntra/verdict", json={"product_id": "123"})
    assert res_post.status_code == 401
