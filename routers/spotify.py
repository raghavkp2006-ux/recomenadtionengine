import os
import time
import requests
import base64
from collections import defaultdict
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


def get_artist_genres(artist_id: str, token: str) -> List[str]:
    """
    Fetch genres for a single artist from the Spotify API.

    GET https://api.spotify.com/v1/artists/{artist_id}

    Returns the ``genres`` list from the response, or ``[]`` on any error.
    """
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.spotify.com/v1/artists/{artist_id}"
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json().get("genres", [])
    except Exception as e:
        print(f"[spotify] get_artist_genres({artist_id}): {e}")
    return []


def search_candidates(
    top_genres: List[str],
    exclude_ids: Set[str],
    token: str,
    limit_per_genre: int = 20,
) -> List[Dict[str, Any]]:
    """
    Search Spotify for candidate tracks across a list of genres.

    For each genre string in ``top_genres``, issues:
        GET /v1/search?q=genre:"<genre>"&type=track&limit=<limit_per_genre>

    Deduplicates by track id and excludes any id in ``exclude_ids``.

    Returns a list of track dicts with keys: id, name, artists (list of
    artist name strings), album.
    """
    headers = {"Authorization": f"Bearer {token}"}
    seen_ids: Set[str] = set(exclude_ids)
    candidates: List[Dict[str, Any]] = []

    for genre in top_genres:
        url = "https://api.spotify.com/v1/search"
        # Try genre query with quotes first, then fallback to raw genre term
        queries = [f'genre:"{genre}"', genre]
        genre_items = []
        for q in queries:
            params = {
                "q": q,
                "type": "track",
                "limit": limit_per_genre,
            }
            try:
                response = requests.get(url, headers=headers, params=params, timeout=5)
                if response.status_code == 200:
                    items = response.json().get("tracks", {}).get("items", [])
                    if items:
                        genre_items = items
                        break
                else:
                    print(f"[spotify] search_candidates: {response.status_code} for query={q}")
            except Exception as e:
                print(f"[spotify] search_candidates({q}): {e}")

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
            })

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


