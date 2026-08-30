"""
services/taste_profile.py — Cross-module taste profile engine.

compute_taste_profile(user_id, spotify_token=None) aggregates signal from:
  1. Spotify — weighted genre profile from top artists (reuses compute_genre_profile
               from routers.spotify — no duplication)
  2. Anime   — genres of explicitly liked anime entries and AniList watch history

The signal vectors are merged into a single {keyword: float} dict.
A genre crosswalk maps Spotify music genres to semantically related anime
genres.
"""

from __future__ import annotations

import requests
from typing import Any, Dict, List, Optional

from database import get_likes, get_anilist_user
from services.anilist_client import fetch_user_anime_list

# ---------------------------------------------------------------------------
# Genre crosswalk: Spotify music genre → related anime genre keywords
# These are the seeds for the ?personalize=true boost in routers/anime.py.
# ---------------------------------------------------------------------------
GENRE_CROSSWALK: Dict[str, List[str]] = {
    # High-energy music → high-energy anime
    "rock": ["action", "shonen", "adventure"],
    "metal": ["action", "shonen", "dark fantasy", "seinen"],
    # Chill / jazz → slice-of-life, drama
    "jazz": ["slice of life", "drama", "music", "josei"],
    "classical": ["slice of life", "drama", "music"],
    "ambient": ["slice of life", "psychological", "drama"],
    # Electronic → futuristic / cerebral
    "electronic": ["sci-fi", "mecha", "psychological"],
    # Pop / indie → romance / comedy
    "pop": ["romance", "comedy", "school"],
    "indie": ["romance", "slice of life", "comedy"],
    # Hip-hop / rap → sports, street
    "hip hop": ["sports", "action", "adventure"],
    "rap": ["sports", "action"],
    # Country / folk → historical / rural
    "country": ["historical", "adventure", "fantasy"],
    "folk": ["historical", "fantasy"],
    # R&B → romance
    "r&b": ["romance", "drama", "music"],
}

# ---------------------------------------------------------------------------
# Tourism crosswalk: Music genre / Anime genre → tourist spot categories
# ---------------------------------------------------------------------------
TOURISM_CROSSWALK: Dict[str, List[str]] = {
    # High-energy / aggressive genres & action anime lean adventure_outdoor
    "rock": ["adventure_outdoor"],
    "metal": ["adventure_outdoor"],
    "action": ["adventure_outdoor"],
    "sports": ["adventure_outdoor"],
    "adventure": ["adventure_outdoor"],
    "shonen": ["adventure_outdoor"],

    # Ambient / acoustic / chill genres & slice-of-life anime lean chill_scenic
    "ambient": ["chill_scenic"],
    "jazz": ["chill_scenic"],
    "folk": ["chill_scenic", "cultural_historic"],
    "country": ["chill_scenic"],
    "slice of life": ["chill_scenic"],
    "iyashikei": ["chill_scenic"],

    # Pop / dance / electronic genres & idol / music anime lean nightlife
    "electronic": ["nightlife", "offbeat_indie"],
    "dance": ["nightlife"],
    "edm": ["nightlife"],
    "house": ["nightlife"],
    "techno": ["nightlife"],
    "hip hop": ["nightlife", "adventure_outdoor"],
    "rap": ["nightlife"],
    "music": ["nightlife"],

    # Classical / indie genres & arthouse / psychological anime lean cultural_historic / offbeat_indie
    "classical": ["cultural_historic"],
    "historical": ["cultural_historic"],
    "indie": ["offbeat_indie", "chill_scenic"],
    "psychological": ["offbeat_indie"],
    "sci-fi": ["offbeat_indie"],
    "mecha": ["offbeat_indie"],
    "fantasy": ["cultural_historic", "adventure_outdoor"],
    "dark fantasy": ["offbeat_indie"],
    "mystery": ["offbeat_indie"],
    "supernatural": ["offbeat_indie"],
    "seinen": ["cultural_historic", "offbeat_indie"],
    "josei": ["cultural_historic"],
    "drama": ["cultural_historic", "chill_scenic"],

    # Mainstream pop & romance / comedy lean shopping_social
    "pop": ["shopping_social"],
    "r&b": ["shopping_social", "chill_scenic"],
    "romance": ["shopping_social", "chill_scenic"],
    "comedy": ["shopping_social"],
    "school": ["shopping_social"],
}

