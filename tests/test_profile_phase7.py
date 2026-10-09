"""Tests for Phase 7: Data Export, Nuclear Wipe, and Playlist Generation."""

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, User, SpotifyUser, SpotifyPlayEvent, UserLike
from models.profile import TasteControls, PublicProfile, SyncLog
from services.auth import get_current_user_id

client = TestClient(app)


def test_profile_phase7_export_wipe_playlist():
    user_id = "test_user_phase7"

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.google_sub == user_id).first()
        if not user:
            user = User(google_sub=user_id, email="test_phase7@polytaste.app", name="Phase7Tester")
            db.add(user)

        # Add mock spotify user
        sp_user = db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first()
        if not sp_user:
            sp_user = SpotifyUser(
                user_id=user_id,
                access_token="mock_token",
                refresh_token="mock_refresh",
                expires_at=9999999999,
                spotify_account_id="sp_phase7",
            )
            db.add(sp_user)

        # Add taste controls
        ctrl = db.query(TasteControls).filter(TasteControls.user_id == user_id).first()
        if not ctrl:
            ctrl = TasteControls(user_id=user_id)
            db.add(ctrl)

        db.commit()
    finally:
        db.close()

    app.dependency_overrides[get_current_user_id] = lambda: user_id
    try:
        # 1. Test data export -> 200 with Content-Disposition
        res_exp = client.get("/profile/export")
        assert res_exp.status_code == 200
        assert "attachment" in res_exp.headers.get("content-disposition", "")
        exp_data = res_exp.json()
        assert "version" in exp_data
        assert "exported_at" in exp_data
        assert "connections" in exp_data
        # Ensure sensitive token fields are excluded
        assert "access_token" not in exp_data.get("connections", {}).get("spotify", {})
        assert "refresh_token" not in exp_data.get("connections", {}).get("spotify", {})

        # 2. Test playlist creation with mock or missing scope -> returns 409 needs_reconnect, never 500
        res_pl = client.post("/profile/playlist", json={"name": "Test Run", "range": "short"})
        assert res_pl.status_code in (200, 409)
        if res_pl.status_code == 409:
            assert "needs_reconnect" in res_pl.json()["detail"]["status"]

        # 3. Test nuclear wipe without confirm -> 400
        res_wipe_bad = client.delete("/profile/data")
        assert res_wipe_bad.status_code == 400

        # 4. Test nuclear wipe with confirm=DELETE -> 200
        res_wipe_ok = client.delete("/profile/data?confirm=DELETE")
        assert res_wipe_ok.status_code == 200
        assert res_wipe_ok.json()["ok"] is True

        # Verify data is wiped in DB
        db2 = SessionLocal()
        try:
            assert db2.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first() is None
            assert db2.query(TasteControls).filter(TasteControls.user_id == user_id).first() is None
        finally:
            db2.close()
    finally:
        app.dependency_overrides.clear()
