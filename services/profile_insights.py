"""Taste insights computation engine: entropy, genre radar, evolution, and personality."""

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import SessionLocal, SpotifyUser, SpotifyPlayEvent
from services.spotify_sync import get_valid_access_token


_INSIGHTS_CACHE: Dict[Tuple[str, str], Tuple[float, Dict[str, Any]]] = {}
CACHE_TTL = 600  # 10 minutes


def compute_shannon_entropy_diversity(weights: List[float]) -> float:
    """
    Compute normalized Shannon entropy:
      H = - sum(p_i * ln(p_i))
      diversity = H / ln(num_genres) for num_genres >= 2, else 0.0.
    """
    total = sum(weights)
    if total <= 0:
        return 0.0
    p = [w / total for w in weights if w > 0]
    num_items = len(p)
    if num_items < 2:
        return 0.0
    entropy = -sum(pi * math.log(pi) for pi in p)
    max_entropy = math.log(num_items)
    if max_entropy <= 0:
        return 0.0
    diversity = entropy / max_entropy
    return round(max(0.0, min(1.0, diversity)), 4)


def _spotify_api_get(token: str, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=10)
    if resp.status_code == 401:
        raise PermissionError("Spotify token expired or invalid")
    resp.raise_for_status()
    return resp.json()


def compute_profile_insights(
    user_id: str,
    time_range_key: str = "medium",
    refresh: bool = False,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Compute music & taste insights for the requested range (short | medium | long).
    Returns cached result if fresh within 10 minutes unless refresh=True.
    """
    cache_key = (user_id, time_range_key)
    now = time.time()
    if not refresh and cache_key in _INSIGHTS_CACHE:
        cached_time, cached_val = _INSIGHTS_CACHE[cache_key]
        if now - cached_time < CACHE_TTL:
            return cached_val

    range_map = {
        "short": "short_term",
        "medium": "medium_term",
        "long": "long_term",
    }
    spotify_range = range_map.get(time_range_key, "medium_term")

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Check Spotify account
        spotify_row = db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first()
        if not spotify_row:
            result = _empty_or_partial_insights(user_id, db, status="needs_reconnect", range_key=time_range_key)
            _INSIGHTS_CACHE[cache_key] = (now, result)
            return result

        try:
            token = get_valid_access_token(user_id)
        except Exception:
            result = _empty_or_partial_insights(user_id, db, status="needs_reconnect", range_key=time_range_key)
            _INSIGHTS_CACHE[cache_key] = (now, result)
            return result

        # 1. Fetch top artists and tracks for the target range
        try:
            top_artists_data = _spotify_api_get(
                token,
                "https://api.spotify.com/v1/me/top/artists",
                params={"limit": 50, "time_range": spotify_range},
            )
            top_tracks_data = _spotify_api_get(
                token,
                "https://api.spotify.com/v1/me/top/tracks",
                params={"limit": 50, "time_range": spotify_range},
            )
            artists_items = top_artists_data.get("items", [])
            tracks_items = top_tracks_data.get("items", [])
        except Exception as e:
            print(f"[profile_insights] Failed to fetch top artists/tracks: {e}")
            result = _empty_or_partial_insights(user_id, db, status="needs_reconnect")
            _INSIGHTS_CACHE[cache_key] = (now, result)
            return result

        # Also fetch short_term and long_term artists for discovery rate & evolution
        short_artists_items = artists_items if spotify_range == "short_term" else []
        long_artists_items = artists_items if spotify_range == "long_term" else []

        if not short_artists_items:
            try:
                s_data = _spotify_api_get(
                    token,
                    "https://api.spotify.com/v1/me/top/artists",
                    params={"limit": 50, "time_range": "short_term"},
                )
                short_artists_items = s_data.get("items", [])
            except Exception:
                short_artists_items = []

        if not long_artists_items:
            try:
                l_data = _spotify_api_get(
                    token,
                    "https://api.spotify.com/v1/me/top/artists",
                    params={"limit": 50, "time_range": "long_term"},
                )
                long_artists_items = l_data.get("items", [])
            except Exception:
                long_artists_items = []

        # 2. Genre weights for current range
        genre_accum: Dict[str, float] = defaultdict(float)
        n_artists = len(artists_items)
        for i, a in enumerate(artists_items):
            rank_weight = (n_artists - i) / n_artists if n_artists > 0 else 1.0
            for g in a.get("genres", []):
                genre_accum[g.lower()] += rank_weight

        total_genre_weight = sum(genre_accum.values())
        top_genres = []
        if total_genre_weight > 0:
            sorted_genres = sorted(genre_accum.items(), key=lambda x: x[1], reverse=True)[:10]
            top_genres = [
                {"genre": g, "weight": round(w / total_genre_weight, 4)}
                for g, w in sorted_genres
            ]

        # 3. Diversity
        genre_weights_list = [item["weight"] for item in top_genres]
        diversity = compute_shannon_entropy_diversity(genre_weights_list)

        # 4. Mainstream score & Obscurity score
        all_popularities: List[int] = []
        for a in artists_items:
            if "popularity" in a and a["popularity"] is not None:
                all_popularities.append(int(a["popularity"]))
        for t in tracks_items:
            if "popularity" in t and t["popularity"] is not None:
                all_popularities.append(int(t["popularity"]))

        mainstream_score = (
            round(sum(all_popularities) / len(all_popularities), 1)
            if all_popularities
            else 50.0
        )
        obscurity_score = round(100.0 - mainstream_score, 1)

        # 5. Rarest artist & track
        rarest_artist = None
        if artists_items:
            sorted_by_pop = sorted(
                artists_items,
                key=lambda a: a.get("popularity", 100),
            )
            ra = sorted_by_pop[0]
            images = ra.get("images", [])
            rarest_artist = {
                "name": ra.get("name"),
                "popularity": ra.get("popularity", 0),
                "image": images[0]["url"] if images else None,
            }

        rarest_track = None
        if tracks_items:
            sorted_tracks_by_pop = sorted(
                tracks_items,
                key=lambda t: t.get("popularity", 100),
            )
            rt = sorted_tracks_by_pop[0]
            album = rt.get("album", {})
            album_images = album.get("images", [])
            rarest_track = {
                "name": rt.get("name"),
                "artist": ", ".join([a["name"] for a in rt.get("artists", []) if "name" in a]),
                "popularity": rt.get("popularity", 0),
                "image": album_images[0]["url"] if album_images else None,
            }

        # 6. Decades histogram
        decades_counter: Counter = Counter()
        for t in tracks_items:
            album = t.get("album", {})
            rel_date = album.get("release_date") or ""
            if len(rel_date) >= 4 and rel_date[:4].isdigit():
                year = int(rel_date[:4])
                decade_start = (year // 10) * 10
                decades_counter[f"{decade_start}s"] += 1

        decades_list = [
            {"decade": dec, "count": count}
            for dec, count in sorted(decades_counter.items(), key=lambda x: x[0])
        ]

        # 7. Discovery rate: short_term top artists absent from long_term
        short_ids = {a["id"] for a in short_artists_items if "id" in a}
        long_ids = {a["id"] for a in long_artists_items if "id" in a}
        if short_ids:
            new_artist_count = len(short_ids - long_ids)
            discovery_rate = round(new_artist_count / len(short_ids), 4)
        else:
            discovery_rate = 0.0

        # 8. Evolution: delta of genre weights short vs long
        short_genre_weights = _get_normalized_genre_weights(short_artists_items)
        long_genre_weights = _get_normalized_genre_weights(long_artists_items)
        all_comparison_genres = set(short_genre_weights.keys()) | set(long_genre_weights.keys())

        deltas = []
        for g in all_comparison_genres:
            d = short_genre_weights.get(g, 0.0) - long_genre_weights.get(g, 0.0)
            deltas.append((g, d))

        deltas.sort(key=lambda x: x[1], reverse=True)
        rising = [
            {"genre": g, "delta": round(d, 4)}
            for g, d in deltas if d > 0.01
        ][:3]
        fading = [
            {"genre": g, "delta": round(abs(d), 4)}
            for g, d in reversed(deltas) if d < -0.01
        ][:3]

        # 9. Personality label & reason
        if diversity > 0.75 and discovery_rate > 0.4:
            personality = {
                "label": "Explorer",
                "reason": "Eagerly discovers new sounds across diverse musical spaces.",
            }
        elif diversity < 0.4:
            personality = {
                "label": "Loyalist",
                "reason": "Strongly devoted to a tightly defined sonic comfort zone.",
            }
        elif mainstream_score > 70:
            personality = {
                "label": "Mainstreamer",
                "reason": "Tuned in to chart-topping, universally loved hits.",
            }
        elif obscurity_score > 60:
            personality = {
                "label": "Digger",
                "reason": "Digs deep into underground gems and niche artists.",
            }
        else:
            personality = {
                "label": "Balanced",
                "reason": "Curates a harmonious blend of familiar favorites and new discoveries.",
            }

        # 10. Recently played
        recently_played = _fetch_recently_played(user_id, db)

        insights = {
            "status": "ok",
            "range": time_range_key,
            "top_genres": top_genres,
            "diversity": diversity,
            "mainstream_score": mainstream_score,
            "obscurity_score": obscurity_score,
            "rarest": {
                "artist": rarest_artist,
                "track": rarest_track,
            },
            "decades": decades_list,
            "discovery_rate": discovery_rate,
            "evolution": {
                "rising": rising,
                "fading": fading,
            },
            "personality": personality,
            "recently_played": recently_played,
        }

        _INSIGHTS_CACHE[cache_key] = (now, insights)
        return insights

    finally:
        if close_db:
            db.close()


def _get_normalized_genre_weights(artists: List[Dict[str, Any]]) -> Dict[str, float]:
    genre_accum: Dict[str, float] = defaultdict(float)
    n = len(artists)
    for i, a in enumerate(artists):
        w = (n - i) / n if n > 0 else 1.0
        for g in a.get("genres", []):
            genre_accum[g.lower()] += w
    total = sum(genre_accum.values())
    if total <= 0:
        return {}
    return {g: w / total for g, w in genre_accum.items()}


def _fetch_recently_played(user_id: str, db: Session) -> List[Dict[str, Any]]:
    events = (
        db.query(SpotifyPlayEvent)
        .filter(SpotifyPlayEvent.user_id == user_id)
        .order_by(desc(SpotifyPlayEvent.played_at))
        .limit(20)
        .all()
    )
    result = []
    for ev in events:
        artists_str = ""
        if ev.artist_names_json:
            try:
                names = json.loads(ev.artist_names_json)
                artists_str = ", ".join(names)
            except Exception:
                artists_str = ev.artist_names_json
        result.append({
            "track": ev.track_name or "Unknown Track",
            "artist": artists_str or "Unknown Artist",
            "played_at": ev.played_at.isoformat() if ev.played_at else None,
        })
    return result


def _empty_or_partial_insights(user_id: str, db: Session, status: str = "needs_reconnect", range_key: str = "medium") -> Dict[str, Any]:
    recently_played = _fetch_recently_played(user_id, db)
    return {
        "status": status,
        "range": range_key,
        "top_genres": [],
        "diversity": 0.0,
        "mainstream_score": 50.0,
        "obscurity_score": 50.0,
        "rarest": {"artist": None, "track": None},
        "decades": [],
        "discovery_rate": 0.0,
        "evolution": {"rising": [], "fading": []},
        "personality": {
            "label": "Balanced",
            "reason": "Connect Spotify to unlock complete taste insights.",
        },
        "recently_played": recently_played,
    }