# ---------------------------------------------------------------------------
# Movie crosswalk: Music genre / Anime genre -> movie genres
# ---------------------------------------------------------------------------
MOVIE_CROSSWALK: Dict[str, List[str]] = {
    # High-energy / aggressive genres & action anime
    "rock": ["Action", "Thriller", "War"],
    "metal": ["Action", "Thriller", "Horror"],
    "action": ["Action", "Thriller", "Adventure"],
    "sports": ["Action", "Drama", "Documentary"],
    "adventure": ["Adventure", "Action", "Fantasy"],
    "shonen": ["Action", "Adventure", "Animation"],

    # Ambient / acoustic / chill genres & slice-of-life anime
    "ambient": ["Documentary", "Drama", "Mystery"],
    "jazz": ["Drama", "Music", "Crime"],
    "folk": ["Drama", "Family", "History"],
    "country": ["Western", "Drama", "Family"],
    "slice of life": ["Drama", "Comedy", "Family"],
    "iyashikei": ["Documentary", "Family", "Animation"],

    # Pop / dance / electronic genres & idol / music anime
    "electronic": ["Science Fiction", "Mystery", "Thriller"],
    "dance": ["Music", "Romance", "Comedy"],
    "edm": ["Science Fiction", "Action", "Music"],
    "house": ["Music", "Drama", "Romance"],
    "techno": ["Science Fiction", "Thriller", "Action"],
    "hip hop": ["Crime", "Action", "Music"],
    "rap": ["Crime", "Action", "Drama"],
    "music": ["Music", "Documentary", "Family"],

    # Classical / indie genres & arthouse / psychological anime
    "classical": ["History", "Drama", "Music"],
    "historical": ["History", "War", "Drama"],
    "indie": ["Drama", "Comedy", "Romance"],
    "psychological": ["Thriller", "Mystery", "Drama"],
    "sci-fi": ["Science Fiction", "Mystery", "Action"],
    "mecha": ["Science Fiction", "Action", "Animation"],
    "fantasy": ["Fantasy", "Adventure", "Animation"],
    "dark fantasy": ["Horror", "Fantasy", "Thriller"],
    "mystery": ["Mystery", "Crime", "Thriller"],
    "supernatural": ["Horror", "Fantasy", "Mystery"],
    "seinen": ["Crime", "Drama", "Thriller"],
    "josei": ["Romance", "Drama", "Comedy"],
    "drama": ["Drama", "Romance", "History"],

    # Mainstream pop & romance / comedy
    "pop": ["Romance", "Comedy", "Music"],
    "r&b": ["Romance", "Drama", "Music"],
    "romance": ["Romance", "Drama", "Comedy"],
    "comedy": ["Comedy", "Family", "Romance"],
    "school": ["Comedy", "Romance", "Animation"],
}

# ---------------------------------------------------------------------------
# Dining crosswalk: Music genre / Anime genre → dining spot categories
# ---------------------------------------------------------------------------
DINING_CROSSWALK: Dict[str, List[str]] = {
    # High-energy / aggressive genres & action anime → bars, street food
    "rock": ["bar_nightlife_dining", "street_food_quick_bite"],
    "metal": ["bar_nightlife_dining", "street_food_quick_bite"],
    "action": ["bar_nightlife_dining", "street_food_quick_bite"],
    "sports": ["street_food_quick_bite", "casual_dining"],
    "adventure": ["street_food_quick_bite", "casual_dining"],
    "shonen": ["street_food_quick_bite", "casual_dining"],

    # Ambient / acoustic / chill genres & slice-of-life → cafes, fine dining
    "ambient": ["cafe_coffee", "fine_dining"],
    "jazz": ["cafe_coffee", "fine_dining"],
    "folk": ["cafe_coffee", "casual_dining"],
    "country": ["casual_dining", "cafe_coffee"],
    "slice of life": ["cafe_coffee", "casual_dining"],
    "iyashikei": ["cafe_coffee", "dessert_bakery"],

    # Pop / dance / electronic → bars, casual dining
    "electronic": ["bar_nightlife_dining"],
    "dance": ["bar_nightlife_dining"],
    "edm": ["bar_nightlife_dining"],
    "house": ["bar_nightlife_dining"],
    "techno": ["bar_nightlife_dining"],
    "hip hop": ["bar_nightlife_dining", "street_food_quick_bite"],
    "rap": ["bar_nightlife_dining", "street_food_quick_bite"],
    "music": ["bar_nightlife_dining"],

    # Classical / indie / arthouse → fine dining, cafes
    "classical": ["fine_dining", "cafe_coffee"],
    "historical": ["fine_dining", "casual_dining"],
    "indie": ["cafe_coffee", "dessert_bakery"],
    "psychological": ["cafe_coffee"],
    "sci-fi": ["cafe_coffee", "dessert_bakery"],
    "mecha": ["cafe_coffee"],
    "fantasy": ["casual_dining", "fine_dining"],
    "dark fantasy": ["bar_nightlife_dining", "cafe_coffee"],
    "mystery": ["cafe_coffee", "fine_dining"],
    "supernatural": ["cafe_coffee"],
    "seinen": ["fine_dining", "cafe_coffee"],
    "josei": ["cafe_coffee", "dessert_bakery"],
    "drama": ["casual_dining", "cafe_coffee"],

    # Mainstream pop & romance / comedy → casual dining, desserts
    "pop": ["casual_dining", "dessert_bakery"],
    "r&b": ["casual_dining", "dessert_bakery"],
    "romance": ["dessert_bakery", "cafe_coffee"],
    "comedy": ["casual_dining", "dessert_bakery"],
    "school": ["street_food_quick_bite", "dessert_bakery"],
}

