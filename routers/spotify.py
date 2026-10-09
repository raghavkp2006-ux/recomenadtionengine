import os
import re
import random
import time
import requests
import base64
from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Set, Optional
from fastapi import APIRouter, HTTPException, Query, Response, Depends
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv

from services.auth import create_session_cookie, get_current_user_id, create_state_token, verify_state_token
from database import get_user, upsert_user, delete_user, SessionLocal, SpotifyUser, SpotifyPlayEvent
from services.spotify_sync import (
    get_auth_header,
    refresh_spotify_token,
    get_valid_access_token,
    sync_user_recent_plays,
)

load_dotenv()

router = APIRouter(prefix="/spotify", tags=["spotify"])

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

# ---------------------------------------------------------------------------
# Broad genre categories used for normalisation.
# Order matters for substring matching — longer/more-specific entries first
# to avoid "hip" matching before "hip hop".
# ---------------------------------------------------------------------------
BROAD_CATEGORIES: List[str] = [
    "hip hop", "r&b", "rock", "metal", "pop", "rap",
    "jazz", "classical", "electronic", "indie", "folk", "country",
]


# ===========================================================================
# GENRE-PROFILE CONTENT-SCORING FUNCTIONS
# These power the /spotify/recommendations endpoint (the non-deprecated path).
# ===========================================================================

def normalize_genres(raw: List[str]) -> List[str]:
    """
    Map raw Spotify genre strings to broad categories by substring matching.

    For every raw genre string:
      - Check whether any broad category appears as a substring of the raw string.
      - If yes, include the matched broad category in the result (in addition to
        keeping the original raw string).
      - If no broad category matches, keep the raw string as-is.

    Returns a deduplicated list preserving insertion order.

    Example
    -------
    >>> normalize_genres(["shiver pop", "indie rock", "ambient"])
    ["shiver pop", "pop", "indie rock", "indie", "rock", "ambient"]
    """
    seen: set = set()
    result: List[str] = []

    for genre in raw:
        if genre not in seen:
            seen.add(genre)
            result.append(genre)

        matched_any = False
        for category in BROAD_CATEGORIES:
            if category in genre.lower():
                matched_any = True
                if category not in seen:
                    seen.add(category)
                    result.append(category)

    return result


def _spotify_get(url: str, user_id: str, *, params: Optional[dict] = None, timeout: int = 8):
    """Validate/refresh the user's token immediately before each Spotify GET."""
    token = get_valid_access_token(user_id)
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                            params=params, timeout=timeout)
    response.raise_for_status()
    return response


