import pytest
from fastapi.testclient import TestClient
from main import app
from services.auth import get_current_user_id


def test_profile_phase2_endpoints():
    client = TestClient(app)
    app.dependency_overrides[get_current_user_id] = lambda: "test_user_phase2"

    try:
        # 1. Overview
        r = client.get("/profile/overview")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "counts" in data
        assert "movies_rated" in data["counts"]
        assert "places_rated" in data["counts"]

        # 2. Connections
        r = client.get("/profile/connections")
        assert r.status_code == 200, r.text
        conns = r.json()
        assert isinstance(conns, list)
        domains = [c["domain"] for c in conns]
        assert "spotify" in domains
        assert "anilist" in domains
        assert "myntra" in domains
        assert "movies" in domains

        # 3. Resync domain
        r = client.post("/profile/connections/movies/resync")
        assert r.status_code == 200, r.text
        resync_data = r.json()
        assert resync_data["domain"] == "movies"
        assert resync_data["status"] == "ok"

        # 4. Disconnect without confirm -> 400
        r = client.delete("/profile/connections/movies")
        assert r.status_code == 400

        # 5. Disconnect with confirm -> 200
        r = client.delete("/profile/connections/movies?confirm=true")
        assert r.status_code == 200
        assert r.json()["ok"] is True
    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
