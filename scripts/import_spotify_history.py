"""
scripts/import_spotify_history.py — Spotify Extended Streaming History import pipeline.

Parses raw JSON files from a Spotify data download, aggregates per-artist
listening behaviour, enriches with genres via the Spotify Client Credentials
API, builds a weighted genre profile, and stores it so it plugs into the
existing taste-profile pipeline.

Usage
-----
    python scripts/import_spotify_history.py \\
        --folder "C:\\path\\to\\Spotify Extended Streaming History" \\
        --user-id test_import_user

    python scripts/import_spotify_history.py --folder "..." --dry-run   # inspect only, don't store
"""

import argparse
import json
import os
import sys
import time
import base64
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")


# ---------------------------------------------------------------------------
# Step 1 — Parse and merge
# ---------------------------------------------------------------------------

def parse_and_merge(folder: str) -> List[Dict[str, Any]]:
    """
    Load all Streaming_History_Audio_*.json files from *folder*,
    merge them into one list, and drop records with null artist names.
    """
    all_records: List[Dict[str, Any]] = []
    files_found = 0

    for fname in sorted(os.listdir(folder)):
        if fname.startswith("Streaming_History_Audio_") and fname.endswith(".json"):
            fpath = os.path.join(folder, fname)
            with open(fpath, encoding="utf-8") as f:
                records = json.load(f)
            print(f"  {fname}: {len(records):,} records")
            all_records.extend(records)
            files_found += 1

    print(f"\n  Files merged: {files_found}")
    print(f"  Total play events (raw): {len(all_records):,}")

    # Filter out null-artist records (podcasts, audiobooks, etc.)
    filtered = [
        r for r in all_records
        if r.get("master_metadata_album_artist_name")
    ]
    print(f"  After filtering null artists: {len(filtered):,}")

    return filtered


# ---------------------------------------------------------------------------
# Step 2 — Aggregate per artist
# ---------------------------------------------------------------------------

def aggregate_per_artist(
    records: List[Dict[str, Any]],
    min_plays: int = 5,
) -> Dict[str, Dict[str, Any]]:
    """
    Group by artist name and compute listening stats.
    Returns a dict keyed by artist name.
    """
    raw: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"total_ms_played": 0, "play_count": 0, "skip_count": 0}
    )

    for rec in records:
        artist = rec["master_metadata_album_artist_name"]
        ms = rec.get("ms_played", 0)
        skipped = rec.get("skipped")

        raw[artist]["total_ms_played"] += ms
        raw[artist]["play_count"] += 1

        # Count as skip if explicitly skipped OR played < 30s
        if skipped is True or ms < 30_000:
            raw[artist]["skip_count"] += 1

    print(f"\n  Unique artists (before filter): {len(raw):,}")

    # Filter by minimum play count and compute completion rate
    result: Dict[str, Dict[str, Any]] = {}
    for artist, stats in raw.items():
        if stats["play_count"] < min_plays:
            continue
        stats["completion_rate"] = round(
            1.0 - (stats["skip_count"] / stats["play_count"]), 4
        )
        result[artist] = dict(stats)

    print(f"  After {min_plays}-play filter: {len(result):,}")
    return result


# ---------------------------------------------------------------------------
# Step 3 — Compute affinity score
# ---------------------------------------------------------------------------

