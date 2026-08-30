"""Grounded shopping-assistant helpers; explanations only use ranked candidates."""
from services.myntra_profile import get_profile
from services.myntra_recommender import recommendations

def get_myntra_profile(db, user_id): return get_profile(db, user_id)
def get_recent_myntra_history(db, user_id): return get_profile(db, user_id).get("recent_interests", [])
def search_candidates(db, user_id, **filters): return recommendations(db, user_id, **filters)
def get_product_details(candidates, product_id): return next((item for item in candidates if item["product_id"] == product_id), None)
def rank_candidates(db, user_id, **filters): return recommendations(db, user_id, **filters)
def recommend_outfit(db, user_id, *, limit=3, category=None, max_price=None, brand=None):
    profile = get_profile(db, user_id)
    candidates = recommendations(db, user_id, limit, category, None, max_price, brand)
    reasons = []
    if category and profile["categories"].get(category.lower()): reasons.append(f"matches your {category} interest")
    if profile["price_range"]["median"] is not None: reasons.append("fits your observed price range")
    return {"candidates": candidates, "explanation": "; ".join(reasons) or "ranked from products you have already viewed"}
def record_feedback(db, user_id, product_id, feedback):
    from models.myntra import MyntraFeedback
    row = MyntraFeedback(user_id=user_id, product_id=product_id, feedback=feedback); db.add(row); db.flush(); return row