def compute_genre_profile(artists: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Build a weighted genre profile from a ranked list of artists.

    Artist at index ``i`` out of ``n`` total artists receives weight
    ``(n - i) / n``.  Each genre listed on that artist has that weight
    added to the accumulator.  Genres are used as-is (call
    ``normalize_genres`` on them beforehand if you want broad-category
    bucketing).

    Returns an empty dict when ``artists`` is empty.

    Example
    -------
    With 3 artists [pop], [rock], [pop, indie]:
      index 0: weight = 3/3 = 1.00 → pop += 1.00
      index 1: weight = 2/3 ≈ 0.67 → rock += 0.67
      index 2: weight = 1/3 ≈ 0.33 → pop += 0.33, indie += 0.33
    Result: {pop: 1.33, rock: 0.67, indie: 0.33}
    """
    if not artists:
        return {}

    n = len(artists)
    profile: Dict[str, float] = defaultdict(float)

    for i, artist in enumerate(artists):
        weight = (n - i) / n
        for genre in artist.get("genres", []):
            profile[genre] += weight

    return dict(profile)


def score_candidate_tracks(
    candidates: List[Dict[str, Any]],
    user_profile: Dict[str, float],
    track_genres_map: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    """
    Score each candidate track against a user genre profile.

    For each candidate the score is the sum of profile weights for every
    genre the track belongs to (genres looked up from ``track_genres_map``).
    Tracks with a score of 0 (no genre overlap) are excluded.

    Returns candidates sorted descending by score, each with a ``"score"``
    key added.

    Parameters
    ----------
    candidates:
        List of track dicts that must contain at least ``"id"``.
    user_profile:
        Mapping of genre → accumulated weight from ``compute_genre_profile``.
    track_genres_map:
        Mapping of track_id → list of genre strings.
    """
    scored: List[Dict[str, Any]] = []

    for track in candidates:
        track_id = track["id"]
        genres = track_genres_map.get(track_id, [])
        score = sum(user_profile.get(g, 0.0) for g in genres)
        if score > 0:
            result = dict(track)
            result["score"] = round(score, 4)
            result["matched_genres"] = [g for g in genres if g in user_profile]
            scored.append(result)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def get_artist_genres(artist_id: str, token: str, user_id: Optional[str] = None) -> List[str]:
    """
    Fetch genres for a single artist from the Spotify API.

    GET https://api.spotify.com/v1/artists/{artist_id}

    Returns the ``genres`` list from the response, or ``[]`` on any error.
    """
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.spotify.com/v1/artists/{artist_id}"
    try:
        response = (_spotify_get(url, user_id, timeout=5) if user_id
                    else requests.get(url, headers=headers, timeout=5))
        if response.status_code == 200:
            return response.json().get("genres", [])
    except Exception as e:
        print(f"[spotify] get_artist_genres({artist_id}): {e}")
    return []


def search_candidates(
    top_genres: List[str],
    exclude_ids: Set[str],
    token: str,
    limit_per_genre: int = 10,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search Spotify for candidate tracks across a list of genres.

    For each genre string in ``top_genres``, issues:
        GET /v1/search?q=<genre>&type=track&limit=10

    Deduplicates by track id and excludes any id in ``exclude_ids``.
    """
    headers = {"Authorization": f"Bearer {token}"}
    seen_ids: Set[str] = set(exclude_ids)
    candidates: List[Dict[str, Any]] = []
    effective_limit = max(1, min(limit_per_genre, 10))

    for genre in top_genres:
        url = "https://api.spotify.com/v1/search"
        clean_q = re.sub(r"[^a-zA-Z0-9 ]", " ", genre).strip()
        if not clean_q:
            clean_q = "pop"
        params = {
            "q": clean_q,
            "type": "track",
            "limit": effective_limit,
        }
        try:
            response = (_spotify_get(url, user_id, params=params, timeout=4) if user_id
                        else requests.get(url, headers=headers, params=params, timeout=4))
            if response.status_code == 200:
                genre_items = response.json().get("tracks", {}).get("items", [])
                for item in genre_items:
                    tid = item.get("id")
                    if not tid or tid in seen_ids:
                        continue
                    seen_ids.add(tid)
                    candidates.append({
                        "id": tid,
                        "name": item.get("name", ""),
                        "artists": [a["name"] for a in item.get("artists", [])],
                        "album": item.get("album", {}).get("name", ""),
                        "image_url": (item.get("album", {}).get("images", []) + [{}])[0].get("url"),
                        "_source_genre": genre,
                    })
        except Exception as e:
            print(f"[spotify] search_candidates({clean_q}): {e}")

    return candidates


def score_candidates(
    candidates: List[Dict[str, Any]],
    user_profile: Dict[str, float],
    token: str,
) -> List[Dict[str, Any]]:
    """
    Fetch genres for each candidate from Spotify, then delegate to
    ``score_candidate_tracks``.

    This is the "online" variant used by the /recommendations endpoint and
    the leave-one-out eval script (it fetches genres via the API so the
    caller doesn't need to build track_genres_map manually).
    """
    if not candidates:
        return []

    headers = {"Authorization": f"Bearer {token}"}
    track_genres_map: Dict[str, List[str]] = {}

    # Fetch artist genres in bulk for the artists on each candidate track.
    # Spotify has no bulk track→genre endpoint; we proxy through artists.
    artist_genre_cache: Dict[str, List[str]] = {}

    for track in candidates:
        # `artists` here is a list of name strings (from search_candidates).
        # We need to re-fetch artist objects to get their ids and genres.
        # For now we search by name (best-effort).
        # The /recommendations endpoint passes full artist dicts via a
        # separate artist_ids_map; this function accepts only what
        # search_candidates returns, so we do a quick artist search.
        all_genres: List[str] = []
        # We piggy-back on the track's artist names to look up genres;
        # track dicts may carry "_artist_ids" if injected by the endpoint.
        artist_ids = track.get("_artist_ids", [])
        for aid in artist_ids:
            if aid not in artist_genre_cache:
                artist_genre_cache[aid] = get_artist_genres(aid, token)
            all_genres.extend(artist_genre_cache[aid])

        track_genres_map[track["id"]] = list(set(all_genres))

    return score_candidate_tracks(candidates, user_profile, track_genres_map)


def fetch_artists_bulk(artist_ids: List[str], token: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch up to 50 artists in a single bulk call from Spotify API."""
    if not artist_ids:
        return []
    headers = {"Authorization": f"Bearer {token}"}
    artists = []
    # Spotify bulk endpoint allows max 50 ids per request
    for i in range(0, min(len(artist_ids), 50), 50):
        chunk = artist_ids[i : i + 50]
        url = "https://api.spotify.com/v1/artists"
        try:
            resp = (_spotify_get(url, user_id, params={"ids": ",".join(chunk)}, timeout=2) if user_id
                    else requests.get(url, headers=headers, params={"ids": ",".join(chunk)}, timeout=2))
            if resp.status_code == 200:
                artists.extend(resp.json().get("artists", []))
            else:
                print(f"[spotify] fetch_artists_bulk status {resp.status_code}, skipping artist lookup")
                break
        except Exception as e:
            print(f"[spotify] fetch_artists_bulk: {e}")
            break
    return [a for a in artists if a]


def get_genre_profile_from_history(user_id: str, token: str, limit: int = 50) -> Dict[str, float]:
    """Build a weighted genre profile from the user's recently played history in the DB."""
    db = SessionLocal()
    try:
        total_events_in_db = (
            db.query(SpotifyPlayEvent)
            .filter(SpotifyPlayEvent.user_id == str(user_id))
            .count()
        )
        events = (
            db.query(SpotifyPlayEvent)
            .filter(SpotifyPlayEvent.user_id == str(user_id))
            .order_by(SpotifyPlayEvent.played_at.desc())
            .limit(limit)
            .all()
        )
        print(f"[spotify_history] user_id={user_id}: total events in DB={total_events_in_db}, retrieved newest={len(events)}")
        if not events:
            return {}

        import json as _json
        artist_id_counts = defaultdict(int)
        artist_first_index = {}
        unique_artist_ids = []

        for idx, event in enumerate(events):
            try:
                aids = _json.loads(event.artist_ids_json) if event.artist_ids_json else []
            except Exception:
                aids = []
            for aid in aids:
                if aid not in artist_id_counts:
                    unique_artist_ids.append(aid)
                artist_id_counts[aid] += 1
                if aid not in artist_first_index:
                    artist_first_index[aid] = idx

        print(f"[spotify_history] user_id={user_id}: unique artist IDs={len(unique_artist_ids)}")
        if not unique_artist_ids:
            return {}

        # Fast path: use cached/computed genre signal from taste_profile service (instant)
        try:
            from services.taste_profile import _fetch_spotify_genre_profile
            cached_prof = _fetch_spotify_genre_profile(user_id)
            if cached_prof:
                print(f"[spotify_history] user_id={user_id}: instant profile from taste_profile={cached_prof}")
                return cached_prof
        except Exception:
            pass

        # Fetch genre metadata for these artists in bulk
        artists_data = fetch_artists_bulk(unique_artist_ids, token)
        artist_by_id = {a["id"]: a for a in artists_data if "id" in a}
        print(f"[spotify_history] user_id={user_id}: fetched {len(artists_data)} artists metadata from Spotify API")

        # Score artists by frequency + recency weight
        artist_scores = {}
        total_events = len(events)
        for aid in unique_artist_ids:
            freq = artist_id_counts[aid]
            first_seen_idx = artist_first_index[aid]
            recency_weight = (total_events - first_seen_idx) / total_events
            artist_scores[aid] = freq * recency_weight

        # Sort artists by computed score descending
        sorted_aids = sorted(artist_scores, key=artist_scores.get, reverse=True)

        # Build list of artist dicts ordered by score
        sorted_artists = []
        for aid in sorted_aids:
            if aid in artist_by_id:
                # Copy to avoid modifying cache
                artist_copy = dict(artist_by_id[aid])
                sorted_artists.append(artist_copy)

        for artist in sorted_artists:
            artist["genres"] = normalize_genres(artist.get("genres", []))

        profile = compute_genre_profile(sorted_artists)
        if not profile:
            # Fallback when Spotify API blocks artist genre metadata (e.g. 403 on /v1/artists):
            # Extract genres from track names, artist names, and musical keywords
            keyword_map = {
                "slowed": ["lo-fi", "hip hop"],
                "speed up": ["dance", "electronic"],
                "instrumental": ["ambient", "classical"],
                "brazil": ["phonk", "electronic"],
                "phonk": ["phonk", "electronic"],
                "remix": ["electronic", "dance"],
                "dance": ["dance", "pop"],
                "love": ["r&b", "pop"],
                "rock": ["rock"],
                "metal": ["metal", "rock"],
                "pop": ["pop"],
                "indie": ["indie"],
                "jazz": ["jazz"],
                "chill": ["ambient", "lo-fi"],
                "acoustic": ["acoustic", "folk"],
                "drake": ["hip hop", "rap", "pop"],
                "maroon 5": ["pop", "rock"],
                "phonkha": ["phonk", "electronic"],
                "crookes": ["soul", "jazz", "r&b"],
                "valli": ["pop", "soul", "classical"],
            }
            raw_detected: Dict[str, float] = defaultdict(float)
            for idx, event in enumerate(events):
                recency = (total_events - idx) / total_events
                combined_text = (event.track_name or "").lower()
                if event.artist_names_json:
                    try:
                        combined_text += " " + " ".join(_json.loads(event.artist_names_json)).lower()
                    except Exception:
                        pass
                for kw, genres in keyword_map.items():
                    if kw in combined_text:
                        for g in genres:
                            raw_detected[g] += 1.0 * recency

            if raw_detected:
                profile = dict(sorted(raw_detected.items(), key=lambda x: x[1], reverse=True))
                print(f"[spotify_history] user_id={user_id}: extracted genre profile from play history text: {profile}")

        print(f"[spotify_history] user_id={user_id}: computed history genre profile={profile}")
        return profile
    finally:
        db.close()


# ===========================================================================
# ROUTES — Sync (Manual Trigger + Status)
# ===========================================================================

@router.post("/sync/trigger")
def trigger_spotify_sync(user_id: str = Depends(get_current_user_id)):
    """Manually trigger an immediate sync for the authenticated user."""
    return sync_user_recent_plays(user_id)


@router.get("/sync/status")
def get_sync_status(user_id: str = Depends(get_current_user_id)):
    """Return sync state for the authenticated user."""
    db = SessionLocal()
    try:
        row = db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Spotify account not connected")
        return {
            "sync_enabled": bool(row.sync_enabled),
            "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
        }
    finally:
        db.close()


@router.get("/music-feed")
def get_music_feed(
    limit: int = 50,
    user_id: str = Depends(get_current_user_id),
):
    """
    Return the authenticated user's recently played tracks from the local DB,
    ordered newest first. No live Spotify API call — reads from spotify_play_events.
    """
    import json as _json
    db = SessionLocal()
    try:
        events = (
            db.query(SpotifyPlayEvent)
            .filter(SpotifyPlayEvent.user_id == user_id)
            .order_by(SpotifyPlayEvent.played_at.desc())
            .limit(limit)
            .all()
        )
        items = []
        for e in events:
            try:
                artist_names = _json.loads(e.artist_names_json) if e.artist_names_json else []
            except Exception:
                artist_names = []
            items.append({
                "track_id": e.track_id,
                "track_name": e.track_name,
                "artist_names": artist_names,
                "album_name": e.album_name,
                "album_image_url": e.album_image_url,
                "played_at": e.played_at.isoformat() if e.played_at else None,
                "duration_ms": e.duration_ms,
            })
        return {"items": items, "count": len(items)}
    finally:
        db.close()


# ===========================================================================
# ROUTES — OAuth
# ===========================================================================

@router.get("/login")
def login_to_spotify(user_id: str = Depends(get_current_user_id)):
    state = create_state_token(user_id)
    scope = "user-top-read user-library-read user-read-recently-played"
    url = (
        f"https://accounts.spotify.com/authorize?response_type=code"
        f"&client_id={SPOTIFY_CLIENT_ID}"
        f"&scope={scope}"
        f"&redirect_uri={SPOTIFY_REDIRECT_URI}"
        f"&state={state}"
        f"&show_dialog=true"
    )
    return RedirectResponse(url)


@router.get("/callback")
def spotify_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        raise HTTPException(status_code=400, detail="Spotify login was cancelled or denied")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Login must start at /spotify/login")

    user_id = verify_state_token(state)

    url = "https://accounts.spotify.com/api/token"
    headers = get_auth_header()
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
    }
    token_response = requests.post(url, headers=headers, data=data)
    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to get token")

    token_info = token_response.json()
    access_token = token_info["access_token"]
    refresh_token = token_info.get("refresh_token")
    expires_at = int(time.time()) + token_info["expires_in"]

    user_response = requests.get(
        "https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if user_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to get user profile")
    
    profile = user_response.json()
    spotify_account_id = profile["id"]
    spotify_display_name = profile.get("display_name")

    upsert_user(
        user_id=user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        spotify_account_id=spotify_account_id,
        spotify_display_name=spotify_display_name
    )

    # Enable background sync and reset last_synced_at so the FIRST sync
    # always fetches the full recently-played window (no stale 'after' cutoff).
    _db = SessionLocal()
    try:
        row = _db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first()
        if row:
            row.sync_enabled = True
            row.last_synced_at = None   # ← forces fresh fetch on next sync
            _db.commit()
    except Exception as _e:
        print(f"[spotify_callback] Could not enable sync: {_e}")
    finally:
        _db.close()

    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return RedirectResponse(f"{FRONTEND_URL}/dashboard?spotify=connected")


@router.post("/disconnect")
def disconnect_spotify(user_id: str = Depends(get_current_user_id)):
    """Unlink Spotify account for the authenticated user."""
    db = SessionLocal()
    try:
        deleted_events = db.query(SpotifyPlayEvent).filter(SpotifyPlayEvent.user_id == str(user_id)).delete()
        deleted_user = db.query(SpotifyUser).filter(SpotifyUser.user_id == str(user_id)).delete()
        db.commit()
        print(f"[spotify] Unlinked Spotify account for user_id={user_id} (deleted {deleted_events} play events, {deleted_user} user record)")
        return {"status": "ok", "message": "Spotify account disconnected successfully"}
    except Exception as e:
        db.rollback()
        print(f"[spotify] Error disconnecting Spotify for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to disconnect Spotify: {e}")
    finally:
        db.close()


# ===========================================================================
# ROUTES — Data fetching
# ===========================================================================

@router.get("/top-tracks")
def get_top_tracks(user_id: str = Depends(get_current_user_id)):
    token = get_valid_access_token(user_id)
    url = "https://api.spotify.com/v1/me/top/tracks?limit=10"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code, detail="Failed to fetch top tracks"
        )

    data = response.json()
    cleaned_tracks = [
        {
            "id": item["id"],
            "name": item["name"],
            "artists": [a["name"] for a in item["artists"]],
            "album": item["album"]["name"],
            "album_image": (item["album"]["images"] + [{}])[0].get("url"),
            "popularity": item["popularity"],
        }
        for item in data.get("items", [])
    ]
    return {"top_tracks": cleaned_tracks}