def compute_affinity_scores(
    artist_stats: Dict[str, Dict[str, Any]],
    top_n: int = 200,
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    affinity_score = total_ms_played * completion_rate
    Returns top *top_n* artists sorted by affinity descending.
    """
    for stats in artist_stats.values():
        stats["affinity_score"] = round(
            stats["total_ms_played"] * stats["completion_rate"], 2
        )

    ranked = sorted(
        artist_stats.items(),
        key=lambda x: x[1]["affinity_score"],
        reverse=True,
    )
    return ranked[:top_n]


# ---------------------------------------------------------------------------
# Step 4 — Genre enrichment via Spotify Client Credentials
# ---------------------------------------------------------------------------

def get_client_credentials_token() -> str:
    """Get an app-level access token (no user login needed)."""
    auth_str = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    b64 = base64.b64encode(auth_str.encode()).decode()

    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={
            "Authorization": f"Basic {b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials"},
        timeout=10,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Client Credentials token failed: {resp.status_code} {resp.text}")

    return resp.json()["access_token"]


def search_artist_id(name: str, token: str) -> Optional[str]:
    """Search Spotify for an artist by name, return their ID or None."""
    resp = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": name, "type": "artist", "limit": 1},
        timeout=15,
    )
    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", 5))
        print(f"    Rate limited, waiting {retry_after}s...")
        time.sleep(retry_after)
        return search_artist_id(name, token)  # retry once
    if resp.status_code != 200:
        return None
    items = resp.json().get("artists", {}).get("items", [])
    if not items:
        return None
    return items[0]["id"]


def batch_fetch_artist_genres(
    artist_ids: List[str], token: str
) -> Dict[str, List[str]]:
    """Batch-fetch genres for up to 50 artist IDs at a time."""
    result: Dict[str, List[str]] = {}
    CHUNK = 50

    for i in range(0, len(artist_ids), CHUNK):
        chunk = artist_ids[i : i + CHUNK]
        resp = requests.get(
            f"https://api.spotify.com/v1/artists?ids={','.join(chunk)}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            print(f"    Rate limited, waiting {retry_after}s...")
            time.sleep(retry_after)
            resp = requests.get(
                f"https://api.spotify.com/v1/artists?ids={','.join(chunk)}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
        if resp.status_code != 200:
            print(f"    Batch fetch failed: {resp.status_code}")
            continue
        for artist in resp.json().get("artists", []) or []:
            if artist:
                result[artist["id"]] = artist.get("genres", [])

    return result


def enrich_with_genres(
    ranked_artists: List[Tuple[str, Dict[str, Any]]],
    token: str,
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    For each ranked artist, search for their Spotify ID and batch-fetch genres.
    Adds 'spotify_id' and 'genres' keys to each artist's stats dict.
    """
    from routers.spotify import normalize_genres

    print("\n  Searching artist IDs on Spotify...")
    name_to_id: Dict[str, str] = {}
    for idx, (name, _stats) in enumerate(ranked_artists):
        aid = search_artist_id(name, token)
        if aid:
            name_to_id[name] = aid
        if (idx + 1) % 50 == 0:
            print(f"    Searched {idx + 1}/{len(ranked_artists)} artists...")
        # Small delay to avoid rate limits
        time.sleep(0.05)

    print(f"  Matched {len(name_to_id)}/{len(ranked_artists)} artists to Spotify IDs")

    # Batch-fetch genres
    all_ids = list(name_to_id.values())
    id_to_genres = batch_fetch_artist_genres(all_ids, token)

    # Attach genres to ranked artists
    for name, stats in ranked_artists:
        aid = name_to_id.get(name)
        if aid:
            stats["spotify_id"] = aid
            raw_genres = id_to_genres.get(aid, [])
            stats["genres"] = normalize_genres(raw_genres)
        else:
            stats["spotify_id"] = None
            stats["genres"] = []

    return ranked_artists


# ---------------------------------------------------------------------------
# Step 5 — Build weighted taste profile
# ---------------------------------------------------------------------------

def build_genre_profile(
    ranked_artists: List[Tuple[str, Dict[str, Any]]],
) -> Dict[str, float]:
    """
    For each genre across all enriched artists, sum the affinity_score of
    every artist tagged with that genre.  Returns {genre: weight} sorted desc.
    """
    profile: Dict[str, float] = defaultdict(float)

    for _name, stats in ranked_artists:
        score = stats.get("affinity_score", 0)
        for genre in stats.get("genres", []):
            profile[genre] += score

    # Sort descending
    return dict(sorted(profile.items(), key=lambda x: x[1], reverse=True))


# ---------------------------------------------------------------------------
# Step 6 — Store via database
# ---------------------------------------------------------------------------

def store_profile(
    user_id: str,
    genre_profile: Dict[str, float],
    ranked_artists: List[Tuple[str, Dict[str, Any]]],
    total_plays: int,
    unique_artists: int,
) -> None:
    """Persist the computed profile into the database."""
    from database import upsert_spotify_import_profile

    # Build artist summary (top 50)
    artist_summary = [
        {
            "artist": name,
            "affinity_score": stats["affinity_score"],
            "play_count": stats["play_count"],
            "completion_rate": stats["completion_rate"],
            "genres": stats.get("genres", []),
        }
        for name, stats in ranked_artists[:50]
    ]

    upsert_spotify_import_profile(
        user_id=user_id,
        genre_profile_json=json.dumps(genre_profile),
        artist_summary_json=json.dumps(artist_summary),
        total_plays=total_plays,
        unique_artists=unique_artists,
    )
    print(f"\n  Profile stored for user_id='{user_id}'")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_pipeline(folder: str, user_id: str, dry_run: bool = False) -> Dict[str, Any]:
    """Run the full import pipeline and return results."""
    print("=" * 60)
    print("STEP 1: Parse and merge")
    print("=" * 60)
    records = parse_and_merge(folder)
    total_plays = len(records)

    print("\n" + "=" * 60)
    print("STEP 2: Aggregate per artist")
    print("=" * 60)
    artist_stats = aggregate_per_artist(records, min_plays=5)

    print("\n" + "=" * 60)
    print("STEP 3: Compute affinity scores (top 200)")
    print("=" * 60)
    ranked = compute_affinity_scores(artist_stats, top_n=200)

    print(f"\n  Top 10 artists by affinity score:")
    print(f"  {'Artist':<40} {'Affinity':>14} {'Plays':>7} {'Skips':>7} {'Completion':>11}")
    print(f"  {'-'*40} {'-'*14} {'-'*7} {'-'*7} {'-'*11}")
    for name, stats in ranked[:10]:
        print(
            f"  {name:<40} {stats['affinity_score']:>14,.0f} "
            f"{stats['play_count']:>7,} {stats['skip_count']:>7,} "
            f"{stats['completion_rate']:>10.1%}"
        )

    print("\n" + "=" * 60)
    print("STEP 4: Genre enrichment via Spotify API")
    print("=" * 60)
    try:
        from services.spotify_sync import get_valid_access_token
        token = get_valid_access_token(user_id)
        if not token:
            token = get_client_credentials_token()
    except Exception:
        token = get_client_credentials_token()
    print(f"  Got access token.")
    ranked = enrich_with_genres(ranked, token)

    print(f"\n  Genre enrichment sample (top 10):")
    print(f"  {'Artist':<40} Genres")
    print(f"  {'-'*40} {'-'*50}")
    for name, stats in ranked[:10]:
        genres_str = ", ".join(stats.get("genres", [])[:6]) or "(no genres found)"
        print(f"  {name:<40} {genres_str}")

    print("\n" + "=" * 60)
    print("STEP 5: Build weighted genre profile")
    print("=" * 60)
    genre_profile = build_genre_profile(ranked)

    print(f"\n  Top 20 genres in taste profile:")
    print(f"  {'Genre':<30} {'Weight':>14}")
    print(f"  {'-'*30} {'-'*14}")
    for genre, weight in list(genre_profile.items())[:20]:
        print(f"  {genre:<30} {weight:>14,.0f}")

    if not dry_run:
        print("\n" + "=" * 60)
        print("STEP 6: Store profile")
        print("=" * 60)
        store_profile(
            user_id=user_id,
            genre_profile=genre_profile,
            ranked_artists=ranked,
            total_plays=total_plays,
            unique_artists=len(artist_stats),
        )

        # Verify retrieval
        from database import get_spotify_import_profile
        stored = get_spotify_import_profile(user_id)
        if stored:
            print(f"  Verified: profile retrieved from DB for '{user_id}'")
            print(f"    total_plays = {stored['total_plays']}")
            print(f"    unique_artists = {stored['unique_artists']}")
            stored_profile = json.loads(stored["genre_profile_json"])
            print(f"    genre count = {len(stored_profile)}")
            print(f"    top 5 genres = {list(stored_profile.items())[:5]}")
        else:
            print(f"  ERROR: could not retrieve stored profile!")
    else:
        print("\n  [DRY RUN] Skipping storage.")

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)

    return {
        "total_plays": total_plays,
        "unique_artists": len(artist_stats),
        "genre_profile": genre_profile,
        "top_artists": [
            {"artist": n, **s} for n, s in ranked[:50]
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import Spotify Extended Streaming History into the taste profile."
    )
    parser.add_argument(
        "--folder",
        required=True,
        help="Path to the folder containing Streaming_History_Audio_*.json files.",
    )
    parser.add_argument(
        "--user-id",
        default="import_test_user",
        help="User ID to store the profile against (default: import_test_user).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run Steps 1-5 without storing to the database.",
    )
    args = parser.parse_args()

    run_pipeline(folder=args.folder, user_id=args.user_id, dry_run=args.dry_run)