def fetch_artists_bulk(artist_ids: List[str], token: str) -> List[Dict[str, Any]]:
    """Fetch up to 50 artists in a single bulk call from Spotify API."""
    if not artist_ids:
        return []
    headers = {"Authorization": f"Bearer {token}"}
    artists = []
    # Spotify bulk endpoint allows max 50 ids per request
    for i in range(0, len(artist_ids), 50):
        chunk = artist_ids[i : i + 50]
        url = f"https://api.spotify.com/v1/artists?ids={','.join(chunk)}"
        try:
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code == 200:
                artists.extend(resp.json().get("artists", []))
            else:
                print(f"[spotify] fetch_artists_bulk error: status {resp.status_code}")
        except Exception as e:
            print(f"[spotify] fetch_artists_bulk exception: {e}")
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

    # --- 1. Fetch top artists ---
    artists = []
    try:
        artists_resp = requests.get(
            "https://api.spotify.com/v1/me/top/artists?limit=50", headers=headers, timeout=6
        )
        if artists_resp.status_code == 200:
            artists = artists_resp.json().get("items", [])
        else:
            print(f"[spotify_rec] user_id={user_id}: me/top/artists returned HTTP {artists_resp.status_code}")
    except Exception as e:
        print(f"[spotify_rec] user_id={user_id}: me/top/artists error: {e}")

    user_profile: Dict[str, float] = {}
    if artists:
        for artist in artists:
            artist["genres"] = normalize_genres(artist.get("genres", []))
        user_profile = compute_genre_profile(artists)
        print(f"[spotify_rec] user_id={user_id}: top artists count={len(artists)}, computed profile={user_profile}")

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

    print(f"[spotify_rec] user_id={user_id}: final user_profile={user_profile}")

    sorted_genres = sorted(user_profile, key=user_profile.get, reverse=True) if user_profile else []
    top_genres = sorted_genres[:5]

    # --- 3. Build exclusion set from user's own top tracks ---
    exclude_ids: Set[str] = set()
    try:
        top_tracks_resp = requests.get(
            "https://api.spotify.com/v1/me/top/tracks?limit=50", headers=headers, timeout=6
        )
        if top_tracks_resp.status_code == 200:
            exclude_ids = {t["id"] for t in top_tracks_resp.json().get("items", [])}
    except Exception as e:
        print(f"[spotify_rec] user_id={user_id}: top/tracks exclusion error: {e}")

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
        raw_candidates = search_candidates(top_genres, exclude_ids, token)
        print(f"[spotify_rec] user_id={user_id}: top_genres={top_genres}, raw_candidates found={len(raw_candidates)}")

    # If genre search returned no candidates OR user_profile had no genres (Spotify API lockdown),
    # search candidate tracks using the user's top artist names!
    if not raw_candidates and top_artist_names:
        print(f"[spotify_rec] user_id={user_id}: Searching candidate tracks by top artist names: {top_artist_names[:8]}")
        seen_cand_ids = set(exclude_ids)
        for aname in top_artist_names[:8]:
            search_url = "https://api.spotify.com/v1/search"
            try:
                s_resp = requests.get(
                    search_url,
                    headers=headers,
                    params={"q": f'artist:"{aname}"', "type": "track", "limit": 6},
                    timeout=5,
                )
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
                        })
            except Exception as e:
                print(f"[spotify_rec] search by artist {aname} error: {e}")

    if not raw_candidates:
        print(f"[spotify_rec] user_id={user_id}: No raw candidates found. Returning 0 recommendations.")
        return {"recommendations": [], "genre_profile": {}}

    # Simpler: re-fetch track details for all candidate ids in one batch
    candidate_ids = [t["id"] for t in raw_candidates]
    CHUNK = 50
    track_details: Dict[str, Any] = {}
    artist_genre_cache: Dict[str, List[str]] = {}
    track_genres_map: Dict[str, List[str]] = {}

    for i in range(0, len(candidate_ids), CHUNK):
        chunk = candidate_ids[i : i + CHUNK]
        try:
            resp = requests.get(
                f"https://api.spotify.com/v1/tracks?ids={','.join(chunk)}",
                headers=headers,
                timeout=6,
            )
            if resp.status_code == 200:
                for t in resp.json().get("tracks", []) or []:
                    if t:
                        track_details[t["id"]] = t
        except Exception as e:
            print(f"[spotify_rec] tracks details error: {e}")

    # Fetch genres per artist (cached)
    for track in raw_candidates:
        tid = track["id"]
        detail = track_details.get(tid, {})
        all_genres: List[str] = []
        for artist_obj in detail.get("artists", []):
            aid = artist_obj.get("id")
            if aid:
                if aid not in artist_genre_cache:
                    artist_genre_cache[aid] = normalize_genres(
                        get_artist_genres(aid, token)
                    )
                all_genres.extend(artist_genre_cache[aid])
        track_genres_map[tid] = list(set(all_genres))

    # --- 5. Score ---
    scored = score_candidate_tracks(raw_candidates, user_profile, track_genres_map)
    # If no candidate scored (e.g. artist genres missing from Spotify), score based on candidate list order and artist presence
    if not scored and raw_candidates:
        print(f"[spotify_rec] user_id={user_id}: No candidates scored by artist genre overlap; falling back to artist candidate ranking")
        for idx, cand in enumerate(raw_candidates):
            cand_copy = dict(cand)
            cand_copy["score"] = round(max(0.95 - (idx * 0.03), 0.5), 3)
            cand_copy["matched_genres"] = top_genres[:2] if top_genres else ["music"]
            scored.append(cand_copy)

    print(f"[spotify_rec] user_id={user_id}: total scored recommendations={len(scored)}")

    return {
        "recommendations": scored[:limit],
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
