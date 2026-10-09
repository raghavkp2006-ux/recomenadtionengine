"""Tests for Phase 8: Applying Controls to Rerank and Recommendations."""

from types import SimpleNamespace
from services.rerank import rerank
from models.profile import TasteControls


def test_rerank_hidden_items_filtered_out():
    items = [
        {"id": "1", "artists": ["Radiohead"], "genres": ["art rock"]},
        {"id": "2", "artists": ["Drake"], "genres": ["hip hop"]},
        {"id": "3", "artists": ["Chopin"], "genres": ["classical"]},
    ]
    vectors = [{1}, {2}, {3}]
    scores = [0.9, 0.85, 0.8]

    # Hide Drake
    controls = {
        "hidden": {"artists": ["Drake"], "genres": []},
        "pinned": {"artists": [], "genres": []},
        "sliders": {"novelty": 50},
    }

    result = rerank(items, scores, vectors, user_id="u_phase8", controls=controls, k=5)
    result_ids = [x["id"] for x in result]
    assert "2" not in result_ids
    assert "1" in result_ids
    assert "3" in result_ids


def test_rerank_pinned_items_boosted():
    items = [
        {"id": "1", "artists": ["Artist A"], "genres": ["pop"]},
        {"id": "2", "artists": ["Artist B"], "genres": ["metal"]},
    ]
    vectors = [{1}, {2}]
    # Artist B starts with lower score
    scores = [0.55, 0.50]

    controls = {
        "hidden": {"artists": [], "genres": []},
        "pinned": {"artists": ["Artist B"], "genres": []},
        "sliders": {"novelty": 50},
    }

    result = rerank(items, scores, vectors, user_id="u_phase8", controls=controls, k=5)
    # Artist B received +0.15 boost, so it should rank first
    assert result[0]["id"] == "2"
