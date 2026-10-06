import os
from fastapi import Request, HTTPException, status
from itsdangerous import URLSafeSerializer
from dotenv import load_dotenv

load_dotenv()

_DEFAULT_SECRET_KEY = "dev_secret_key_change_me_in_prod"
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", _DEFAULT_SECRET_KEY)

if os.getenv("ENV") == "production" and (not os.getenv("SESSION_SECRET_KEY") or SESSION_SECRET_KEY == _DEFAULT_SECRET_KEY):
    raise RuntimeError(
        "SESSION_SECRET_KEY must be set to a secure custom value when ENV=production."
    )

# HTTP cookies are permitted only when local development is explicitly selected.
SESSION_COOKIE_SECURE = os.getenv("ENV") != "local"
SESSION_COOKIE_SAMESITE = "lax" if os.getenv("ENV") == "local" else "none"

serializer = URLSafeSerializer(SESSION_SECRET_KEY, salt="session-cookie")
state_serializer = URLSafeSerializer(SESSION_SECRET_KEY, salt="oauth-state")

def create_session_cookie(user_id: str) -> str:
    """Sign the user_id into a session cookie string."""
    return serializer.dumps({"user_id": user_id})

def get_current_user_id(request: Request) -> str:
    """
    FastAPI dependency to get the current user_id from the session cookie.
    Raises 401 Unauthorized if missing or invalid.
    """
    cookie = request.cookies.get("session")
    if not cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in.",
        )
    try:
        data = serializer.loads(cookie)
        user_id = data.get("user_id")
        if not user_id:
            raise ValueError("No user_id in session")
        return user_id
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again.",
        )

def create_state_token(user_id: str) -> str:
    """Sign the connect_user_id into a state token string."""
    return state_serializer.dumps({"connect_user_id": user_id})

def verify_state_token(token: str) -> str:
    """
    Verify state token and return the connect_user_id.
    Raises 401 Unauthorized if invalid.
    """
    try:
        data = state_serializer.loads(token)
        user_id = data.get("connect_user_id")
        if not user_id:
            raise ValueError("No connect_user_id in state token")
        return user_id
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OAuth state token.",
        )

