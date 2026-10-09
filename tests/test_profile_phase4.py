import uuid
import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models.profile import TasteControls
from services.auth import get_current_user_id


def test_profile_phase4_controls_and_feedback():
    test_user_id = f"test_user_p4_{uuid.uuid4().hex[:8]}"
    client = TestClient(app)
    app.dependency_overrides[get_current_user_id] = lambda: test_user_id

    try:
        # 1. GET default controls
        r = client.get("/profile/controls")
        assert r.status_code == 200, r.text
        ctrls = r.json()
        assert ctrls["domain_weights"]["music"] == 25
        assert ctrls["sliders"]["energy"] == 50

        # 2. PUT valid payload -> 200
        valid_payload = {
            "domain_weights": {"music": 40, "anime": 20, "movies": 20, "fashion": 20},
            "sliders": {"energy": 75, "obscurity": 80, "novelty": 60},
            "pinned": {"artists": ["Radiohead"], "genres": ["art rock"]},
            "hidden": {"artists": ["Blocked Artist"], "genres": ["screamo"]},
        }
        r = client.put("/profile/controls", json=valid_payload)
        assert r.status_code == 200, r.text
        updated = r.json()
        assert updated["domain_weights"]["music"] == 40
        assert updated["sliders"]["energy"] == 75
        assert "Radiohead" in updated["pinned"]["artists"]

        # 3. PUT invalid weights (sum != 100) -> 400
        invalid_weights = {
            "domain_weights": {"music": 30, "anime": 20, "movies": 20, "fashion": 20},  # sum=90
        }
        r = client.put("/profile/controls", json=invalid_weights)
        assert r.status_code == 400, r.text
        print("PUT invalid weights response:", r.json())

        # 4. PUT invalid pinned list (> 50) -> 400
        invalid_pinned = {
            "pinned": {"artists": [f"artist_{i}" for i in range(51)], "genres": []},
        }
        r = client.put("/profile/controls", json=invalid_pinned)
        assert r.status_code == 400, r.text
        print("PUT invalid pinned response:", r.json())

        # 5. GET feedback history
        r = client.get("/profile/feedback-history")
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

        # 6. DELETE feedback history without confirm -> 400
        r = client.delete("/profile/feedback-history")
        assert r.status_code == 400, r.text
        print("DELETE feedback without confirm:", r.json())

        # 7. DELETE feedback history with confirm -> 200
        r = client.delete("/profile/feedback-history?confirm=true")
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        print("DELETE feedback with confirm:", r.json())

    finally:
        app.dependency_overrides.pop(get_current_user_id, None)
