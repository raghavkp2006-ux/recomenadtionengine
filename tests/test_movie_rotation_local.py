"""End-to-end recommendation checks against the configured local SQLite DB."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
from fastapi.testclient import TestClient

from database import RecommendationFeedback, SessionLocal, engine
from main import app
from services.movie_recommender import _resolve_movie_index, movie_data_map, tfidf_matrix
from services.rerank import rerank
from services.auth import create_session_cookie


def test_local_movie_rotation_feedback_and_posters():
    assert engine.dialect.name == "sqlite", "This integration test must use the local SQLite database"
    user_id = f"rotation-test-{uuid4()}"
    db = SessionLocal()
    try:
        assert db.query(RecommendationFeedback).filter_by(user_id=user_id).count() == 0
    finally:
        db.close()

    try:
        client = TestClient(app)
        client.cookies.set("session", create_session_cookie(user_id))
        responses = []
        all_ids: set[str] = set()
        for _ in range(5):
            response = client.post("/movie/recommendations", json={})
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["source"] in {"crosswalk_profile", "sampling_fallback"}
            items = payload["recommendations"]
            assert len(items) == 10
            assert all(item.get("poster_url") for item in items)
            if responses:
                overlap = {item["id"] for item in responses[-1]} & {item["id"] for item in items}
                assert len(overlap) <= 3
            responses.append(items)
            all_ids.update(item["id"] for item in items)
        assert len(all_ids) >= 25

        disliked_id = responses[-1][0]["id"]
        disliked = client.post("/feedback", json={"domain": "movie", "item_id": disliked_id, "action": "dislike"})
        assert disliked.status_code == 200, disliked.text
        after_dislike = []
        for _ in range(2):
            response = client.post("/movie/recommendations", json={})
            assert response.status_code == 200, response.text
            after_dislike = response.json()["recommendations"]
            assert all(item.get("poster_url") for item in after_dislike)
            assert disliked_id not in {item["id"] for item in after_dislike}

        liked_id = after_dislike[0]["id"]
        liked_response = client.post("/feedback", json={"domain": "movie", "item_id": liked_id, "action": "like"})
        assert liked_response.status_code == 200, liked_response.text

        # Compare a real catalog item's score with and without its persisted
        # like vector. No fake catalog rows or mocked database are involved.
        liked_index = _resolve_movie_index(liked_id)
        liked_vector = np.asarray(tfidf_matrix[liked_index]).ravel()
        nearest = []
        for movie_id in movie_data_map:
            index = _resolve_movie_index(movie_id)
            if index is None or str(movie_id) in {liked_id, disliked_id}:
                continue
            vector = np.asarray(tfidf_matrix[index]).ravel()
            denominator = np.linalg.norm(vector) * np.linalg.norm(liked_vector)
            similarity = float(np.dot(vector, liked_vector) / denominator) if denominator else 0.0
            nearest.append((similarity, str(movie_id), vector))
        nearest.sort(reverse=True, key=lambda row: row[0])
        candidates = [{"id": liked_id}] + [{"id": movie_id} for _, movie_id, _ in nearest[:59]]
        vectors = [liked_vector] + [vector for _, _, vector in nearest[:59]]
        db = SessionLocal()
        try:
            like_row = db.query(RecommendationFeedback).filter_by(
                user_id=user_id, domain="movie", item_id=liked_id, action="like"
            ).order_by(RecommendationFeedback.created_at.desc()).first()
            assert like_row is not None
        finally:
            db.close()
        baseline = rerank(candidates, [0.0] * len(candidates), vectors, user_id=user_id,
                          feedback=[], k=len(candidates))
        with_like = rerank(candidates, [0.0] * len(candidates), vectors, user_id=user_id,
                           feedback=[SimpleNamespace(item_id=liked_id, action="like",
                                                     created_at=like_row.created_at or datetime.now(timezone.utc))],
                           k=len(candidates))
        baseline_scores = {item["id"]: item["score"] for item in baseline}
        liked_scores = {item["id"]: item["score"] for item in with_like}
        nearest_id = nearest[0][1]
        assert liked_scores[nearest_id] > baseline_scores[nearest_id]
    finally:
        db = SessionLocal()
        try:
            db.query(RecommendationFeedback).filter_by(user_id=user_id).delete()
            db.commit()
        finally:
            db.close()
