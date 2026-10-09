"""
scripts/add_movies.py — Fetch and insert 300 additional movies from TMDB.

Fetches:
  - 150 global (en)
  - 75 Hindi (hi)
  - 75 South Indian (ta|te|ml)
from TMDB /discover/movie with sort_by=popularity.desc.
Starts with vote_count.gte=500, stepping down if fewer candidates exist in TMDB.
Skips existing tmdb_id / imdb_id, empty overview, or empty genres.
Fills Movie ORM fields: tmdb_id, imdb_id, title, overview, genres_json,
release_year, poster_url, vote_average.
Idempotent: scanning the same discover windows skips existing rows and adds 0.
"""

import json
import os
import ssl
import subprocess
import sys
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
REQUEST_DELAY = 0.3


class _TLS12Adapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        if hasattr(ssl, "OP_IGNORE_UNEXPECTED_EOF"):
            ctx.options |= ssl.OP_IGNORE_UNEXPECTED_EOF
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


_session = requests.Session()
_session.mount("https://", _TLS12Adapter())


def _curl_tmdb_fallback(endpoint: str, all_params: dict) -> dict:
    """Fallback using Windows curl (Schannel) when Python OpenSSL hits handshake issues."""
    qs = urllib.parse.urlencode(all_params)
    url = f"{TMDB_BASE_URL}{endpoint}?{qs}"
    for attempt in range(5):
        res = subprocess.run(
            ["curl.exe", "-sS", "--retry", "5", "--retry-all-errors", "--retry-delay", "1", url],
            capture_output=True,
        )
        if res.returncode == 0 and res.stdout:
            txt = res.stdout.decode("utf-8", errors="replace").strip()
            if txt.startswith("{"):
                return json.loads(txt)
        time.sleep(0.5)
    raise RuntimeError(f"TMDB request failed via curl for {endpoint}")