# Per-source weight multipliers so explicit likes (low volume but intentional)
# are not drowned out by Spotify's high-volume implicit signal.
_SPOTIFY_WEIGHT = 1.0   # Spotify profile already normalized to sum ~50
_ANIME_WEIGHT   = 2.0   # Each explicit anime like contributes 2.0 per genre
_ANILIST_WEIGHT = 2.0
_MOVIE_WEIGHT   = 2.0   # Each explicit movie rating contributes up to 2.0 per genre


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_spotify_genre_profile(
    user_id: str, token: str
) -> Dict[str, float]:
    """
    Fetch the user's top artists from Spotify and return a weighted genre profile.

    Imports compute_genre_profile and normalize_genres directly from
    routers.spotify — no duplication of that logic.

    Falls back to an imported streaming-history profile if the live fetch
    returns empty (e.g. new account with no listening history yet, or the
    token is expired and refresh failed silently).
    """
    try:
        from routers.spotify import compute_genre_profile, normalize_genres  # type: ignore[import]
    except ImportError:
        return {}

    profile: Dict[str, float] = {}
    try:
        resp = requests.get(
            "https://api.spotify.com/v1/me/top/artists?limit=50",
            headers={"Authorization": f"Bearer {token}"},
            timeout=6,
        )
        if resp.status_code == 200:
            artists = resp.json().get("items", [])
            # Normalise genres into broad categories (reuses existing logic)
            for artist in artists:
                artist["genres"] = normalize_genres(artist.get("genres", []))
            profile = compute_genre_profile(artists)
    except Exception as exc:
        print(f"[taste_profile] Spotify fetch error: {exc}")

    # Fallback 1: check synced play history in database
    if not profile:
        try:
            from routers.spotify import get_genre_profile_from_history
            profile = get_genre_profile_from_history(user_id, token)
            if profile:
                print(f"[taste_profile] Using synced play-history profile for {user_id}")
        except Exception as exc:
            print(f"[taste_profile] Play-history fallback error: {exc}")

    # Fallback 2: if still nothing, check for an uploaded streaming-history file profile
    if not profile:
        try:
            from database import get_spotify_import_profile
            import json as _json
            import_data = get_spotify_import_profile(user_id)
            if import_data and import_data.get("genre_profile_json"):
                profile = _json.loads(import_data["genre_profile_json"])
                print(f"[taste_profile] Using imported streaming-history profile for {user_id}")
        except Exception as exc:
            print(f"[taste_profile] Import-profile fallback error: {exc}")

    return profile


def _anime_genre_signal(user_id: str) -> Dict[str, float]:
    """
    Return a genre-frequency dict from the user's liked anime entries.

    Looks each liked mal_id up in the in-memory catalog held by routers.anime.
    Skips items not found in catalog (catalog may be empty in tests — mocked).
    """
    likes = get_likes(user_id, module="anime")
    if not likes:
        return {}

    try:
        from routers.anime import catalog as anime_catalog, mal_id_to_index  # type: ignore[import]
    except ImportError:
        return {}

    profile: Dict[str, float] = {}
    for like in likes:
        try:
            mal_id = int(like["item_id"])
        except (ValueError, KeyError):
            continue
        idx = mal_id_to_index.get(mal_id)
        if idx is None:
            continue
        entry = anime_catalog[idx]
        for genre in entry.get("genres", []):
            genre_key = genre.lower()
            profile[genre_key] = profile.get(genre_key, 0.0) + _ANIME_WEIGHT

    return profile


