import json

import numpy as np
import pytest
from sqlalchemy import Column, Float, Integer, MetaData, Table, create_engine

from scripts.eval_movies_loo import evaluate, load_catalog, write_report
from services import movie_recommender


@pytest.fixture
def clustered_catalog(monkeypatch):
    # Twenty liked action movies, eighty unliked romance movies. On each
    # fold the only remaining action movie is the held-out positive.
    rows = [dict(tmdb_id=i + 1000, personal_rating=7 + (i % 4) * 0.5 if i < 20 else None,
                 vote_average=float((i * 7) % 10)) for i in range(100)]
    ids = [str(row["tmdb_id"]) for row in rows]
    matrix = np.array([[1, 0] if i < 20 else [0, 1] for i in range(100)], dtype=float)
    monkeypatch.setattr(movie_recommender, "movie_ids", ids)
    monkeypatch.setattr(movie_recommender, "movie_id_to_idx", {mid: i for i, mid in enumerate(ids)})
    monkeypatch.setattr(movie_recommender, "movie_data_map", {mid: {} for mid in ids})
    monkeypatch.setattr(movie_recommender, "tfidf_matrix", matrix)
    engine = create_engine("sqlite://")
    table = Table("movies", MetaData(), Column("tmdb_id", Integer, primary_key=True),
                  Column("personal_rating", Float), Column("vote_average", Float))
    table.create(engine)
    with engine.begin() as db:
        db.execute(table.insert(), rows)
    yield load_catalog(engine)
    engine.dispose()


def test_beats_random_and_deterministic(clustered_catalog):
    result = evaluate(clustered_catalog)
    assert result["metrics"]["HitRate@10"] == 1
    assert result["metrics"]["HitRate@10"] > result["baselines"]["random"]["HitRate@10"]
    assert result["metrics"]["NDCG@10"] == result["metrics"]["MRR"] == 1
    assert result == evaluate(list(reversed(clustered_catalog)))


def test_correlated_ratings_guard(clustered_catalog):
    for row in clustered_catalog:
        if row["personal_rating"] is not None:
            row["vote_average"] = row["personal_rating"]
    with pytest.raises(ValueError, match="Ratings look synthetic"):
        evaluate(clustered_catalog)
    result = evaluate(clustered_catalog, allow_synthetic=True)
    assert result["rating_source"] == "synthetic_suspected"
    assert "synthetic" in result["caveat"]


def test_json_schema(clustered_catalog, tmp_path):
    result = evaluate(clustered_catalog)
    path = tmp_path / "movies_loo.json"
    write_report(result, path)
    data = json.loads(path.read_text())
    assert {"metrics", "baselines", "n_liked", "n_catalog", "rating_source", "lift"} <= data.keys()
    assert data["n_liked"] == 20 and data["n_catalog"] == 100
    assert set(data["baselines"]) == {"random", "popularity"}
    assert all(0 <= value <= 1 for value in data["metrics"].values())
    assert data["rating_source"] == "unverified"


def test_folds_seed_only_remaining_likes(clustered_catalog, monkeypatch):
    actual = movie_recommender.get_taste_vector_recommendations
    calls = []
    def record(*, liked_ids, n):
        calls.append(set(liked_ids))
        return actual(liked_ids=liked_ids, n=n)
    monkeypatch.setattr(movie_recommender, "get_taste_vector_recommendations", record)
    result = evaluate(clustered_catalog)
    liked = {str(row["tmdb_id"]) for row in clustered_catalog if row["personal_rating"] is not None}
    for fold, seeds in zip(result["folds"], calls):
        assert seeds == liked - {fold["held_out"]}
        assert fold["model"] == 1


def test_requires_twenty_likes(clustered_catalog):
    clustered_catalog[0]["personal_rating"] = None
    with pytest.raises(ValueError, match="found 19"):
        evaluate(clustered_catalog)


def test_missing_artifact_movie_refuses_partial_catalog(clustered_catalog):
    clustered_catalog.append(dict(tmdb_id=9999, personal_rating=None, vote_average=5))
    with pytest.raises(ValueError, match="full database catalog"):
        evaluate(clustered_catalog)
