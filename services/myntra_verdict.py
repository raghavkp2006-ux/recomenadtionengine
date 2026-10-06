"""Deterministic fashion verdict scoring engine.

Computes Buy / Consider / Skip verdicts for fashion products based on direct
browsing history (TF-IDF cosine similarity), cross-domain taste crosswalk (Spotify / AniList / Movies),
log-normal price fit, and diversity redundancy penalties.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.myntra import MyntraEvent, MyntraFeedback, MyntraProduct
from services.fashion_crosswalk import crosswalk_affinity
from services.myntra_profile import DECAY_LAMBDA, EVENT_WEIGHTS, get_profile

# ---------------------------------------------------------------------------
# Fixed constants a priori — do NOT tune against evaluation
# ---------------------------------------------------------------------------
W_DIRECT: float = 0.5
W_CROSS: float = 0.3
W_PRICE: float = 0.2
W_REDUNDANCY: float = 0.25

BUY_PCT: float = 80.0
SKIP_PCT: float = 40.0
MIN_BUY_FIT: float = 0.25
REDUNDANCY_FLOOR: float = 0.6

FEEDBACK_WEIGHTS: Dict[str, float] = {
    "like": 7.0,
    "purchased": 15.0,
    "clicked": 2.0,
    "dislike": -5.0,
    "not_interested": -7.0,
}

KIDS_GENDERS: Set[str] = {"boys", "girls", "kid", "kids", "infant", "infants", "baby", "babies"}


def _canonical(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip().lower()
    return s if s else None


def _is_kids_item(product: Dict[str, Any] | MyntraProduct) -> bool:
    """Check if item belongs to kids/infants/boys/girls categories."""
    if isinstance(product, MyntraProduct):
        gender = product.gender
        cat = product.category
        subcat = product.subcategory
    else:
        gender = product.get("gender")
        cat = product.get("category")
        subcat = product.get("subcategory")

    for field in (gender, cat, subcat):
        canon = _canonical(field)
        if canon:
            for k in KIDS_GENDERS:
                if k in canon:
                    return True
    return False


def _product_text(p: Dict[str, Any] | MyntraProduct) -> str:
    """Create normalized text representation of product for TF-IDF."""
    if isinstance(p, MyntraProduct):
        fields = [
            p.brand,
            p.title,
            p.category,
            p.subcategory,
            p.colour,
            p.pattern,
            p.fit,
            p.material,
            p.occasion,
        ]
    else:
        fields = [
            p.get("brand"),
            p.get("title"),
            p.get("category"),
            p.get("subcategory"),
            p.get("colour"),
            p.get("pattern"),
            p.get("fit"),
            p.get("material"),
            p.get("occasion"),
        ]
    tokens = [str(f).strip().lower() for f in fields if f is not None and str(f).strip()]
    return " ".join(tokens) if tokens else "fashion item"


def _dict_from_product(p: MyntraProduct | Dict[str, Any]) -> Dict[str, Any]:
    """Ensure product is represented as a dictionary."""
    if isinstance(p, MyntraProduct):
        return {
            "product_id": str(p.product_id),
            "product_url": p.product_url or "",
            "brand": p.brand or "",
            "title": p.title or "",
            "category": p.category or "",
            "subcategory": p.subcategory or "",
            "gender": p.gender or "",
            "price": float(p.price) if p.price is not None else 0.0,
            "currency": p.currency or "INR",
            "image_url": p.image_url or "",
            "colour": p.colour or "",
            "pattern": p.pattern or "",
            "fit": p.fit or "",
            "material": p.material or "",
            "occasion": p.occasion or "",
        }
    return {
        "product_id": str(p.get("product_id") or ""),
        "product_url": p.get("product_url") or "",
        "brand": p.get("brand") or "",
        "title": p.get("title") or "",
        "category": p.get("category") or "",
        "subcategory": p.get("subcategory") or "",
        "gender": p.get("gender") or "",
        "price": float(p.get("price") or 0.0) if p.get("price") is not None else 0.0,
        "currency": p.get("currency") or "INR",
        "image_url": p.get("image_url") or "",
        "colour": p.get("colour") or "",
        "pattern": p.get("pattern") or "",
        "fit": p.get("fit") or "",
        "material": p.get("material") or "",
        "occasion": p.get("occasion") or "",
    }


def _price_fit(price: Optional[float], median_price: Optional[float]) -> Optional[float]:
    """Calculate price fit component using log-normal formula."""
    if price is None or price <= 0 or median_price is None or median_price <= 0:
        return None
    ln_ratio = math.log(price / median_price)
    return float(math.exp(-(ln_ratio ** 2) / (2.0 * (0.5 ** 2))))


def _build_price_note(price: Optional[float], median_price: Optional[float]) -> str:
    """Format human-readable price note."""
    if median_price is not None and median_price > 0 and price is not None and price > 0:
        return f"₹{int(price):,} vs your median ₹{int(median_price):,}"
    return "No price history yet"


def _infer_gender(db: Session, user_id: str) -> str:
    """Infer gender filter from majority gender of user's engaged products, or 'all'."""
    events = (
        db.query(MyntraEvent)
        .filter(MyntraEvent.user_id == user_id, MyntraEvent.product_id.isnot(None))
        .all()
    )
    genders: List[str] = []
    for ev in events:
        if ev.product_json:
            try:
                pj = json.loads(ev.product_json)
                g = _canonical(pj.get("gender"))
                if g and not any(k in g for k in KIDS_GENDERS):
                    genders.append(g)
            except Exception:
                pass
    if not genders:
        return "all"

    men_count = sum(1 for g in genders if "men" in g and "women" not in g)
    women_count = sum(1 for g in genders if "women" in g)

    if men_count > women_count and men_count > 0:
        return "men"
    elif women_count > men_count and women_count > 0:
        return "women"
    return "all"