def _anilist_genre_signal(user_id: str) -> Dict[str, float]:
    """
    Return a genre-frequency dict from the user's AniList anime list.

    Genre data comes directly from the AniList API response.  If an entry
    lacks genres (older cached responses), the local catalog is used as a
    fallback.
    """
    anilist_user = get_anilist_user(user_id)
    if not anilist_user:
        return {}

    access_token = anilist_user.get("access_token")
    anilist_id = anilist_user.get("anilist_id")
    if not access_token or not anilist_id:
        return {}

    anime_list = fetch_user_anime_list(access_token, anilist_id)
    if not anime_list:
        return {}

    # Optional fallback: local catalog for entries missing genres
    try:
        from routers.anime import catalog as anime_catalog, mal_id_to_index  # type: ignore[import]
    except ImportError:
        anime_catalog = []
        mal_id_to_index = {}

    profile: Dict[str, float] = {}
    for entry in anime_list:
        status = entry.get("status")
        if status not in {"CURRENT", "COMPLETED", "REPEATING"}:
            continue

        score = entry.get("score", 0.0)

        if score > 0:
            weight = (score / 10.0) * _ANILIST_WEIGHT
        else:
            weight = 0.5 * _ANILIST_WEIGHT

        # Prefer genres from AniList response; fall back to local catalog
        genres = entry.get("genres") or []
        if not genres:
            mal_id = entry.get("mal_id")
            idx = mal_id_to_index.get(mal_id)
            if idx is not None:
                genres = anime_catalog[idx].get("genres", [])

        for genre in genres:
            genre_key = genre.lower()
            profile[genre_key] = profile.get(genre_key, 0.0) + weight

    return profile


def _tourism_signal(
    user_genre_weights: Dict[str, float],
    user_anime_weights: Dict[str, float],
) -> Dict[str, float]:
    """
    Map user's Spotify genre weights and anime genre weights to tourist spot
    category weights across the six tourism categories using TOURISM_CROSSWALK.
    """
    crosswalk_tourism: Dict[str, float] = {
        "adventure_outdoor": 0.0,
        "cultural_historic": 0.0,
        "nightlife": 0.0,
        "chill_scenic": 0.0,
        "shopping_social": 0.0,
        "offbeat_indie": 0.0,
    }
    combined = _merge_profiles(user_genre_weights, user_anime_weights)
    for genre, weight in combined.items():
        categories = TOURISM_CROSSWALK.get(genre.lower(), [])
        for cat in categories:
            crosswalk_tourism[cat] = crosswalk_tourism.get(cat, 0.0) + weight

    return crosswalk_tourism


def _dining_signal(
    user_genre_weights: Dict[str, float],
    user_anime_weights: Dict[str, float],
) -> Dict[str, float]:
    """
    Map user's Spotify genre weights and anime genre weights to dining spot
    category weights across the six dining categories using DINING_CROSSWALK.
    """
    crosswalk_dining: Dict[str, float] = {
        "fine_dining": 0.0,
        "casual_dining": 0.0,
        "street_food_quick_bite": 0.0,
        "cafe_coffee": 0.0,
        "dessert_bakery": 0.0,
        "bar_nightlife_dining": 0.0,
    }
    combined = _merge_profiles(user_genre_weights, user_anime_weights)
    for genre, weight in combined.items():
        categories = DINING_CROSSWALK.get(genre.lower(), [])
        for cat in categories:
            crosswalk_dining[cat] = crosswalk_dining.get(cat, 0.0) + weight

    return crosswalk_dining


