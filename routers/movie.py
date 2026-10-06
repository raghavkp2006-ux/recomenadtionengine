"""
routers/movie.py — Movie domain router.

Endpoints
---------
Static paths (registered first):
  GET  /movie/search                 — substring search on movie titles
  POST /movie/recommendations        — personalized multi-item or auto-seeded recommendations

Parameterised paths:
  GET  /movie/{movie_id}             — single movie detail
  GET  /movie/{movie_id}/recommend   — TF-IDF cosine similarity recommendations
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from pydantic import BaseModel

from services.movie_recommender import (
    get_similar_movies,
    get_taste_vector_recommendations,
    movie_data_map,
    movie_ids,
    _resolve_movie_index,
    tfidf_matrix,
)
from database import Movie, RecommendationFeedback, SessionLocal
from services.auth import get_current_user_id
from services.rerank import rerank
from datetime import datetime, timezone

router = APIRouter(prefix="/movie", tags=["movie"])


class MovieRecRequest(BaseModel):
    liked_ids: Optional[List[str]] = None


# ===========================================================================
# STATIC-PATH ROUTES — registered BEFORE parameterised routes
# ===========================================================================

@router.get("/search")
def search_movies(q: str = Query(..., min_length=1)):
    """Substring search on catalog movie titles."""
    q_lower = q.lower()
    results = [
        meta for meta in movie_data_map.values()
        if q_lower in (meta.get("title") or "").lower()
    ]
    return {"results": results[:10]}


@router.post("/recommendations")
def get_recommendations(
    request: MovieRecRequest,
    n: int = Query(default=10, ge=1, le=50),
    user_id: str = Depends(get_current_user_id),
):
    """
    Return personalized movie recommendations.
    - If liked_ids provided in body: average TF-IDF vectors of liked movies.
    - If liked_ids empty/omitted: auto-seed using movies with personal_rating >= 7.0
      weighted by (personal_rating - 5.5).
    """
    recommendations = get_taste_vector_recommendations(liked_ids=request.liked_ids, n=max(40, n))
    vectors = [tfidf_matrix[_resolve_movie_index(item["id"])] for item in recommendations]
    scores = [float(item.get("score", 0.0)) for item in recommendations]
    db = SessionLocal()
    try:
        feedback_rows = db.query(RecommendationFeedback).filter_by(user_id=user_id, domain="movie").all()
        candidate_ids = [int(item["id"]) for item in recommendations if str(item["id"]).isdigit()]
        rated = {str(m.tmdb_id): m.personal_rating for m in db.query(Movie).filter(
            Movie.tmdb_id.in_(candidate_ids)).all()}
        scores = [score + (float(rated.get(str(item["id"])) or 0.0) / 10.0) * 0.15
                  for item, score in zip(recommendations, scores)]
        reranked = rerank(recommendations, scores, vectors, user_id=user_id, feedback=feedback_rows, k=n)
        now = datetime.now(timezone.utc)
        db.add_all([RecommendationFeedback(user_id=user_id, domain="movie", item_id=str(item["id"]),
                                            action="shown", created_at=now) for item in reranked])
        db.commit()
        recommendations = reranked
    finally:
        db.close()
    return {"recommendations": recommendations}


# ===========================================================================
# PARAMETERISED ROUTES — /{movie_id} and sub-paths
# ===========================================================================

@router.get("/{movie_id}")
def get_movie(movie_id: str):
    """Return a single movie record from catalog by tmdb_id or database id."""
    idx = _resolve_movie_index(movie_id)
    if idx is None:
        raise HTTPException(status_code=404, detail=f"Movie '{movie_id}' not found in catalog")

    tmdb_id_str = movie_ids[idx]
    return movie_data_map.get(tmdb_id_str, {})


@router.get("/{movie_id}/recommend")
def recommend_movie(
    movie_id: str,
    request: Request,
    n: int = Query(default=5, ge=1, le=50),
    personalize: bool = Query(default=False),
):
    """
    Compute TF-IDF cosine similarity against the precomputed catalog matrix
    and return top-N most similar movies matching the shared contract:
    { id, title, imageUrl, reason, score, category: "movie" }.

    Optional: pass ``?personalize=true`` to re-rank results using the user's
    cross-module taste profile (requires a valid session cookie).  The base
    similarity score is preserved — the profile boost only reorders; it never
    discards items.  Non-personalized behaviour is unchanged when the param
    is omitted or false.
    """
    idx = _resolve_movie_index(movie_id)
    if idx is None:
        raise HTTPException(status_code=404, detail=f"Movie '{movie_id}' not found in catalog")

    from services.auth import serializer as _session_serializer
    user_id: Optional[str] = None
    _cookie = request.cookies.get("session")
    if _cookie:
        try:
            user_id = _session_serializer.loads(_cookie).get("user_id")
        except Exception:
            pass

    recommendations = get_similar_movies(movie_id=movie_id, n=n)

    # --- Optional: personalized re-ranking ---
    if personalize and user_id:
        try:
            from services.taste_profile import get_movie_boost_map  # lazy import
            boost_map = get_movie_boost_map(user_id)
            boost_map_lower = {k.lower(): v for k, v in boost_map.items()}
            for rec in recommendations:
                rec_genres = [g.lower() for g in rec.get("genres", [])]
                genre_boost = sum(boost_map_lower.get(g, 0.0) for g in rec_genres)
                # Boost formula: score * (1 + normalised_boost)
                # Normalise by dividing by 10 to keep multiplier sane
                normalised_boost = genre_boost / 10.0
                base_score = rec.get("similarity_score") if rec.get("similarity_score") is not None else rec.get("score", 0.0)
                rec["personalized_score"] = round(
                    base_score * (1.0 + normalised_boost), 4
                )
                rec["genre_boost"] = round(genre_boost, 4)
            # Re-sort by personalized_score
            recommendations.sort(key=lambda r: r.get("personalized_score", 0.0), reverse=True)
        except Exception as exc:
            print(f"[movie] personalize error: {exc}")
            # Fall through — return un-boosted results

    return {"recommendations": recommendations, "personalized": personalize}

