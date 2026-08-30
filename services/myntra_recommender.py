"""Deterministic ranking of products already observed from user-visible pages."""
from models.myntra import MyntraProduct
from services.myntra_profile import get_profile
def recommendations(db, user_id, limit=20, category=None, min_price=None, max_price=None, brand=None):
    profile = get_profile(db, user_id); rows = db.query(MyntraProduct).all(); results = []
    for row in rows:
        if category and row.category != category or brand and row.brand != brand or min_price is not None and (row.price is None or row.price < min_price) or max_price is not None and (row.price is None or row.price > max_price): continue
        if row.product_id in profile["negative_signals"] or row.product_id in profile["strong_positive_signals"]: continue
        score = .30 * profile["categories"].get((row.category or "").lower(), 0) + .20 * profile["brands"].get((row.brand or "").lower(), 0) + .10 * profile["colours"].get((row.colour or "").lower(), 0)
        median = profile["price_range"]["median"]
        if median and row.price is not None: score += .10 * max(0, 1 - abs(row.price - median) / max(median, 1))
        results.append({"product_id": row.product_id, "product_url": row.product_url, "brand": row.brand, "title": row.title, "category": row.category, "price": row.price, "currency": row.currency, "image_url": row.image_url, "score": round(score, 6)})
    return sorted(results, key=lambda item: (-item["score"], item["product_id"]))[:limit]
