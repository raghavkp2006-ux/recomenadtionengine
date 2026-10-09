import pytest
from fastapi.testclient import TestClient
from main import app
from services.auth import get_current_user_id
from services.profile_insights import compute_shannon_entropy_diversity


def test_shannon_entropy_unit_check():
    """Verify Shannon entropy diversity formula exact values."""
    res_half = compute_shannon_entropy_diversity([0.5, 0.5])
    print(f"ENTROPY [0.5, 0.5]: {res_half}")
    assert res_half == 1.0

    res_single = compute_shannon_entropy_diversity([1.0])
    print(f"ENTROPY [1.0]: {res_single}")
    assert res_single == 0.0

    res_four = compute_shannon_entropy_diversity([0.25, 0.25, 0.25, 0.25])
    assert res_four == 1.0


def test_profile_insights_endpoints():
    client = TestClient(app)
    app.dependency_overrides[get_current_user_id] = lambda: "test_user_phase3"

    try:
        for r_name in ["short", "medium", "long"]:
            r = client.get(f"/profile/insights?range={r_name}")
            assert r.status_code == 200, r.text
            data = r.json()
            assert "range" in data
            assert data["range"] == r_name
            assert "personality" in data
            assert "diversity" in data
            assert "mainstream_score" in data
            assert "recently_played" in data
            print(f"RANGE {r_name} -> status={data['status']}, label={data['personality']['label']}")
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