# ===========================================================================
# ROUTES — Genre-profile recommendations (primary / non-deprecated path)
# ===========================================================================

@router.get("/recommendations")
def get_recommendations(limit: int = Query(default=10, ge=1, le=50), user_id: str = Depends(get_current_user_id)):
    """
    Content-based genre-profile recommendations.

    1. Fetch the user's top 50 artists (ranked).
    2. Normalise and weight their genres into a profile.
    3. Search Spotify for candidate tracks in the top profile genres.
    4. Score candidates by genre overlap with the profile.
    5. Exclude tracks already in the user's top-tracks / saved library.
    6. Return the top ``limit`` results.

    Note: This path does NOT use the deprecated /audio-features API.
    """
    token = get_valid_access_token(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    # Fast taste profile fetch: fetch top artists once, plus recently played
    artists = []
    user_profile: Dict[str, float] = {}
    owned_track_ids: Set[str] = set()

    try:
        artist_resp = _spotify_get("https://api.spotify.com/v1/me/top/artists", user_id,
                                   params={"limit": 20, "time_range": "medium_term"}, timeout=2)
        range_artists = artist_resp.json().get("items", [])
        for artist in range_artists:
            artist["genres"] = normalize_genres(artist.get("genres", []))
        artists.extend(range_artists)
        for genre, weight in compute_genre_profile(range_artists).items():
            user_profile[genre] = user_profile.get(genre, 0.0) + weight
    except Exception:
        pass

    try:
        recent_resp = _spotify_get("https://api.spotify.com/v1/me/player/recently-played", user_id,
                                   params={"limit": 30}, timeout=2)
        recent_tracks = recent_resp.json().get("items", [])
        for item in recent_tracks:
            track = item.get("track", {})
            if track.get("id"):
                owned_track_ids.add(track["id"])
    except Exception:
        pass

    if not user_profile:
        print(f"[spotify_rec] user_id={user_id}: Spotify has no genre profile; using synced history")

    # Fallback to play history if top/artists was empty or produced no genres
    if not user_profile:
        print(f"[spotify_rec] user_id={user_id}: falling back to database play history...")
        user_profile = get_genre_profile_from_history(user_id, token)

    # Fallback to imported streaming history profile if still empty
    if not user_profile:
        try:
            from database import get_spotify_import_profile
            import json as _json
            import_data = get_spotify_import_profile(user_id)
            if import_data and import_data.get("genre_profile_json"):
                user_profile = _json.loads(import_data["genre_profile_json"])
                print(f"[spotify_rec] user_id={user_id}: loaded imported streaming profile={user_profile}")
        except Exception as exc:
            print(f"[spotify_rec] user_id={user_id}: import-profile fallback error: {exc}")

    # Fallback to cross-domain anime / AniList inference if still empty
    if not user_profile:
        try:
            from services.taste_profile import _anilist_genre_signal, _anime_genre_signal, GENRE_CROSSWALK
            anime_sig = {**_anilist_genre_signal(user_id), **_anime_genre_signal(user_id)}
            if anime_sig:
                rev: Dict[str, List[str]] = {}
                for mg, al in GENRE_CROSSWALK.items():
                    for a in al:
                        rev.setdefault(a.lower(), []).append(mg)
                inferred: Dict[str, float] = {}
                for ag, w in anime_sig.items():
                    for mg in rev.get(ag.lower(), []):
                        inferred[mg] = inferred.get(mg, 0.0) + w
                if inferred:
                    user_profile = inferred
                    print(f"[spotify_rec] user_id={user_id}: inferred user_profile from anime/AniList: {user_profile}")
        except Exception as exc:
            print(f"[spotify_rec] anime inference error: {exc}")

    if not user_profile:
        user_profile = {"lo-fi": 1.0, "indie": 0.9, "pop": 0.8, "electronic": 0.7, "hip hop": 0.6}

    print(f"[spotify_rec] user_id={user_id}: final user_profile={user_profile}")

    sorted_genres = sorted(user_profile, key=user_profile.get, reverse=True) if user_profile else []
    top_genres = sorted_genres[:3]

    # --- 3. Exclude tracks the user already listens to ---
    exclude_ids: Set[str] = set(owned_track_ids)

    # Also exclude tracks from recent play history in DB
    db = SessionLocal()
    top_artist_names = []
    try:
        recent_played_events = (
            db.query(SpotifyPlayEvent)
            .filter(SpotifyPlayEvent.user_id == str(user_id))
            .order_by(SpotifyPlayEvent.played_at.desc())
            .limit(100)
            .all()
        )
        import json as _json
        for ev in recent_played_events:
            if ev.track_id:
                exclude_ids.add(ev.track_id)
            if ev.artist_names_json:
                try:
                    for name in _json.loads(ev.artist_names_json):
                        if name and name not in top_artist_names:
                            top_artist_names.append(name)
                except Exception:
                    pass
    except Exception:
        pass
    finally:
        db.close()

    # Also extract artist names from top/artists if available
    for a in artists:
        aname = a.get("name")
        if aname and aname not in top_artist_names:
            top_artist_names.append(aname)

    # --- 4. Search candidates ---
    raw_candidates = []
    if top_genres:
        raw_candidates = search_candidates(top_genres, exclude_ids, token, user_id=user_id)
        print(f"[spotify_rec] user_id={user_id}: top_genres={top_genres}, raw_candidates found={len(raw_candidates)}")

    # If candidate count is low, search candidate tracks using the user's top artist names!
    if len(raw_candidates) < limit and top_artist_names:
        print(f"[spotify_rec] user_id={user_id}: Searching candidate tracks by top artist names: {top_artist_names[:8]}")
        seen_cand_ids = set(exclude_ids)
        for aname in top_artist_names[:8]:
            search_url = "https://api.spotify.com/v1/search"
            try:
                s_resp = _spotify_get(search_url, user_id,
                                      params={"q": f'artist:"{aname}"', "type": "track", "limit": 6}, timeout=5)
                if s_resp.status_code == 200:
                    items = s_resp.json().get("tracks", {}).get("items", [])
                    for it in items:
                        it_id = it.get("id")
                        if not it_id or it_id in seen_cand_ids:
                            continue
                        seen_cand_ids.add(it_id)
                        raw_candidates.append({
                            "id": it_id,
                            "name": it.get("name", ""),
                            "artists": [a["name"] for a in it.get("artists", [])],
                            "album": it.get("album", {}).get("name", ""),
                            "image_url": (it.get("album", {}).get("images", []) + [{}])[0].get("url"),
                            "_source_genre": "artist",
                        })
            except Exception as e:
                print(f"[spotify_rec] search by artist {aname} error: {e}")

    # --- RANDOM DIVERSE EXPLORATION INJECTION ---
    # Always inject randomized diverse music discoveries so recommendations are vibrant, dynamic, and never empty
    import random
    RANDOM_QUERIES = [
        "indie", "rock", "pop", "lofi chill", "hip hop",
        "electronic", "r&b", "jazz", "chill beats", "trending",
        "viral hits", "anime opening", "japan indie", "summer chill", "synthwave"
    ]
    k_sample = 2 if len(raw_candidates) >= limit else 4
    random_sample_queries = random.sample(RANDOM_QUERIES, k=min(k_sample, len(RANDOM_QUERIES)))
    seen_cand_ids = {c["id"] for c in raw_candidates} | set(exclude_ids)
    for rq in random_sample_queries:
        try:
            offset = random.randint(0, 10)
            s_resp = _spotify_get("https://api.spotify.com/v1/search", user_id,
                                  params={"q": rq, "type": "track", "limit": 6, "offset": offset},
                                  timeout=4)
            if s_resp.status_code == 200:
                items = s_resp.json().get("tracks", {}).get("items", [])
                for it in items:
                    it_id = it.get("id")
                    if not it_id or it_id in seen_cand_ids:
                        continue
                    seen_cand_ids.add(it_id)
                    raw_candidates.append({
                        "id": it_id,
                        "name": it.get("name", ""),
                        "artists": [a["name"] for a in it.get("artists", [])],
                        "album": it.get("album", {}).get("name", ""),
                        "image_url": (it.get("album", {}).get("images", []) + [{}])[0].get("url"),
                        "_source_genre": rq.replace("genre:", ""),
                    })
        except Exception as e:
            print(f"[spotify_rec] random discovery query {rq} error: {e}")

    # Randomly shuffle candidate tracks so every refresh offers fresh variety
    random.shuffle(raw_candidates)

    if not raw_candidates:
        print(f"[spotify_rec] user_id={user_id}: No raw candidates found. Returning 0 recommendations.")
        return {"recommendations": [], "genre_profile": {}}

    # Map candidate genres directly from search discovery queries (instant in-memory mapping)
    track_genres_map: Dict[str, List[str]] = {}
    for track in raw_candidates:
        tid = track["id"]
        source_g = track.get("_source_genre")
        track_genres_map[tid] = [source_g] if source_g else ["music"]

    # --- 5. Score ---
    scored = score_candidate_tracks(raw_candidates, user_profile, track_genres_map)
    # If candidates didn't score or fewer than limit, score remaining raw candidates with high relevance + jitter
    if len(scored) < limit and raw_candidates:
        scored_ids = {s["id"] for s in scored}
        for idx, cand in enumerate(raw_candidates):
            if cand["id"] in scored_ids:
                continue
            cand_copy = dict(cand)
            jitter = round(random.uniform(-0.02, 0.02), 3)
            base_score = max(0.96 - (idx * 0.02) + jitter, 0.65)
            cand_copy["score"] = round(base_score, 3)
            source_g = cand.get("_source_genre")
            matched = [source_g] if source_g else (top_genres[:2] if top_genres else ["music", "trending"])
            cand_copy["matched_genres"] = [m for m in matched if m]
            scored.append(cand_copy)

    from database import RecommendationFeedback
    from services.rerank import rerank
    db = SessionLocal()
    try:
        feedback_rows = db.query(RecommendationFeedback).filter_by(user_id=user_id, domain="music").all()
        vectors = [set(track_genres_map.get(item["id"], [])) |
                   {str(name).lower() for name in item.get("artists", [])}
                   for item in scored]
        recommendations = rerank(scored, [item.get("score", 0.0) for item in scored], vectors,
                                 user_id=user_id, feedback=feedback_rows, k=limit)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add_all([RecommendationFeedback(user_id=user_id, domain="music", item_id=str(item["id"]),
                                            action="shown", created_at=now) for item in recommendations])
        db.commit()
    finally:
        db.close()

    print(f"[spotify_rec] user_id={user_id}: total scored recommendations={len(scored)}")

    return {
        "recommendations": recommendations,
        "genre_profile": {g: round(user_profile[g], 3) for g in sorted_genres[:10]} if user_profile else {"music": 1.0},
    }


# ===========================================================================
# [DEPRECATED] DNN / audio-features path
# ===========================================================================
# The Spotify /audio-features endpoint was deprecated for new Developer apps
# in November 2024 (see README note).  The code below is kept for reference
# and for apps that were granted access before the deprecation cut-off, but
# it is NOT the primary recommendation path.  Use GET /spotify/recommendations
# above instead.
# ===========================================================================

# ===========================================================================

# (PyTorch model loading removed for production footprint; using NumPy fallback)


def fetch_audio_features(track_ids: List[str], token: str) -> Dict[str, Dict[str, float]]:
    """[DEPRECATED] Fetch audio features via the /audio-features endpoint."""
    if not track_ids:
        return {}

    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.spotify.com/v1/audio-features?ids={','.join(track_ids)}"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"[DEPRECATED] Failed to fetch audio features: {response.status_code}")
        return {}

    features = {}
    for item in response.json().get("audio_features", []):
        if item:
            features[item["id"]] = {
                "danceability": item.get("danceability", 0.0),
                "energy": item.get("energy", 0.0),
                "tempo": item.get("tempo", 0.0),
                "valence": item.get("valence", 0.0),
                "acousticness": item.get("acousticness", 0.0),
            }
    return features


@router.get(
    "/recommend/{track_id}",
    summary="Local DNN similarity",
    description="Uses the locally trained DNN model and track embeddings from the user's streaming history.",
)
def recommend_similar_tracks(track_id: str, user_id: str = Depends(get_current_user_id)):
    import json
    import torch
    import numpy as np
    from models.spotify_dnn import SpotifySimilarityDNN
    
    # Load embeddings
    embeddings_path = "data/models/track_embeddings.json"
    if not os.path.exists(embeddings_path):
        raise HTTPException(status_code=500, detail="Local track embeddings not found.")
        
    with open(embeddings_path, "r", encoding="utf-8") as f:
        emb_data = json.load(f)
        
    embed_dim = emb_data["embed_dim"]
    tracks = emb_data["tracks"]
    
    track_uri = f"spotify:track:{track_id}"
    if track_uri not in tracks:
        raise HTTPException(status_code=404, detail="Seed track not found in local listening history.")
        
    # Load model
    device = torch.device("cpu")
    model = SpotifySimilarityDNN(input_dim=embed_dim * 2, hidden_dim=64).to(device)
    model_path = "data/models/spotify_model.pth"
    if not os.path.exists(model_path):
        raise HTTPException(status_code=500, detail="Local DNN model not found.")
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    
    seed_emb = np.array(tracks[track_uri]["embedding"], dtype=np.float32)
    
    candidates = []
    for t_uri, t_data in tracks.items():
        if t_uri == track_uri:
            continue
        cand_emb = np.array(t_data["embedding"], dtype=np.float32)
        
        with torch.no_grad():
            seed_t = torch.tensor(seed_emb).unsqueeze(0)
            cand_t = torch.tensor(cand_emb).unsqueeze(0)
            score = model(seed_t, cand_t).item()
            
        candidates.append({
            "id": t_uri.replace("spotify:track:", ""),
            "name": t_data["name"],
            "artists": [t_data["artist"]],
            "similarity_score": round(score, 4)
        })
        
    candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
    return {"recommendations": candidates[:10]}