def _movie_crosswalk_signal(
    user_genre_weights: Dict[str, float],
    user_anime_weights: Dict[str, float],
) -> Dict[str, float]:
    """
    Map user's Spotify genre weights and anime genre weights to movie genres
    using MOVIE_CROSSWALK.
    """
    crosswalk_movie: Dict[str, float] = {
        "Action": 0.0, "Adventure": 0.0, "Animation": 0.0, "Comedy": 0.0,
        "Crime": 0.0, "Documentary": 0.0, "Drama": 0.0, "Family": 0.0,
        "Fantasy": 0.0, "History": 0.0, "Horror": 0.0, "Music": 0.0,
        "Mystery": 0.0, "Romance": 0.0, "Science Fiction": 0.0,
        "TV Movie": 0.0, "Thriller": 0.0, "War": 0.0, "Western": 0.0,
    }
    combined = _merge_profiles(user_genre_weights, user_anime_weights)
    for genre, weight in combined.items():
        categories = MOVIE_CROSSWALK.get(genre.lower(), [])
        for cat in categories:
            crosswalk_movie[cat] = crosswalk_movie.get(cat, 0.0) + weight

    return crosswalk_movie


def _movie_signal(user_id: str) -> Dict[str, float]:
    """
    Return a genre-frequency dict from the user's rated movies.
    Weights by personal_rating (higher rating = proportionally higher weight).
    """
    try:
        from database import get_db, Movie
        import json as _json
    except ImportError:
        return {}

    profile: Dict[str, float] = {}
    db = next(get_db())
    try:
        rated_movies = db.query(Movie).filter(Movie.personal_rating.isnot(None)).all()
        for movie in rated_movies:
            rating = movie.personal_rating
            if rating is None or rating <= 0:
                continue

            # Weighting: score/10 * _MOVIE_WEIGHT (mirroring _anilist_genre_signal)
            weight = (rating / 10.0) * _MOVIE_WEIGHT

            genres = []
            if movie.genres_json:
                genres = _json.loads(movie.genres_json)

            for genre in genres:
                profile[genre] = profile.get(genre, 0.0) + weight
    except Exception as exc:
        print(f"[taste_profile] _movie_signal error: {exc}")
    finally:
        db.close()

    return profile


