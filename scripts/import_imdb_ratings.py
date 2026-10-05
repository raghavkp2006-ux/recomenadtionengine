"""Import an IMDb ratings export into an existing local SQLite movie catalog."""

import argparse
import csv
import math
import os
from pathlib import Path
import unicodedata

from dotenv import dotenv_values
from sqlalchemy import MetaData, Table, create_engine, select, update
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_COLUMNS = {"Const", "Your Rating", "Title", "Year", "Title Type"}


def default_database_url():
    """Resolve database.py's default without importing its startup migrations."""
    config = dotenv_values(ROOT / ".env")
    url = os.environ.get("DATABASE_URL", config.get("DATABASE_URL"))
    if url:
        return url.replace("postgres://", "postgresql://", 1)
    path = os.environ.get("SQLITE_PATH", config.get("SQLITE_PATH")) or ROOT / "spotify_tokens.db"
    return f"sqlite:///{path}"


def local_engine(url):
    if make_url(url).get_backend_name() != "sqlite":
        raise ValueError("This offline tool only accepts a local SQLite database URL")
    return create_engine(url)


def normalize_title(title):
    return " ".join("".join(
        char for char in title.casefold()
        if not unicodedata.category(char).startswith("P")
    ).split())


def read_ratings(path):
    with open(path, newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"IMDb CSV missing required columns: {', '.join(sorted(missing))}")
        rows = list(reader)
    # Validate all eligible rows before any changes, including clear-synthetic.
    for line, row in enumerate(rows, 2):
        if row["Title Type"].strip().casefold() not in {"movie", "tvmovie"}:
            continue
        try:
            rating = float(row["Your Rating"])
            year = int(row["Year"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"IMDb CSV row {line}: invalid rating or year") from exc
        if not math.isfinite(rating) or not 1 <= rating <= 10:
            raise ValueError(f"IMDb CSV row {line}: rating must be between 1 and 10")
        row["rating"] = rating
        row["year"] = year
    return rows


def import_ratings(path, engine, *, clear_synthetic=False, dry_run=False):
    rows = read_ratings(path)
    movies = Table("movies", MetaData(), autoload_with=engine)
    summary = dict(rows_read=len(rows), matched_by_imdb_id=0,
                   matched_by_title_year=0, unmatched=0, skipped_non_movie=0, cleared=0)
    with engine.connect() as connection:
        catalog = connection.execute(select(movies)).mappings().all()
        by_imdb = {row["imdb_id"]: row for row in catalog if row["imdb_id"]}
        by_title = {}
        for row in catalog:
            key = (normalize_title(row["title"]), row["release_year"])
            by_title.setdefault(key, []).append(row)
        matched = {}
        for row in rows:
            if row["Title Type"].strip().casefold() not in {"movie", "tvmovie"}:
                summary["skipped_non_movie"] += 1
                continue
            match = by_imdb.get(row["Const"].strip())
            strategy = "imdb_id"
            if match is None:
                candidates = by_title.get((normalize_title(row["Title"]), row["year"]), [])
                # Never arbitrarily choose between duplicate title/year entries.
                match = candidates[0] if len(candidates) == 1 else None
                strategy = "title_year"
            if match is None:
                summary["unmatched"] += 1
                print(f"Unmatched: {row['Const']} ({row['Title']})")
                continue
            summary[f"matched_by_{strategy}"] += 1
            matched[match["id"]] = row["rating"]
            print(f"Matched by {strategy}: {row['Const']} -> movie {match['id']}")
        cleared_ids = [row["id"] for row in catalog
                       if row["id"] not in matched and row["personal_rating"] is not None]
        if clear_synthetic:
            summary["cleared"] = len(cleared_ids)
        if not dry_run:
            if clear_synthetic and cleared_ids:
                connection.execute(update(movies).where(movies.c.id.in_(cleared_ids))
                                   .values(personal_rating=None))
            for movie_id, rating in matched.items():
                connection.execute(update(movies).where(movies.c.id == movie_id)
                                   .values(personal_rating=rating))
            connection.commit()
    print("DRY RUN (planned counts)" if dry_run else "IMPORT SUMMARY")
    for name, value in summary.items():
        print(f"{name}: {value}")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default="data/imdb_ratings.csv")
    parser.add_argument("--db-url", default=default_database_url())
    parser.add_argument("--clear-synthetic", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not Path(args.csv).is_file():
        print(f"IMDb CSV not found at {args.csv}; nothing imported")
        return 0
    engine = None
    try:
        # Validate before connecting; reflecting existing tables performs no DDL.
        read_ratings(args.csv)
        engine = local_engine(args.db_url)
        import_ratings(args.csv, engine, clear_synthetic=args.clear_synthetic, dry_run=args.dry_run)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
