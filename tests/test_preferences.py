import pytest
from fastapi.testclient import TestClient
from main import app
from services.auth import create_session_cookie
from database import SessionLocal, User

client = TestClient(app)


@pytest.fixture
def pref_test_user():
    db = SessionLocal()
    user_id = None
    try:
        user = User(
            google_sub="test_preferences_fixture_sub",
            email="pref-test@example.com",
            name="Pref Test User",
            theme="dark",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    yield user_id

    # Cleanup regardless of test outcome
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.google_sub == "test_preferences_fixture_sub").first()
        if u:
            db.delete(u)
            db.commit()
    finally:
        db.close()


def test_preferences_unauthenticated():
    response = client.get("/preferences")
    assert response.status_code == 401


def test_preferences_get_and_update(pref_test_user):
    token = create_session_cookie(str(pref_test_user))
    client.cookies.set("session", token)

    try:
        # Initial state should be default 'dark'
        res = client.get("/preferences")
        assert res.status_code == 200
        assert res.json() == {"theme": "dark"}

        # Update to light
        res_put = client.put("/preferences", json={"theme": "light"})
        assert res_put.status_code == 200
        assert res_put.json() == {"theme": "light"}

        # Re-fetch to ensure persistence
        res_get = client.get("/preferences")
        assert res_get.status_code == 200
        assert res_get.json() == {"theme": "light"}

        # Validation test: invalid theme rejected with 422
        res_invalid = client.put("/preferences", json={"theme": "neon"})
        assert res_invalid.status_code == 422
    finally:
        client.cookies.clear()
