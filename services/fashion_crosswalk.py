"""Fashion crosswalk mapping cross-domain media genres to fashion attributes.

This mapping is a hypothesis under evaluation (Phase 2), not an established fact.
Maps media genres (from Spotify, Anime/AniList, and Movies) to fashion attributes
using only vocabulary present in the Myntra catalog and the user taste profile.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Only keys that actually exist in the merged genre vocabulary (Part 0 Item 5),
# and only values that exist in the Myntra catalog vocabulary (Part 0 Item 4).
FASHION_CROSSWALK: Dict[str, Dict[str, List[str]]] = {
    "action": {
        "colours": ["black", "red", "grey"],
        "patterns": ["solid", "graphic"],
        "occasions": ["casual", "daily"],
        "categories": ["shirts", "tops"],
    },
    "drama": {
        "colours": ["navy", "maroon", "black"],
        "patterns": ["solid", "striped"],
        "occasions": ["festive", "ethnic", "daily"],
        "categories": ["kurtas", "kurta sets", "shirts"],
    },
    "supernatural": {
        "colours": ["black", "purple", "maroon"],
        "patterns": ["abstract", "woven design"],
        "occasions": ["party", "casual"],
        "categories": ["kurtas", "tops", "dresses"],
    },
    "adventure": {
        "colours": ["khaki", "brown", "green"],
        "patterns": ["solid", "checked"],
        "occasions": ["casual", "daily"],
        "categories": ["shirts", "tops"],
    },
    "comedy": {
        "colours": ["yellow", "orange", "pink"],
        "patterns": ["printed", "quirky"],
        "occasions": ["casual", "daily"],
        "categories": ["tops", "dresses", "kurtis"],
    },
    "fantasy": {
        "colours": ["purple", "teal", "turquoise blue"],
        "patterns": ["ethnic motifs", "embroidered", "embellished"],
        "occasions": ["festive", "ethnic", "party"],
        "categories": ["lehenga choli", "kurta sets", "sarees"],
    },
    "psychological": {
        "colours": ["black", "grey", "white"],
        "patterns": ["abstract", "geometric", "solid"],
        "occasions": ["daily", "casual"],
        "categories": ["shirts", "tops"],
    },
    "romance": {
        "colours": ["pink", "coral", "lavender", "red"],
        "patterns": ["floral", "printed"],
        "occasions": ["party", "festive", "daily"],
        "categories": ["dresses", "kurtis", "lehenga choli"],
    },
    "mystery": {
        "colours": ["black", "navy", "dark grey"],
        "patterns": ["solid", "textured"],
        "occasions": ["daily", "party"],
        "categories": ["nehru jackets", "shirts"],
    },
    "sci-fi": {
        "colours": ["black", "grey", "blue"],
        "patterns": ["geometric", "abstract", "colourblocked"],
        "occasions": ["casual", "party"],
        "categories": ["tops", "shirts"],
    },
    "slice of life": {
        "colours": ["white", "beige", "blue", "sea green"],
        "patterns": ["solid", "striped", "printed"],
        "occasions": ["daily", "casual"],
        "categories": ["kurtas", "kurtis", "shirts", "tops"],
    },
    "thriller": {
        "colours": ["black", "maroon", "red"],
        "patterns": ["solid", "abstract"],
        "occasions": ["party", "casual"],
        "categories": ["nehru jackets", "shirts", "tops"],
    },
    "horror": {
        "colours": ["black", "red", "grey"],
        "patterns": ["solid", "graphic"],
        "occasions": ["casual"],
        "categories": ["tops", "shirts"],
    },
    "ecchi": {
        "colours": ["pink", "magenta", "red"],
        "patterns": ["printed", "floral"],
        "occasions": ["party", "casual"],
        "categories": ["dresses", "tops"],
    },
    "mecha": {
        "colours": ["grey", "blue", "black"],
        "patterns": ["geometric", "colourblocked"],
        "occasions": ["casual", "daily"],
        "categories": ["tops", "shirts"],
    },
    "sports": {
        "colours": ["blue", "white", "red"],
        "patterns": ["solid", "colourblocked", "striped"],
        "occasions": ["casual", "daily"],
        "categories": ["tops", "shirts"],
    },
    "music": {
        "colours": ["black", "purple", "blue"],
        "patterns": ["graphic", "abstract", "printed"],
        "occasions": ["party", "casual"],
        "categories": ["tops", "shirts"],
    },
}


def _canonical(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip().lower()
    return s if s else None


def _get_best_domain_for_genre(genre: str, breakdown: Dict[str, Any]) -> str:
    """Find the breakdown source (spotify, anime, anilist, movie) with the highest weight for a genre."""
    best_domain = "anilist"
    best_weight = -1.0
    for domain in ("spotify", "anime", "anilist", "movie", "movies"):
        source_data = breakdown.get(domain)
        if isinstance(source_data, dict):
            w = source_data.get(genre, 0.0)
            if isinstance(w, (int, float)) and w > best_weight:
                best_weight = float(w)
                best_domain = "movies" if domain == "movie" else domain
    return best_domain


def crosswalk_affinity(
    product: Dict[str, Any],
    taste: Dict[str, Any],
) -> Tuple[Optional[float], List[Dict[str, Any]]]:
    """Calculate crosswalk affinity score between product and user taste profile.

    taste is the compute_taste_profile result.
    Score = sum(genre_weight * match(product, mapping[genre])) / sum(genre_weight), in [0, 1].
    Returns (None, []) when no media signals exist in taste.
    Evidence list contains elements with:
    {"domain": str, "genre": str, "attribute": str, "value": str, "weight": float}
    """
    if not isinstance(taste, dict):
        return None, []

    profile_genres = taste.get("profile")
    if not isinstance(profile_genres, dict) or not profile_genres:
        return None, []

    breakdown = taste.get("breakdown") if isinstance(taste.get("breakdown"), dict) else {}

    # Check whether any non-Myntra media signal is non-empty
    has_media_signal = False
    for src in ("spotify", "anime", "anilist", "movie", "movies"):
        b_src = breakdown.get(src)
        if isinstance(b_src, dict) and len(b_src) > 0:
            has_media_signal = True
            break
    if not has_media_signal:
        return None, []

    prod_colour = _canonical(product.get("colour"))
    prod_pattern = _canonical(product.get("pattern"))
    prod_occasion = _canonical(product.get("occasion"))
    prod_category = _canonical(product.get("category"))

    total_weighted_match = 0.0
    total_genre_weights = 0.0
    evidence: List[Dict[str, Any]] = []

    for genre, genre_weight in profile_genres.items():
        if not isinstance(genre_weight, (int, float)) or genre_weight <= 0:
            continue

        genre_key = _canonical(genre)
        if not genre_key or genre_key not in FASHION_CROSSWALK:
            continue

        mapping = FASHION_CROSSWALK[genre_key]
        total_genre_weights += float(genre_weight)

        matched_dims = 0
        total_dims = len(mapping) if mapping else 1
        domain = _get_best_domain_for_genre(genre, breakdown)

        # Check colour
        if prod_colour and prod_colour in [_canonical(c) for c in mapping.get("colours", [])]:
            matched_dims += 1
            evidence.append({
                "domain": domain,
                "genre": genre,
                "attribute": "colour",
                "value": product.get("colour"),
                "weight": float(genre_weight),
            })

        # Check pattern / style
        if prod_pattern and prod_pattern in [_canonical(p) for p in mapping.get("patterns", [])]:
            matched_dims += 1
            evidence.append({
                "domain": domain,
                "genre": genre,
                "attribute": "pattern",
                "value": product.get("pattern"),
                "weight": float(genre_weight),
            })

        # Check occasion
        if prod_occasion and prod_occasion in [_canonical(o) for o in mapping.get("occasions", [])]:
            matched_dims += 1
            evidence.append({
                "domain": domain,
                "genre": genre,
                "attribute": "occasion",
                "value": product.get("occasion"),
                "weight": float(genre_weight),
            })

        # Check category
        if prod_category and prod_category in [_canonical(cat) for cat in mapping.get("categories", [])]:
            matched_dims += 1
            evidence.append({
                "domain": domain,
                "genre": genre,
                "attribute": "category",
                "value": product.get("category"),
                "weight": float(genre_weight),
            })

        if matched_dims > 0:
            dim_match_score = matched_dims / total_dims
            total_weighted_match += float(genre_weight) * dim_match_score

    if total_genre_weights <= 0:
        return None, []

    score = min(1.0, max(0.0, total_weighted_match / total_genre_weights))
    return score, evidence
