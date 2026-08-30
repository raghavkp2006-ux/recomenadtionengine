"""Deterministic, event-weighted Myntra taste profile construction."""
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from sqlalchemy.orm import Session
from models.myntra import MyntraEvent, MyntraProfile

EVENT_WEIGHTS = {"search": 1, "listing_view": 1, "product_view": 2, "product_click": 2, "long_product_view": 3, "wishlist_add": 7, "cart_add": 10, "purchase": 15, "wishlist_remove": -5, "cart_remove": -3}
DECAY_LAMBDA = 0.02
def _canonical(value): return str(value).strip().lower().replace("t-shirts", "tshirt").replace("t-shirts", "tshirt") if value else None
def rebuild_profile(db: Session, user_id: str) -> dict:
    buckets = {name: defaultdict(float) for name in ("brands", "categories", "subcategories", "colours", "styles", "fits", "materials", "preferred_sizes", "occasions")}
    prices, recent, positive, negative = [], [], [], []
    now = datetime.now(timezone.utc)
    for event in db.query(MyntraEvent).filter(MyntraEvent.user_id == user_id).order_by(MyntraEvent.occurred_at.desc()).all():
        product = json.loads(event.product_json) if event.product_json else {}
        age = max(0, (now - event.occurred_at.replace(tzinfo=event.occurred_at.tzinfo or timezone.utc)).total_seconds() / 86400)
        weight = EVENT_WEIGHTS.get(event.event_type, 1) * math.exp(-DECAY_LAMBDA * age)
        for target, field in (("brands", "brand"), ("categories", "category"), ("subcategories", "subcategory"), ("colours", "colour"), ("fits", "fit"), ("materials", "material"), ("occasions", "occasion"), ("styles", "pattern")):
            value = _canonical(product.get(field))
            if value: buckets[target][value] += weight
        for size in product.get("sizes") or []: buckets["preferred_sizes"][_canonical(size)] += weight
        if product.get("price") is not None and weight > 0: prices.append(product["price"])
        if product.get("product_id") and weight > 0: positive.append(product["product_id"])
        if product.get("product_id") and weight < 0: negative.append(product["product_id"])
        if product.get("product_id"): recent.append(product["product_id"])
    profile = {key: dict(sorted(values.items(), key=lambda item: (-item[1], item[0]))) for key, values in buckets.items()}
    profile.update({"price_range": {"min": min(prices) if prices else None, "median": median(prices) if prices else None, "max": max(prices) if prices else None}, "recent_interests": list(dict.fromkeys(recent))[:20], "strong_positive_signals": list(dict.fromkeys(positive))[:20], "negative_signals": list(dict.fromkeys(negative))[:20]})
    row = db.get(MyntraProfile, user_id)
    if row: row.profile_json = json.dumps(profile, ensure_ascii=False, sort_keys=True)
    else: db.add(MyntraProfile(user_id=user_id, profile_json=json.dumps(profile, ensure_ascii=False, sort_keys=True)))
    db.flush(); return profile
def get_profile(db: Session, user_id: str):
    row = db.get(MyntraProfile, user_id)
    return json.loads(row.profile_json) if row else rebuild_profile(db, user_id)
