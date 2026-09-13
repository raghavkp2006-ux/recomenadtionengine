"""
routers/taste.py — Cross-module taste profile endpoint.

  GET /taste-profile    — requires auth, returns combined taste profile
"""

import time
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Request

from services.auth import get_current_user_id
from services.taste_profile import compute_taste_profile, compute_convergence
from services.spotify_sync import refresh_spotify_token
from database import get_user, get_anilist_user

router = APIRouter(tags=["taste"])


@router.get("/taste-profile")
def get_taste_profile(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Return the user's combined cross-module taste profile.

    Aggregates:
    - Spotify: weighted genre profile from top artists (requires valid Spotify token)
    - Anime:   genres of explicitly liked anime
    - Amazon:  categories of explicitly liked products

    The ``crosswalk_anime`` field shows which anime genres are boosted based on
    the user's Spotify taste (used by GET /anime/{mal_id}/recommend?personalize=true).
    """
    # Attempt to get a Spotify token for this user — silently skip if unavailable
    spotify_token: str | None = None
    try:
        user_record = get_user(user_id)
        if user_record:
            import time
            if user_record.get("expires_at", 0) > int(time.time()):
                spotify_token = user_record.get("access_token")
    except Exception:
        pass  # Spotify signal is optional

    profile_data = compute_taste_profile(user_id, spotify_token=spotify_token)

    return {
        "user_id": user_id,
        "spotify_connected": spotify_token is not None,
        "anilist_connected": get_anilist_user(user_id) is not None,
        **profile_data,
    }


@router.get("/taste/convergence")
def get_convergence(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    Return the user's computed Convergence score and domain segments.
    Score is 0-100 based on domain coverage (0-40) and cross-domain
    cosine similarity agreement (0-60).
    """
    spotify_token: str | None = None
    try:
        user_record = get_user(user_id)
        if user_record:
            if user_record.get("expires_at", 0) > int(time.time()):
                spotify_token = user_record.get("access_token")
            else:
                spotify_token = refresh_spotify_token(user_record)
    except Exception as e:
        print(f"[taste] Spotify token resolution failed for user {user_id}: {e}")

    profile_data = compute_taste_profile(user_id, spotify_token=spotify_token)
    return compute_convergence(profile_data)