def _tmdb_get(endpoint: str, params: Optional[dict] = None) -> dict:
    """Make authenticated GET request to TMDB v3 with curl fallback."""
    all_params = {"api_key": TMDB_API_KEY}
    if params:
        all_params.update(params)

    try:
        url = f"{TMDB_BASE_URL}{endpoint}"
        resp = _session.get(url, params=all_params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass

    return _curl_tmdb_fallback(endpoint, all_params)


def fetch_genre_map() -> Dict[int, str]:
    """Fetch TMDB movie genre list and return {id: name} mapping."""
    data = _tmdb_get("/genre/movie/list", {"language": "en-US"})
    genre_map = {g["id"]: g["name"] for g in data.get("genres", [])}
    print(f"Loaded {len(genre_map)} genre mappings from TMDB.")
    return genre_map


def fetch_movie_detail(tmdb_id: int) -> Optional[dict]:
    """Fetch full movie detail for imdb_id, vote_average, etc."""
    try:
        return _tmdb_get(f"/movie/{tmdb_id}", {"language": "en-US"})
    except Exception as e:
        print(f"  Detail fetch failed for tmdb_id={tmdb_id}: {e}")
        return None


def fetch_and_insert_bucket(
    db,
    bucket_name: str,
    language_code: str,
    target_count: int,
    threshold_limits: List[Tuple[int, int]],
    genre_map: Dict[int, str],
    existing_tmdb_ids: Set[int],
    existing_imdb_ids: Set[str],
) -> int:
    """Walk /discover/movie pages for a language bucket until target_count new movies are inserted."""
    from database import Movie

    print(f"\n--- Fetching Bucket: {bucket_name} (language={language_code}, target={target_count}) ---")
    added = 0
    commit_counter = 0

    for min_votes, max_pages in threshold_limits:
        if added >= target_count:
            break

        print(f"  Querying /discover/movie with vote_count.gte={min_votes}...")
        page = 1

        while added < target_count and page <= max_pages:
            params = {
                "with_original_language": language_code,
                "vote_count.gte": min_votes,
                "sort_by": "popularity.desc",
                "page": page,
                "language": "en-US",
            }
            try:
                time.sleep(REQUEST_DELAY)
                data = _tmdb_get("/discover/movie", params)
            except Exception as e:
                print(f"    Page {page} fetch error: {e}")
                break

            results = data.get("results", [])
            total_pages = data.get("total_pages", 0)
            if not results:
                break

            for raw in results:
                if added >= target_count:
                    break

                tmdb_id = raw.get("id")
                if not tmdb_id or tmdb_id in existing_tmdb_ids:
                    continue

                title = raw.get("title", "").strip()
                overview = (raw.get("overview") or "").strip()
                if not overview:
                    continue

                # Resolve genres
                genre_ids = raw.get("genre_ids", [])
                genre_names = [genre_map[gid] for gid in genre_ids if gid in genre_map]
                if not genre_names:
                    continue

                # Fetch movie detail for imdb_id & vote_average
                time.sleep(REQUEST_DELAY)
                detail = fetch_movie_detail(tmdb_id)
                imdb_id = None
                vote_avg = raw.get("vote_average")

                if detail:
                    imdb_id = (detail.get("imdb_id") or "").strip() or None
                    if detail.get("vote_average") is not None:
                        vote_avg = detail.get("vote_average")
                    # Fallback genres from detail if needed
                    if not genre_names and detail.get("genres"):
                        genre_names = [g["name"] for g in detail.get("genres", []) if "name" in g]

                if not genre_names:
                    continue

                # Check unique imdb_id
                if imdb_id and imdb_id in existing_imdb_ids:
                    continue

                # Extract release year
                release_date = raw.get("release_date") or ""
                release_year = None
                if release_date and len(release_date) >= 4:
                    try:
                        release_year = int(release_date[:4])
                    except ValueError:
                        pass

                poster_path = raw.get("poster_path")
                poster_url = f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None

                movie = Movie(
                    tmdb_id=tmdb_id,
                    imdb_id=imdb_id,
                    title=title,
                    overview=overview,
                    genres_json=json.dumps(genre_names),
                    release_year=release_year,
                    poster_url=poster_url,
                    vote_average=float(vote_avg) if vote_avg is not None else None,
                    personal_rating=None,
                )
                db.add(movie)
                existing_tmdb_ids.add(tmdb_id)
                if imdb_id:
                    existing_imdb_ids.add(imdb_id)

                added += 1
                commit_counter += 1

                if commit_counter % 50 == 0:
                    db.commit()
                    print(f"    Progress in {bucket_name}: {added}/{target_count} added (committed)")

            page += 1
            if page > total_pages:
                break

    db.commit()
    print(f"  Finished {bucket_name}: {added}/{target_count} movies added.")
    return added


def main():
    if not TMDB_API_KEY:
        print("ERROR: TMDB_API_KEY not found in environment.")
        sys.exit(1)

    print("=" * 60)
    print("TMDB Add Movies: 300 New Titles")
    print("=" * 60)

    os.environ.setdefault("USE_LOCAL_DB", "true")
    from database import SessionLocal, Movie

    db = SessionLocal()
    try:
        initial_count = db.query(Movie).count()
        print(f"Initial movies in database: {initial_count}")

        # Load existing tmdb_id and imdb_id
        existing_movies = db.query(Movie.tmdb_id, Movie.imdb_id).all()
        existing_tmdb_ids: Set[int] = {m[0] for m in existing_movies if m[0] is not None}
        existing_imdb_ids: Set[str] = {m[1] for m in existing_movies if m[1] is not None}
        print(f"Existing unique tmdb_ids: {len(existing_tmdb_ids)}, imdb_ids: {len(existing_imdb_ids)}")

        genre_map = fetch_genre_map()

        # Buckets with exact threshold windows:
        # Global (en): 8 pages @ 500
        # Hindi (hi): 1 page @ 500, 3 pages @ 200
        # South Indian: 1 page @ 500, 1 page @ 200, 3 pages @ 100, 1 page @ 50
        buckets = [
            ("Global (en)", "en", 150, [(500, 8)]),
            ("Hindi (hi)", "hi", 75, [(500, 1), (200, 3)]),
            ("South Indian (ta|te|ml)", "ta|te|ml", 75, [(500, 1), (200, 1), (100, 3), (50, 1)]),
        ]

        counts: Dict[str, int] = {}
        for b_name, b_lang, b_target, b_limits in buckets:
            added = fetch_and_insert_bucket(
                db=db,
                bucket_name=b_name,
                language_code=b_lang,
                target_count=b_target,
                threshold_limits=b_limits,
                genre_map=genre_map,
                existing_tmdb_ids=existing_tmdb_ids,
                existing_imdb_ids=existing_imdb_ids,
            )
            counts[b_name] = added

        final_count = db.query(Movie).count()
        print("\n" + "=" * 60)
        print("SUMMARY OF ADDED MOVIES")
        print("=" * 60)
        for b_name, added in counts.items():
            print(f"  {b_name}: {added} added")
        print(f"  Total newly added: {sum(counts.values())}")
        print(f"  Previous total: {initial_count}")
        print(f"  New database total: {final_count}")

    except Exception as e:
        db.rollback()
        print(f"\nFATAL ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
