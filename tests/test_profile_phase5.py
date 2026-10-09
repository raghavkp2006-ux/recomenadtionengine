import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, User, SpotifyUser, SpotifyPlayEvent, UserLike
from services.auth import get_current_user_id

client = TestClient(app)

def test_profile_phase5_timeline_and_bridges():
    test_user_id = f"test_user_p5_{uuid.uuid4().hex[:8]}"

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.google_sub == test_user_id).first()
        if not user:
            user = User(google_sub=test_user_id, email="test_phase5@polytaste.app", name="Phase5Tester")
            db.add(user)
            db.commit()

        # Add a Spotify play event
        play = SpotifyPlayEvent(
            user_id=test_user_id,
            track_id="sp_trk_1",
            track_name="Midnight City",
            artist_names_json='["M83"]',
            played_at=datetime.now(timezone.utc),
        )
        db.add(play)

        # Add an Anime like
        anime_like = UserLike(
            user_id=test_user_id,
            module="anime",
            item_id="1",
            liked_at=1700000000,
        )
        db.add(anime_like)
        db.commit()
    finally:
        db.close()

    app.dependency_overrides[get_current_user_id] = lambda: test_user_id
    try:
        # 1. Timeline
        res_tl = client.get("/profile/timeline?limit=10")
        assert res_tl.status_code == 200
        tl_data = res_tl.json()
        assert isinstance(tl_data, list)
        assert len(tl_data) >= 2
        domains_in_tl = [item["domain"] for item in tl_data]
        assert "spotify" in domains_in_tl
        assert "anilist" in domains_in_tl

        # 2. Bridges
        res_br = client.get("/profile/bridges")
        assert res_br.status_code == 200
        bridges_data = res_br.json()
        assert isinstance(bridges_data, list)
        assert len(bridges_data) <= 6
        assert len(bridges_data) > 0
        first_b = bridges_data[0]
        assert "from" in first_b and "to" in first_b
        assert "strength" in first_b and "reason" in first_b

        # 3. Taste Tags
        res_tg = client.get("/profile/taste-tags")
        assert res_tg.status_code == 200
        tags_data = res_tg.json()
        assert isinstance(tags_data, list)
        assert len(tags_data) >= 6
    finally:
        app.dependency_overrides.clear()
