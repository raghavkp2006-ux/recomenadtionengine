"""
tests/test_add_movies_catalog.py — Verification tests for expanded movie catalog and TF-IDF index.
"""

import os
import pickle
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_movie_catalog_counts():
    os.environ["USE_LOCAL_DB"] = "true"
    from database import SessionLocal, Movie

    db = SessionLocal()
    try:
        total = db.query(Movie).count()
        assert total == 555, f"Expected 555 movies, got {total}"

        empty_overviews = db.query(Movie).filter((Movie.overview == None) | (Movie.overview == "")).count()
        assert empty_overviews == 0, f"Expected 0 empty overviews, got {empty_overviews}"

        empty_genres = db.query(Movie).filter((Movie.genres_json == None) | (Movie.genres_json == "[]")).count()
        assert empty_genres == 0, f"Expected 0 empty genres, got {empty_genres}"
    finally:
        db.close()


def test_movie_tfidf_artifacts():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    matrix_path = os.path.join(base_dir, "data", "processed", "movie_tfidf_matrix.pkl")
    vectorizer_path = os.path.join(base_dir, "data", "processed", "movie_tfidf_vectorizer.pkl")

    assert os.path.exists(matrix_path), "movie_tfidf_matrix.pkl missing"
    assert os.path.exists(vectorizer_path), "movie_tfidf_vectorizer.pkl missing"

    with open(matrix_path, "rb") as f:
        data = pickle.load(f)

    assert isinstance(data, dict), "matrix pkl must be a dict"
    assert "matrix" in data
    assert "ids" in data
    assert len(data["ids"]) == 555
    assert data["matrix"].shape[0] == 555


def test_movie_recommender_service_shape():
    from services import movie_recommender

    assert movie_recommender.tfidf_matrix is not None
    assert movie_recommender.tfidf_matrix.shape[0] == 555
    assert len(movie_recommender.movie_ids) == 555
    assert len(movie_recommender.movie_data_map) == 555
