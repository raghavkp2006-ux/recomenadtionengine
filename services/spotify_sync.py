"""
services/spotify_sync.py — Incremental Spotify play history sync service.
"""

import os
import time
import json
import base64
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import requests
from fastapi import HTTPException
from dotenv import load_dotenv

from database import SessionLocal, SpotifyUser, SpotifyPlayEvent, get_user, upsert_user

load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")


def get_auth_header() -> Dict[str, str]:
    """Return Basic Auth header for Spotify token requests."""
    auth_str = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {b64_auth_str}"}


def refresh_spotify_token(user: Dict[str, Any]) -> str:
    """Refresh Spotify access token using refresh_token."""
    url = "https://accounts.spotify.com/api/token"
    headers = get_auth_header()
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": user.get("refresh_token"),
    }
    response = requests.post(url, headers=headers, data=data, timeout=10)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to refresh token")

    token_info = response.json()
    new_access_token = token_info["access_token"]
    new_refresh_token = token_info.get("refresh_token", user.get("refresh_token"))
    new_expires_at = int(time.time()) + token_info["expires_in"]

    upsert_user(
        user["user_id"],
        new_access_token,
        new_refresh_token,
        new_expires_at,
        user.get("spotify_account_id"),
        user.get("spotify_display_name"),
    )
    return new_access_token


def get_valid_access_token(user_id: str) -> str:
    """Return a valid Spotify access token for user_id, refreshing if expired."""
    user = get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not logged in with Spotify. Please visit /spotify/login",
        )
    if int(time.time()) > int(user.get("expires_at", 0)):
        return refresh_spotify_token(user)
    return user.get("access_token")


def parse_spotify_datetime(dt_str: str) -> datetime:
    """Parse Spotify ISO 8601 timestamp string into naive UTC datetime."""
    cleaned = dt_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def sync_user_recent_plays(user_id: str) -> Dict[str, Any]:
    """
    Fetch new Spotify plays for user_id since their last sync, store them,
    and advance their last_synced_at.

    Returns a summary dict, e.g.:
        {"user_id": ..., "new_plays": <int>, "status": "ok" | "sync_disabled"
         | "token_invalid" | "no_new_plays"}
    """
    db = SessionLocal()
    try:
        user_row = db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first()
        if not user_row or not user_row.sync_enabled:
            return {
                "user_id": user_id,
                "new_plays": 0,
                "status": "sync_disabled",
            }

        # Step 2: Get a valid access token (refresh if expired)
        try:
            user_dict = user_row.to_dict()
            if int(time.time()) > int(user_row.expires_at or 0):
                access_token = refresh_spotify_token(user_dict)
            else:
                access_token = user_row.access_token
        except Exception as e:
            print(f"[spotify_sync] Token refresh failed for {user_id}: {e}")
            user_row.sync_enabled = False
            db.commit()
            return {
                "user_id": user_id,
                "new_plays": 0,
                "status": "token_invalid",
            }

        # Step 3: Fetch recently played from Spotify API
        params: Dict[str, Any] = {"limit": 50}
        if user_row.last_synced_at:
            # Convert last_synced_at to epoch milliseconds
            last_epoch_ms = int(
                user_row.last_synced_at.replace(tzinfo=timezone.utc).timestamp() * 1000
            )
            params["after"] = last_epoch_ms

        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(
            "https://api.spotify.com/v1/me/player/recently-played",
            headers=headers,
            params=params,
            timeout=10,
        )

        # If 401, retry once after token refresh
        if resp.status_code == 401:
            try:
                access_token = refresh_spotify_token(user_dict)
                headers = {"Authorization": f"Bearer {access_token}"}
                resp = requests.get(
                    "https://api.spotify.com/v1/me/player/recently-played",
                    headers=headers,
                    params=params,
                    timeout=10,
                )
            except Exception:
                pass

        if resp.status_code == 401:
            user_row.sync_enabled = False
            db.commit()
            return {
                "user_id": user_id,
                "new_plays": 0,
                "status": "token_invalid",
            }

        if resp.status_code != 200:
            print(
                f"[spotify_sync] Spotify API error {resp.status_code} for user {user_id}: {resp.text}"
            )
            return {
                "user_id": user_id,
                "new_plays": 0,
                "status": "error",
                "detail": f"Spotify API returned HTTP {resp.status_code}",
            }

        data = resp.json()
        items = data.get("items", [])
        if not items:
            return {
                "user_id": user_id,
                "new_plays": 0,
                "status": "no_new_plays",
            }

        new_plays_count = 0
        max_played_at: Optional[datetime] = None
        seen_played_ats = set()

        # Step 4 & 5: Deduplicate and insert play events
        for item in items:
            track = item.get("track") or {}
            track_id = track.get("id")
            if not track_id:
                continue

            track_name = track.get("name")
            artists = track.get("artists") or []
            artist_names = [a.get("name") for a in artists if a.get("name")]
            artist_ids = [a.get("id") for a in artists if a.get("id")]
            played_at_raw = item.get("played_at")
            if not played_at_raw:
                continue

            # Album metadata
            album = track.get("album") or {}
            album_name = album.get("name")
            images = album.get("images") or []
            album_image_url = images[0].get("url") if images else None
            duration_ms = track.get("duration_ms")

            played_at_dt = parse_spotify_datetime(played_at_raw)
            if max_played_at is None or played_at_dt > max_played_at:
                max_played_at = played_at_dt

            # Skip duplicate timestamps within the same batch
            if played_at_dt in seen_played_ats:
                continue
            seen_played_ats.add(played_at_dt)

            # Check for existing play event by unique constraint (user_id, played_at)
            existing = (
                db.query(SpotifyPlayEvent)
                .filter(
                    SpotifyPlayEvent.user_id == user_id,
                    SpotifyPlayEvent.played_at == played_at_dt,
                )
                .first()
            )
            if not existing:
                play_event = SpotifyPlayEvent(
                    user_id=user_id,
                    track_id=track_id,
                    track_name=track_name,
                    artist_names_json=json.dumps(artist_names),
                    artist_ids_json=json.dumps(artist_ids),
                    album_name=album_name,
                    album_image_url=album_image_url,
                    duration_ms=duration_ms,
                    played_at=played_at_dt,
                )
                db.add(play_event)
                new_plays_count += 1

        # Step 6: Always advance last_synced_at when Spotify returned items so the
        # 'after' cursor moves forward even when all items were duplicates.
        if max_played_at:
            if not user_row.last_synced_at or max_played_at > user_row.last_synced_at:
                user_row.last_synced_at = max_played_at

        db.commit()

        if new_plays_count > 0:
            status_str = "ok"
        else:
            # items were returned by Spotify but all were already in the DB
            status_str = "already_up_to_date"

        return {
            "user_id": user_id,
            "new_plays": new_plays_count,
            "new_tracks": new_plays_count,   # alias for frontend
            "status": status_str,
        }

    except Exception as e:
        db.rollback()
        print(f"[spotify_sync] sync_user_recent_plays({user_id}): {e}")
        return {
            "user_id": user_id,
            "new_plays": 0,
            "status": "error",
            "error": str(e),
        }
    finally:
        db.close()