def _load_candidate_pool(
    db: Session,
    user_id: str,
    gender_filter: str,
    extra_product: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Load deduplicated catalog items, excluding kids and applying gender filtering."""
    rows = db.query(MyntraProduct).all()
    seen_ids: Set[str] = set()
    pool: List[Dict[str, Any]] = []

    for r in rows:
        if r.product_id in seen_ids:
            continue
        if _is_kids_item(r):
            continue

        p_gender = _canonical(r.gender)
        if gender_filter == "men":
            if p_gender and ("women" in p_gender or (p_gender not in ("men", "unisex") and "men" not in p_gender)):
                continue
        elif gender_filter == "women":
            if p_gender and ("men" in p_gender and "women" not in p_gender):
                continue

        seen_ids.add(r.product_id)
        pool.append(_dict_from_product(r))

    if extra_product:
        pid = extra_product.get("product_id")
        if pid and pid not in seen_ids and not _is_kids_item(extra_product):
            pool.append(_dict_from_product(extra_product))

    return pool


def _compute_fit(
    direct: Optional[float],
    crosswalk: Optional[float],
    price_fit_val: Optional[float],
    redundancy: float,
) -> Optional[float]:
    """Compute overall fit score combining available components."""
    available = []
    if direct is not None:
        available.append((direct, W_DIRECT))
    if crosswalk is not None:
        available.append((crosswalk, W_CROSS))
    if price_fit_val is not None:
        available.append((price_fit_val, W_PRICE))

    if not available:
        return None

    w_sum = sum(w for _, w in available)
    if w_sum <= 0:
        return None

    base_fit = sum(comp * w for comp, w in available) / w_sum
    fit = base_fit - (W_REDUNDANCY * redundancy)
    return float(max(0.0, min(1.0, fit)))


def _determine_verdict(fit: Optional[float], percentile: float) -> Optional[str]:
    """Assign BUY / CONSIDER / SKIP verdict."""
    if fit is None:
        return None
    if percentile >= BUY_PCT and fit >= MIN_BUY_FIT:
        return "BUY"
    elif percentile < SKIP_PCT:
        return "SKIP"
    return "CONSIDER"


def _build_reasons(
    product: Dict[str, Any],
    direct_score: Optional[float],
    cross_evidence: List[Dict[str, Any]],
    price_score: Optional[float],
    price_note: str,
    profile: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build grounded, human-readable reasons (max 3) ordered by signal contribution."""
    candidates: List[Tuple[float, Dict[str, Any]]] = []

    # 1. Direct reasons from Myntra profile matching
    if direct_score is not None and direct_score > 0:
        matched_attr = None
        max_attr_weight = 0.0
        attr_label = ""
        attr_val = ""

        # Check category match in profile
        prod_cat = _canonical(product.get("category"))
        categories = profile.get("categories", {})
        if prod_cat and prod_cat in categories:
            w = float(categories[prod_cat])
            if w > max_attr_weight:
                max_attr_weight = w
                matched_attr = "category"
                attr_label = f"You browse {product.get('category')} often"
                attr_val = product.get("category")

        # Check brand match in profile
        prod_brand = _canonical(product.get("brand"))
        brands = profile.get("brands", {})
        if prod_brand and prod_brand in brands:
            w = float(brands[prod_brand])
            if w > max_attr_weight:
                max_attr_weight = w
                matched_attr = "brand"
                attr_label = f"{product.get('brand')} is in your top brands"
                attr_val = product.get("brand")

        # Check colour match in profile
        prod_colour = _canonical(product.get("colour"))
        colours = profile.get("colours", {})
        if prod_colour and prod_colour in colours:
            w = float(colours[prod_colour])
            if w > max_attr_weight:
                max_attr_weight = w
                matched_attr = "colour"
                attr_label = f"You frequently select {product.get('colour')} items"
                attr_val = product.get("colour")

        if matched_attr:
            candidates.append((
                direct_score * W_DIRECT,
                {
                    "domain": "myntra",
                    "text": attr_label,
                    "evidence": {
                        "attribute": matched_attr,
                        "value": attr_val,
                        "profile_weight": max_attr_weight,
                    },
                },
            ))
        else:
            candidates.append((
                direct_score * W_DIRECT,
                {
                    "domain": "myntra",
                    "text": "Matches your browsing profile keywords",
                    "evidence": {"direct_similarity": round(direct_score, 3)},
                },
            ))

    # 2. Crosswalk reasons from cross-domain taste evidence
    if cross_evidence:
        # Group crosswalk evidence by genre / domain
        sorted_ev = sorted(cross_evidence, key=lambda x: x.get("weight", 0.0), reverse=True)
        seen_domains = set()
        for ev in sorted_ev[:2]:
            domain = ev.get("domain", "anilist")
            genre = ev.get("genre", "")
            attr = ev.get("attribute", "")
            val = ev.get("value", "")
            w = ev.get("weight", 1.0)
            text = f"Matches your {genre} taste ({val} {attr})"
            candidates.append((
                w * W_CROSS,
                {
                    "domain": domain,
                    "text": text,
                    "evidence": ev,
                },
            ))

    # 3. Price fit note if strongly aligned
    if price_score is not None and price_score > 0.85 and "vs your median" in price_note:
        candidates.append((
            price_score * W_PRICE,
            {
                "domain": "myntra",
                "text": f"Aligned with your spend: {price_note}",
                "evidence": {"price_fit": round(price_score, 3)},
            },
        ))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [c[1] for c in candidates[:3]]


def score_feed(
    db: Session,
    user_id: str,
    taste: Dict[str, Any],
    gender: Optional[str] = None,
    limit: int = 60,
) -> Dict[str, Any]:
    """Score the candidate catalog pool for a user and return the verdict feed."""
    now = datetime.now(timezone.utc)

    # 1. Events and feedback retrieval
    events = (
        db.query(MyntraEvent)
        .filter(MyntraEvent.user_id == user_id)
        .order_by(MyntraEvent.occurred_at.desc())
        .all()
    )
    feedback_rows = (
        db.query(MyntraFeedback)
        .filter(MyntraFeedback.user_id == user_id)
        .all()
    )

    last_event_at = (
        max((ev.occurred_at for ev in events), default=None)
    )
    last_event_str = (
        last_event_at.replace(tzinfo=timezone.utc).isoformat()
        if last_event_at is not None
        else None
    )

    # Engaged product IDs & exclusions
    excluded_product_ids: Set[str] = set()
    engaged_product_texts: List[str] = []
    engaged_product_ids: Set[str] = set()

    for ev in events:
        pid = ev.product_id
        if not pid:
            continue
        if ev.event_type in ("wishlist_add", "cart_add", "purchase"):
            excluded_product_ids.add(pid)
        if ev.product_json:
            try:
                pj = json.loads(ev.product_json)
                engaged_product_texts.append(_product_text(pj))
                engaged_product_ids.add(pid)
            except Exception:
                pass

    for fb in feedback_rows:
        pid = fb.product_id
        if fb.feedback in ("dislike", "not_interested", "purchased"):
            excluded_product_ids.add(pid)
        if fb.feedback in ("like", "clicked", "purchased"):
            engaged_product_ids.add(pid)

    # Profile & price range
    profile = get_profile(db, user_id)
    median_price = (
        profile.get("price_range", {}).get("median")
        if isinstance(profile.get("price_range"), dict)
        else None
    )

    # Signal status
    breakdown = taste.get("breakdown") if isinstance(taste.get("breakdown"), dict) else {}
    signals = {
        "myntra": len(events) > 0,
        "spotify": bool(breakdown.get("spotify")),
        "anilist": bool(breakdown.get("anilist")),
        "movies": bool(breakdown.get("movie") or breakdown.get("movies")),
    }

    # Gender filter
    effective_gender = (gender or "").lower().strip() or _infer_gender(db, user_id)
    if effective_gender not in ("men", "women", "all"):
        effective_gender = "all"

    # Candidate pool
    candidate_pool = _load_candidate_pool(db, user_id, effective_gender)

    # Cold start check: if no events and no media signals
    is_cold_start = not signals["myntra"] and not any(
        signals[k] for k in ("spotify", "anilist", "movies")
    )

    confidence = "low"
    if len(engaged_product_ids) >= 20:
        confidence = "high"
    elif len(engaged_product_ids) >= 5:
        confidence = "medium"

    summary = {
        "events": len(events),
        "last_event_at": last_event_str,
        "signals": signals,
        "confidence": confidence,
        "price_range": profile.get("price_range", {"min": None, "median": None, "max": None}),
        "top_colours": list(profile.get("colours", {}).keys())[:5],
        "top_categories": list(profile.get("categories", {}).keys())[:5],
        "gender_filter": effective_gender,
    }

    if is_cold_start or not candidate_pool:
        return {
            "summary": summary,
            "counts": {"buy": 0, "consider": 0, "skip": 0},
            "items": [],
        }

    # TF-IDF Vectorization over pool + engaged
    pool_texts = [_product_text(p) for p in candidate_pool]
    corpus = pool_texts + engaged_product_texts
    vectorizer = TfidfVectorizer(lowercase=True, stop_words="english", min_df=1)
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
        pool_vectors = tfidf_matrix[:len(pool_texts)]
    except Exception:
        pool_vectors = None

    # Compute User Vector
    user_vector = None
    if pool_vectors is not None and (len(events) > 0 or len(feedback_rows) > 0):
        acc_vec = np.zeros((1, tfidf_matrix.shape[1]), dtype=np.float32)
        has_positive = False

        for ev in events:
            if not ev.product_json:
                continue
            try:
                pj = json.loads(ev.product_json)
                ptxt = _product_text(pj)
                pvec = vectorizer.transform([ptxt]).toarray()
                age = max(
                    0.0,
                    (now - ev.occurred_at.replace(tzinfo=ev.occurred_at.tzinfo or timezone.utc)).total_seconds()
                    / 86400.0,
                )
                w = EVENT_WEIGHTS.get(ev.event_type, 1) * math.exp(-DECAY_LAMBDA * age)
                acc_vec += w * pvec
                if w > 0:
                    has_positive = True
            except Exception:
                pass

        for fb in feedback_rows:
            fb_w = FEEDBACK_WEIGHTS.get(fb.feedback, 0.0)
            if fb_w == 0.0:
                continue
            cat_match = next((p for p in candidate_pool if p["product_id"] == fb.product_id), None)
            if cat_match:
                pvec = vectorizer.transform([_product_text(cat_match)]).toarray()
                age = max(
                    0.0,
                    (now - fb.created_at.replace(tzinfo=fb.created_at.tzinfo or timezone.utc)).total_seconds()
                    / 86400.0,
                )
                acc_vec += fb_w * math.exp(-DECAY_LAMBDA * age) * pvec
                if fb_w > 0:
                    has_positive = True

        norm = np.linalg.norm(acc_vec)
        if norm > 1e-9 and has_positive:
            user_vector = acc_vec / norm

    # Engaged vectors for redundancy calculation
    engaged_vecs = None
    if vectorizer is not None and engaged_product_texts:
        try:
            engaged_vecs = vectorizer.transform(engaged_product_texts)
        except Exception:
            engaged_vecs = None

    # Pre-score all pool items to compute percentile distribution
    pool_fit_scores: List[float] = []
    pool_item_data: List[Dict[str, Any]] = []

    for idx, product in enumerate(candidate_pool):
        # 1. Direct component
        direct_comp: Optional[float] = None
        if user_vector is not None and pool_vectors is not None:
            p_vec = pool_vectors[idx]
            sim = float(cosine_similarity(user_vector, p_vec)[0, 0])
            direct_comp = max(0.0, min(1.0, sim))

        # 2. Crosswalk component
        cross_comp, cross_ev = crosswalk_affinity(product, taste)

        # 3. Price fit
        price_val = product.get("price")
        p_fit = _price_fit(price_val, median_price)
        price_note = _build_price_note(price_val, median_price)

        # 4. Redundancy
        redundancy = 0.0
        if engaged_vecs is not None and engaged_vecs.shape[0] > 0 and pool_vectors is not None:
            cosines = cosine_similarity(pool_vectors[idx], engaged_vecs)[0]
            max_cos = float(np.max(cosines)) if len(cosines) > 0 else 0.0
            redundancy = max(0.0, (max_cos - REDUNDANCY_FLOOR) / (1.0 - REDUNDANCY_FLOOR))

        fit = _compute_fit(direct_comp, cross_comp, p_fit, redundancy)

        if fit is not None:
            pool_fit_scores.append(fit)

        pool_item_data.append({
            "product": product,
            "direct": direct_comp,
            "crosswalk": cross_comp,
            "price": p_fit,
            "redundancy": redundancy,
            "fit": fit,
            "cross_evidence": cross_ev,
            "price_note": price_note,
        })

    if not pool_fit_scores:
        return {
            "summary": summary,
            "counts": {"buy": 0, "consider": 0, "skip": 0},
            "items": [],
        }

    pool_fits_arr = np.array(pool_fit_scores)

    # Classify items and assemble output list
    items: List[Dict[str, Any]] = []
    buy_count = 0
    consider_count = 0
    skip_count = 0

    for data in pool_item_data:
        p = data["product"]
        pid = p["product_id"]

        # Feed excludes purchased/wishlist/cart products and negative feedback
        if pid in excluded_product_ids:
            continue

        fit = data["fit"]
        if fit is None:
            continue

        # Percentile rank within candidate pool
        pct = float(np.mean(pool_fits_arr <= fit) * 100.0)
        verdict = _determine_verdict(fit, pct)

        if verdict == "BUY":
            buy_count += 1
        elif verdict == "SKIP":
            skip_count += 1
        elif verdict == "CONSIDER":
            consider_count += 1

        reasons = _build_reasons(
            p,
            data["direct"],
            data["cross_evidence"],
            data["price"],
            data["price_note"],
            profile,
        )

        items.append({
            "product_id": pid,
            "product_url": p.get("product_url", ""),
            "brand": p.get("brand", ""),
            "title": p.get("title", ""),
            "category": p.get("category", ""),
            "price": p.get("price", 0.0),
            "currency": p.get("currency", "INR"),
            "image_url": p.get("image_url", ""),
            "verdict": verdict,
            "fit": round(fit, 4),
            "components": {
                "direct": round(data["direct"], 4) if data["direct"] is not None else 0.0,
                "crosswalk": round(data["crosswalk"], 4) if data["crosswalk"] is not None else 0.0,
                "price": round(data["price"], 4) if data["price"] is not None else 0.0,
                "redundancy": round(data["redundancy"], 4),
            },
            "reasons": reasons,
            "price_note": data["price_note"],
        })

    # Sort by fit desc, then product_id
    items.sort(key=lambda x: (-x["fit"], x["product_id"]))

    return {
        "summary": summary,
        "counts": {"buy": buy_count, "consider": consider_count, "skip": skip_count},
        "items": items[:limit],
    }


def score_single(
    db: Session,
    user_id: str,
    taste: Dict[str, Any],
    product: Dict[str, Any],
) -> Dict[str, Any]:
    """Score a single product against user preferences and return verdict and status."""
    now = datetime.now(timezone.utc)
    pid = product.get("product_id")

    # Check for existing wishlist/cart/purchase events
    if pid:
        recent_event = (
            db.query(MyntraEvent)
            .filter(
                MyntraEvent.user_id == user_id,
                MyntraEvent.product_id == pid,
                MyntraEvent.event_type.in_(("wishlist_add", "cart_add", "purchase")),
            )
            .order_by(MyntraEvent.occurred_at.desc())
            .first()
        )
        if recent_event:
            status_map = {
                "wishlist_add": "in_wishlist",
                "cart_add": "in_cart",
                "purchase": "purchased",
            }
            return {
                "status": status_map.get(recent_event.event_type, "already_interacted"),
                "product_id": pid,
                "verdict": None,
                "fit": None,
                "components": None,
                "reasons": [],
                "price_note": "",
            }

    # Retrieve profile
    profile = get_profile(db, user_id)
    median_price = (
        profile.get("price_range", {}).get("median")
        if isinstance(profile.get("price_range"), dict)
        else None
    )

    # Load candidate pool for percentile distribution
    effective_gender = _infer_gender(db, user_id)
    candidate_pool = _load_candidate_pool(db, user_id, effective_gender, extra_product=product)

    # Events and feedback
    events = db.query(MyntraEvent).filter(MyntraEvent.user_id == user_id).all()
    feedback_rows = db.query(MyntraFeedback).filter(MyntraFeedback.user_id == user_id).all()

    engaged_product_texts = []
    for ev in events:
        if ev.product_json:
            try:
                engaged_product_texts.append(_product_text(json.loads(ev.product_json)))
            except Exception:
                pass

    # TF-IDF Vectorizer
    pool_texts = [_product_text(p) for p in candidate_pool]
    vectorizer = TfidfVectorizer(lowercase=True, stop_words="english", min_df=1)
    tfidf_matrix = vectorizer.fit_transform(pool_texts + engaged_product_texts)
    pool_vectors = tfidf_matrix[:len(pool_texts)]

    # User Vector
    user_vector = None
    if len(events) > 0 or len(feedback_rows) > 0:
        acc_vec = np.zeros((1, tfidf_matrix.shape[1]), dtype=np.float32)
        has_positive = False

        for ev in events:
            if not ev.product_json:
                continue
            try:
                pj = json.loads(ev.product_json)
                ptxt = _product_text(pj)
                pvec = vectorizer.transform([ptxt]).toarray()
                age = max(
                    0.0,
                    (now - ev.occurred_at.replace(tzinfo=ev.occurred_at.tzinfo or timezone.utc)).total_seconds()
                    / 86400.0,
                )
                w = EVENT_WEIGHTS.get(ev.event_type, 1) * math.exp(-DECAY_LAMBDA * age)
                acc_vec += w * pvec
                if w > 0:
                    has_positive = True
            except Exception:
                pass

        for fb in feedback_rows:
            fb_w = FEEDBACK_WEIGHTS.get(fb.feedback, 0.0)
            if fb_w == 0.0:
                continue
            cat_match = next((p for p in candidate_pool if p["product_id"] == fb.product_id), None)
            if cat_match:
                pvec = vectorizer.transform([_product_text(cat_match)]).toarray()
                age = max(
                    0.0,
                    (now - fb.created_at.replace(tzinfo=fb.created_at.tzinfo or timezone.utc)).total_seconds()
                    / 86400.0,
                )
                acc_vec += fb_w * math.exp(-DECAY_LAMBDA * age) * pvec
                if fb_w > 0:
                    has_positive = True

        norm = np.linalg.norm(acc_vec)
        if norm > 1e-9 and has_positive:
            user_vector = acc_vec / norm

    engaged_vecs = vectorizer.transform(engaged_product_texts) if engaged_product_texts else None

    # Calculate scores across pool
    pool_fits: List[float] = []
    target_data = None

    for idx, cp in enumerate(candidate_pool):
        direct_comp = None
        if user_vector is not None:
            sim = float(cosine_similarity(user_vector, pool_vectors[idx])[0, 0])
            direct_comp = max(0.0, min(1.0, sim))

        cross_comp, cross_ev = crosswalk_affinity(cp, taste)
        p_fit = _price_fit(cp.get("price"), median_price)

        redundancy = 0.0
        if engaged_vecs is not None and engaged_vecs.shape[0] > 0:
            cosines = cosine_similarity(pool_vectors[idx], engaged_vecs)[0]
            max_cos = float(np.max(cosines)) if len(cosines) > 0 else 0.0
            redundancy = max(0.0, (max_cos - REDUNDANCY_FLOOR) / (1.0 - REDUNDANCY_FLOOR))

        fit = _compute_fit(direct_comp, cross_comp, p_fit, redundancy)
        if fit is not None:
            pool_fits.append(fit)

        if cp.get("product_id") == pid:
            target_data = {
                "product": cp,
                "direct": direct_comp,
                "crosswalk": cross_comp,
                "price": p_fit,
                "redundancy": redundancy,
                "fit": fit,
                "cross_evidence": cross_ev,
                "price_note": _build_price_note(cp.get("price"), median_price),
            }

    # Confidence based on engaged products
    engaged_pids = {ev.product_id for ev in events if ev.product_id}
    confidence = "low"
    if len(engaged_pids) >= 20:
        confidence = "high"
    elif len(engaged_pids) >= 5:
        confidence = "medium"

    if not target_data or target_data["fit"] is None or not pool_fits:
        return {
            "status": "evaluated",
            "product_id": pid or "",
            "verdict": None,
            "fit": None,
            "confidence": confidence,
            "components": None,
            "reasons": [],
            "price_note": _build_price_note(product.get("price"), median_price),
        }

    pct = float(np.mean(np.array(pool_fits) <= target_data["fit"]) * 100.0)
    verdict = _determine_verdict(target_data["fit"], pct)

    reasons = _build_reasons(
        target_data["product"],
        target_data["direct"],
        target_data["cross_evidence"],
        target_data["price"],
        target_data["price_note"],
        profile,
    )

    return {
        "status": "evaluated",
        "product_id": pid or "",
        "product_url": product.get("product_url", ""),
        "brand": product.get("brand", ""),
        "title": product.get("title", ""),
        "category": product.get("category", ""),
        "price": product.get("price", 0.0),
        "currency": product.get("currency", "INR"),
        "image_url": product.get("image_url", ""),
        "verdict": verdict,
        "fit": round(target_data["fit"], 4),
        "confidence": confidence,
        "components": {
            "direct": round(target_data["direct"], 4) if target_data["direct"] is not None else 0.0,
            "crosswalk": round(target_data["crosswalk"], 4) if target_data["crosswalk"] is not None else 0.0,
            "price": round(target_data["price"], 4) if target_data["price"] is not None else 0.0,
            "redundancy": round(target_data["redundancy"], 4),
        },
        "reasons": reasons,
        "price_note": target_data["price_note"],
    }