def _merge_profiles(*profiles: Dict[str, float]) -> Dict[str, float]:
    """Sum multiple genre/keyword dicts into one merged profile."""
    merged: Dict[str, float] = {}
    for prof in profiles:
        for key, val in prof.items():
            merged[key] = merged.get(key, 0.0) + val
    return merged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_taste_profile(
    user_id: str,
    spotify_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a combined cross-module taste profile for the given user.

    Parameters
    ----------
    user_id:
        The authenticated user's ID (from the session cookie).
    spotify_token:
        A valid Spotify access token for this user, used to fetch top artists.
        If None (or if the fetch fails), the Spotify signal is silently skipped.

    Returns
    -------
    dict with keys:
      "profile"          — merged {genre/keyword: float} dict, sorted by weight desc
      "breakdown"        — per-source sub-profiles for debugging
      "crosswalk_anime"   — anime genre keywords derived from Spotify genres via
                            GENRE_CROSSWALK (used by the ?personalize=true boost)
      "crosswalk_tourism" — tourist spot category weights derived from combined
                            music and anime genres via TOURISM_CROSSWALK
    """
    # --- Gather per-source signals ---
    spotify_profile: Dict[str, float] = {}
    if spotify_token:
        raw = _fetch_spotify_genre_profile(user_id, spotify_token)
        spotify_profile = {k: v * _SPOTIFY_WEIGHT for k, v in raw.items()}

    anime_profile = _anime_genre_signal(user_id)
    anilist_profile = _anilist_genre_signal(user_id)
    movie_profile = _movie_signal(user_id)
    # Myntra is a separate structured preference namespace: clothing signals
    # must not be incorrectly mixed into media genre weights.
    try:
        from database import get_db
        from services.myntra_profile import get_profile as get_myntra_profile
        db = next(get_db())
        try:
            myntra_profile = get_myntra_profile(db, user_id)
        finally:
            db.close()
    except Exception:
        myntra_profile = {}

    merged = _merge_profiles(spotify_profile, anime_profile, anilist_profile, movie_profile)

    # --- Build anime crosswalk from Spotify genres ---
    crosswalk_anime: Dict[str, float] = {}
    for sp_genre, weight in spotify_profile.items():
        for anime_genre in GENRE_CROSSWALK.get(sp_genre, []):
            crosswalk_anime[anime_genre] = (
                crosswalk_anime.get(anime_genre, 0.0) + weight
            )

    # --- Build tourism crosswalk from combined music + anime signals ---
    crosswalk_tourism = _tourism_signal(
        spotify_profile,
        _merge_profiles(anime_profile, anilist_profile),
    )

    # --- Build dining crosswalk from combined music + anime signals ---
    crosswalk_dining = _dining_signal(
        spotify_profile,
        _merge_profiles(anime_profile, anilist_profile),
    )

    # --- Build movie crosswalk from combined music + anime signals ---
    crosswalk_movie = _movie_crosswalk_signal(
        spotify_profile,
        _merge_profiles(anime_profile, anilist_profile),
    )

    # Fetch AniList watched list with titles
    anilist_watched = []
    try:
        anilist_user = get_anilist_user(user_id)
        if anilist_user:
            access_token = anilist_user.get("access_token")
            anilist_id = anilist_user.get("anilist_id")
            if access_token and anilist_id:
                raw_list = fetch_user_anime_list(access_token, anilist_id)
                for entry in raw_list:
                    if entry.get("status") in {"CURRENT", "COMPLETED", "REPEATING"}:
                        anilist_watched.append({
                            "mal_id": entry.get("mal_id"),
                            "title": entry.get("title"),
                            "score": entry.get("score"),
                            "status": entry.get("status")
                        })
    except Exception as exc:
        print(f"[taste_profile] failed to fetch anilist_watched: {exc}")

    # Sort merged profile descending by weight
    sorted_profile = dict(
        sorted(merged.items(), key=lambda x: x[1], reverse=True)
    )

    return {
        "profile": sorted_profile,
        "breakdown": {
            "spotify": dict(sorted(spotify_profile.items(), key=lambda x: x[1], reverse=True)),
            "anime": anime_profile,
            "anilist": anilist_profile,
            "movie": movie_profile,
            "myntra": myntra_profile,
        },
        "anilist_watched": anilist_watched,
        "crosswalk_anime": crosswalk_anime,
        "crosswalk_tourism": crosswalk_tourism,
        "crosswalk_dining": crosswalk_dining,
        "crosswalk_movie": crosswalk_movie,
    }


def get_anime_boost_map(user_id: str, spotify_token: Optional[str] = None) -> Dict[str, float]:
    """
    Return a {anime_genre_lower: boost_weight} dict for use in
    routers/anime.py's ?personalize=true re-ranking.

    Combines crosswalk-derived Spotify genres with directly liked anime genres.
    """
    profile_data = compute_taste_profile(user_id, spotify_token=spotify_token)
    boost_map = dict(profile_data["crosswalk_anime"])

    # Also directly boost genres of liked anime (already in profile)
    for genre, weight in profile_data["breakdown"]["anime"].items():
        boost_map[genre] = boost_map.get(genre, 0.0) + weight

    # Also directly boost genres of AniList anime
    for genre, weight in profile_data["breakdown"].get("anilist", {}).items():
        boost_map[genre] = boost_map.get(genre, 0.0) + weight

    return boost_map


def get_movie_boost_map(user_id: str, spotify_token: Optional[str] = None) -> Dict[str, float]:
    """
    Return a {movie_genre: boost_weight} dict for use in
    routers/movie.py's ?personalize=true re-ranking.

    Combines crosswalk-derived movie genres (from Spotify and Anime)
    with directly rated movie genres.

    Values are normalised to [0, 5] so the reranking formula
    ``similarity_score * (1 + boost/10)`` produces at most a 1.5x
    multiplier — enough to reorder, never enough to overwhelm the
    base similarity signal.  This mirrors the magnitude range that
    anime's boost map naturally lands in (a handful of explicit likes
    at ~2.0 weight each → single-digit totals).
    """
    profile_data = compute_taste_profile(user_id, spotify_token=spotify_token)
    boost_map = dict(profile_data.get("crosswalk_movie", {}))

    # Also directly boost genres of rated movies (already in breakdown["movie"])
    for genre, weight in profile_data.get("breakdown", {}).get("movie", {}).items():
        boost_map[genre] = boost_map.get(genre, 0.0) + weight

    # --- Normalise to [0, _MOVIE_BOOST_CEILING] ---
    # Raw weights can reach hundreds (251 rated movies × rating/10 × weight),
    # while the reranking divisor (/10) was calibrated for single-digit boosts.
    # Dividing by max and scaling to ceiling keeps relative genre ordering
    # intact while capping the absolute multiplier.
    _MOVIE_BOOST_CEILING = 5.0
    max_val = max(boost_map.values(), default=0.0)
    if max_val > 0:
        scale = _MOVIE_BOOST_CEILING / max_val
        boost_map = {k: v * scale for k, v in boost_map.items()}

    return boost_map

