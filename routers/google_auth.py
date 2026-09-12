import os
import time
import requests
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from services.auth import create_session_cookie
from database import upsert_google_user

load_dotenv()

router = APIRouter(prefix="/auth/google", tags=["google-auth"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    f"{FRONTEND_URL}/#id_token=",
)

# ===========================================================================
# REQUEST MODELS
# ===========================================================================

class GoogleTokenRequest(BaseModel):
    id_token: str

# ===========================================================================
# ROUTES
# ===========================================================================

@router.get("/login")
def google_login():
    """Return a redirect to Google's ID-token authorization endpoint."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="Google Client ID is not configured on the server.",
        )

    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
    )
    return RedirectResponse(url)


@router.get("/callback")
def google_callback(code: str | None = None, error: str | None = None):
    """Verify the Google authorization code, exchange it for an ID token, upsert user, and set session cookie."""
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"Google login failed: {error}",
        )
    if not code:
        raise HTTPException(
            status_code=400,
            detail="Missing authorization code.",
        )
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="Google Client ID is not configured on the server.",
        )

    # Exchange authorization code for token containing id_token
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    
    resp = requests.post(token_url, data=payload, timeout=10)
    if resp.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to exchange authorization code: {resp.text}",
        )

    token_data = resp.json()
    id_token = token_data.get("id_token")
    if not id_token:
        raise HTTPException(
            status_code=400,
            detail="Missing id_token in Google response.",
        )

    tokeninfo_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
    resp = requests.get(tokeninfo_url, timeout=10)

    if resp.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail="Invalid Google ID token.",
        )

    payload = resp.json()

    if payload.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=401,
            detail="Invalid token audience.",
        )

    google_sub = payload.get("sub")
    email = payload.get("email")
    name = payload.get("name")
    picture_url = payload.get("picture")

    if not google_sub or not email:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields from Google token.",
        )

    user = upsert_google_user(
        google_sub=google_sub,
        email=email,
        name=name,
        picture_url=picture_url,
    )

    session_cookie = create_session_cookie(user_id=str(user["id"]))
    
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
    response = RedirectResponse(FRONTEND_URL)
    response.set_cookie(
        key="session",
        value=session_cookie,
        httponly=True,
        samesite="none",
        secure=True,
        path="/",
        max_age=30 * 24 * 60 * 60,
    )

    return response


@router.post("/callback")
def google_callback_post(req: GoogleTokenRequest, response: Response):
    """Verify the Google ID token directly, upsert the user, and set the session cookie."""
    if not req.id_token:
        raise HTTPException(
            status_code=400,
            detail="Missing Google ID token.",
        )
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="Google Client ID is not configured on the server.",
        )

    tokeninfo_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={req.id_token}"
    resp = requests.get(tokeninfo_url, timeout=10)

    if resp.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail="Invalid Google ID token.",
        )

    payload = resp.json()

    if payload.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=401,
            detail="Invalid token audience.",
        )

    google_sub = payload.get("sub")
    email = payload.get("email")
    name = payload.get("name")
    picture_url = payload.get("picture")

    if not google_sub or not email:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields from Google token.",
        )

    user = upsert_google_user(
        google_sub=google_sub,
        email=email,
        name=name,
        picture_url=picture_url,
    )

    session_cookie = create_session_cookie(user_id=str(user["id"]))
    response.set_cookie(
        key="session",
        value=session_cookie,
        httponly=True,
        samesite="none",
        secure=True,
        path="/",
        max_age=30 * 24 * 60 * 60,
    )

    return {"message": "Login successful", "user_id": str(user["id"])}

