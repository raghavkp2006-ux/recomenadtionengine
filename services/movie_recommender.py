"""
services/movie_recommender.py — Movie recommendation engine using TF-IDF & Cosine Similarity.

Loads precomputed TF-IDF artifacts and provides:
1. get_similar_movies(movie_id, n): Content-based recommendations similar to a seed movie.
2. get_taste_vector_recommendations(liked_ids, n): Multi-item personalized recommendations
   averaged from liked movies or auto-seeded from personal ratings (>= 7.0 weighted by rating - 5.5).
"""

import os
import pickle
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Global State & Artifact Loading
# ---------------------------------------------------------------------------

_data_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "processed",
)
_matrix_pkl_path = os.path.join(_data_dir, "movie_tfidf_matrix.pkl")
_vec_pkl_path = os.path.join(_data_dir, "movie_tfidf_vectorizer.pkl")

movie_data_map: Dict[str, Dict[str, Any]] = {}
movie_id_to_idx: Dict[str, int] = {}
movie_ids: List[str] = []
tfidf_matrix: Optional[np.ndarray] = None
vectorizer = None

if os.path.exists(_matrix_pkl_path):
    with open(_matrix_pkl_path, "rb") as f:
        _mat_data = pickle.load(f)
        tfidf_matrix = _mat_data["matrix"]
        movie_ids = _mat_data["ids"]
        movie_data_map = _mat_data.get("metadata", {})

    for idx, mid in enumerate(movie_ids):
        movie_id_to_idx[mid] = idx
        # Also index by SQLite PK if present in metadata
        if mid in movie_data_map and "id" in movie_data_map[mid]:
            movie_id_to_idx[str(movie_data_map[mid]["id"])] = idx

if os.path.exists(_vec_pkl_path):
    with open(_vec_pkl_path, "rb") as f:
        vectorizer = pickle.load(f)


def _resolve_movie_index(movie_id: Any) -> Optional[int]:
    """Resolve a movie ID (tmdb_id or database id) to matrix row index."""
    str_id = str(movie_id)
    return movie_id_to_idx.get(str_id)


def get_similar_movies(movie_id: Any, n: int = 5) -> List[Dict[str, Any]]:
    """
    Compute cosine similarity between a seed movie and all other movies in the catalog.
    Returns top-N most similar movies matching the shared recommendation contract.
    """
    if tfidf_matrix is None or not movie_ids:
        return []

    idx = _resolve_movie_index(movie_id)
    if idx is None:
        return []

    seed_vec = tfidf_matrix[idx : idx + 1]  # shape (1, features)
    seed_tmdb_id = movie_ids[idx]

    # Cosine similarity
    norms = np.linalg.norm(tfidf_matrix, axis=1, keepdims=True) * np.linalg.norm(seed_vec)
    similarities = (np.dot(tfidf_matrix, seed_vec.T) / np.maximum(norms, 1e-6)).flatten()

    # Sort descending
    top_indices = np.argsort(-similarities)

    recommendations: List[Dict[str, Any]] = []
    for cand_idx in top_indices:
        cand_idx = int(cand_idx)
        cand_id = movie_ids[cand_idx]
        if cand_id == seed_tmdb_id:
            continue

        score = float(similarities[cand_idx])
        meta = movie_data_map.get(cand_id, {})

        recommendations.append({
            "id": cand_id,
            "title": meta.get("title", "Unknown"),
            "imageUrl": meta.get("poster_url") or "",
            "reason": "Similar themes and genres",
            "score": round(score, 4),
            "similarity_score": round(score, 4),
            "category": "movie",
            "genres": meta.get("genres", []),
        })

        if len(recommendations) >= n:
            break

    return recommendations


def get_taste_vector_recommendations(
    liked_ids: Optional[List[str]] = None,
    n: int = 10,
) -> List[Dict[str, Any]]:
    """
    Return personalized recommendations based on an aggregated taste vector.
    - If liked_ids provided: average TF-IDF vectors of liked movies.
    - If liked_ids empty/None: auto-seed using movies with personal_rating >= 7.0,
      weighted by (personal_rating - 5.5).
    """
    if tfidf_matrix is None or not movie_ids:
        return []

    excluded_ids: set[str] = set()
    seed_vectors: List[np.ndarray] = []
    seed_weights: List[float] = []

    if liked_ids:
        for mid in liked_ids:
            idx = _resolve_movie_index(mid)
            if idx is not None:
                seed_vectors.append(tfidf_matrix[idx])
                seed_weights.append(1.0)
                excluded_ids.add(movie_ids[idx])
                excluded_ids.add(str(mid))
        reason_text = "Similar themes to your liked movies"
    else:
        # Auto-seed from personal_rating >= 7.0
        for mid, meta in movie_data_map.items():
            pr = meta.get("personal_rating")
            if pr is not None and pr >= 7.0:
                idx = _resolve_movie_index(mid)
                if idx is not None:
                    weight = float(pr - 5.5)  # Higher-rated contributes more
                    seed_vectors.append(tfidf_matrix[idx])
                    seed_weights.append(weight)
                    excluded_ids.add(mid)
        reason_text = "Based on your movie taste profile"

    if not seed_vectors:
        # No liked_ids and no personal_rating data yet -- fall back to the
        # dataset's own order (it was fetched from TMDB's popular + top_rated
        # lists, so this is a reasonable "popular" ordering even without a
        # stored numeric score).
        fallback: List[Dict[str, Any]] = []
        for mid, meta in list(movie_data_map.items())[:n]:
            fallback.append({
                "id": str(mid),
                "title": meta.get("title", "Unknown"),
                "imageUrl": meta.get("poster_url") or "",
                "reason": "Popular pick to get you started",
                "score": 50,
                "category": "movie",
            })
        return fallback

    # Compute weighted average taste vector
    weights_arr = np.array(seed_weights, dtype=np.float32).reshape(-1, 1)
    vectors_arr = np.array(seed_vectors, dtype=np.float32)
    taste_vector = np.sum(vectors_arr * weights_arr, axis=0, keepdims=True) / np.maximum(np.sum(weights_arr), 1e-6)

    # Compute cosine similarity
    norms = np.linalg.norm(tfidf_matrix, axis=1) * np.linalg.norm(taste_vector)
    similarities = (np.dot(tfidf_matrix, taste_vector.T).flatten() / np.maximum(norms, 1e-6))

    top_indices = np.argsort(-similarities)

    recommendations: List[Dict[str, Any]] = []
    for cand_idx in top_indices:
        cand_idx = int(cand_idx)
        cand_id = movie_ids[cand_idx]
        if cand_id in excluded_ids:
            continue

        score = float(similarities[cand_idx])
        meta = movie_data_map.get(cand_id, {})

        recommendations.append({
            "id": cand_id,
            "title": meta.get("title", "Unknown"),
            "imageUrl": meta.get("poster_url") or "",
            "reason": reason_text,
            "score": round(score, 4),
            "similarity_score": round(score, 4),
            "category": "movie",
            "genres": meta.get("genres", []),
        })

        if len(recommendations) >= n:
            break

    return recommendations
