"""Tests for Phase 6: Public Profile, Sharing Privacy, and Compatibility."""

from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, User
from models.profile import PublicProfile, DEFAULT_VISIBILITY
from services.auth import get_current_user_id

client = TestClient(app)


def test_profile_phase6_public_and_compatibility():
    user_a = "test_user_phase6_a"
    user_b = "test_user_phase6_b"

    db = SessionLocal()
    try:
        # Create users
        for uid, name in [(user_a, "Alpha User"), (user_b, "Beta User")]:
            u = db.query(User).filter(User.google_sub == uid).first()
            if not u:
                u = User(google_sub=uid, email=f"{uid}@polytaste.app", name=name)
                db.add(u)
        db.commit()

        # Clean public profiles
        db.query(PublicProfile).filter(PublicProfile.user_id.in_([user_a, user_b])).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

    # 1. Test unauthenticated request on non-existent or private profile -> 404
    res_404 = client.get("/public/profile/nonexistent_slug")
    assert res_404.status_code == 404
    assert "private" in res_404.json()["detail"].lower()

    # 2. Authenticated user_a checks visibility -> starts as private
    app.dependency_overrides[get_current_user_id] = lambda: user_a
    try:
        res_vis = client.get("/profile/visibility")
        assert res_vis.status_code == 200
        vis_data = res_vis.json()
        assert vis_data["is_public"] is False
        slug_a = vis_data["slug"]
        assert len(slug_a) >= 8

        # Unauthenticated access to user_a while private -> 404
        res_unauth = client.get(f"/public/profile/{slug_a}")
        assert res_unauth.status_code == 404

        # Update user_a to public with genres and personality visible
        res_put = client.put(
            "/profile/visibility",
            json={
                "is_public": True,
                "visibility": {"genres": True, "personality": True, "stats": False},
            },
        )
        assert res_put.status_code == 200
        assert res_put.json()["is_public"] is True
        assert res_put.json()["visibility"]["genres"] is True
    finally:
        app.dependency_overrides.clear()

    # 3. Test unauthenticated request on public profile -> 200 with strict privacy guarantees
    res_pub = client.get(f"/public/profile/{slug_a}")
    assert res_pub.status_code == 200
    pub_payload = res_pub.json()
    assert pub_payload["is_public"] is True
    assert "display_name" in pub_payload
    # Strict privacy verification: user_id, email, google_sub, tokens must NOT exist
    assert "user_id" not in pub_payload
    assert "email" not in pub_payload
    assert "google_sub" not in pub_payload
    assert "tokens" not in pub_payload
    assert "spotify_token" not in pub_payload
    # Cache-Control header check
    assert res_pub.headers.get("cache-control") == "no-store"

    # 4. Authenticated user_b tests compatibility against user_a slug
    app.dependency_overrides[get_current_user_id] = lambda: user_b
    try:
        res_compat = client.get(f"/profile/compatibility/{slug_a}")
        assert res_compat.status_code == 200
        c_data = res_compat.json()
        assert "score_pct" in c_data
        assert 1 <= c_data["score_pct"] <= 100
    finally:
        app.dependency_overrides.clear()
