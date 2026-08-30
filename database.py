"""
database.py — Relational database storage (PostgreSQL on Azure / SQLite local).

Backend selection
-----------------
If DATABASE_URL is set (e.g. Azure PostgreSQL Flexible Server), SQLAlchemy
connects to that PostgreSQL database. Otherwise, it defaults to a local
SQLite file (spotify_tokens.db).

Exports
-------
  SessionLocal    — SQLAlchemy session factory
  SpotifyUser     — SQLAlchemy ORM model
  SpotifyPlayEvent — SQLAlchemy ORM model
  User            — SQLAlchemy ORM model (Google identity)
  UserLike        — SQLAlchemy ORM model
  AniListUser     — SQLAlchemy ORM model
  Base            — declarative_base (for create_all)
  get_user, upsert_user, delete_user
  add_like, remove_like, get_likes
  upsert_google_user, get_user_by_google_sub
  get_anilist_user, upsert_anilist_user
  upsert_spotify_import_profile, get_spotify_import_profile
"""

import os
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from dotenv import load_dotenv

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Boolean, UniqueConstraint, ForeignKey, text, func, inspect
from sqlalchemy.orm import sessionmaker, relationship
from models.base import Base
from models.myntra import MyntraConnection, MyntraEvent, MyntraFeedback, MyntraProduct, MyntraProfile

load_dotenv()

_db_url = os.getenv("DATABASE_URL")
if _db_url:
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    _engine = create_engine(_db_url, pool_pre_ping=True)
else:
    _DB_PATH = os.getenv(
        "SQLITE_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "spotify_tokens.db"),
    )
    _engine = create_engine(f"sqlite:///{_DB_PATH}", connect_args={"check_same_thread": False})
engine = _engine

class SpotifyUser(Base):  # type: ignore[valid-type]
    """ORM model for local-dev SQLite user-token storage."""

    __tablename__ = "spotify_users"

    user_id = Column(String, primary_key=True, index=True)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    expires_at = Column(Integer, nullable=False)
    spotify_account_id = Column(String, nullable=True)
    spotify_display_name = Column(String, nullable=True)
    sync_enabled = Column(Boolean, default=False, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "spotify_account_id": self.spotify_account_id,
            "spotify_display_name": self.spotify_display_name,
            "sync_enabled": self.sync_enabled,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
        }

class User(Base):  # type: ignore[valid-type]
    """ORM model for Google-identity users."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    google_sub = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, nullable=False)
    name = Column(String, nullable=True)
    picture_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "google_sub": self.google_sub,
            "email": self.email,
            "name": self.name,
            "picture_url": self.picture_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

class UserLike(Base):  # type: ignore[valid-type]
    """ORM model for per-user cross-module likes (anime, amazon)."""

    __tablename__ = "user_likes"
    __table_args__ = (
        UniqueConstraint("user_id", "module", "item_id", name="uq_user_module_item"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    module = Column(String, nullable=False)   # "anime" | "amazon"
    item_id = Column(String, nullable=False)  # mal_id or product_id as str
    liked_at = Column(Integer, nullable=False)  # Unix epoch seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "module": self.module,
            "item_id": self.item_id,
            "liked_at": self.liked_at,
        }


class AniListUser(Base):  # type: ignore[valid-type]
    """ORM model for local-dev SQLite AniList user-token storage."""

    __tablename__ = "anilist_users"

    user_id = Column(String, primary_key=True, index=True)
    anilist_id = Column(Integer, nullable=False)
    anilist_username = Column(String, nullable=False)
    access_token = Column(String, nullable=False)
    connected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "anilist_id": self.anilist_id,
            "anilist_username": self.anilist_username,
            "access_token": self.access_token,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
        }

class SpotifyImportProfile(Base):  # type: ignore[valid-type]
    """ORM model for imported Spotify streaming history genre profiles."""

    __tablename__ = "spotify_import_profiles"

    user_id = Column(String, primary_key=True, index=True)
    genre_profile_json = Column(String, nullable=False)   # JSON {genre: weight}
    artist_summary_json = Column(String, nullable=True)   # JSON top-50 artists
    total_plays = Column(Integer, nullable=True)
    unique_artists = Column(Integer, nullable=True)
    imported_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "genre_profile_json": self.genre_profile_json,
            "artist_summary_json": self.artist_summary_json,
            "total_plays": self.total_plays,
            "unique_artists": self.unique_artists,
            "imported_at": self.imported_at.isoformat() if self.imported_at else None,
        }

class TouristSpot(Base):
    __tablename__ = "tourist_spots"

    place_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)
    price_tier = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    city = Column(String, nullable=False, default="Chennai")

class UserSpotFeedback(Base):
    __tablename__ = "user_spot_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.google_sub"), nullable=False, index=True)
    place_id = Column(String, ForeignKey("tourist_spots.place_id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    tag = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

TOURIST_SPOT_CATEGORIES = [
    "adventure_outdoor",
    "cultural_historic",
    "nightlife",
    "chill_scenic",
    "shopping_social",
    "offbeat_indie",
]

class DiningSpot(Base):
    """ORM model for restaurants/cafes catalog entries.

    Sourced from OpenStreetMap Overpass export — this is bootstrap data,
    NOT curated hand-written entries.  Descriptions and price tiers are
    not available in the OSM data and default to NULL.
    """
    __tablename__ = "dining_spots"

    place_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)
    description = Column(String, nullable=True)   # NULL — not in OSM data
    price_tier = Column(String, nullable=True)     # NULL — not in OSM data
    cuisine = Column(String, nullable=True)        # Raw OSM cuisine tag
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    city = Column(String, nullable=False, default="Chennai")
    osm_id = Column(String, nullable=True)         # e.g. "node/12345"

class UserDiningFeedback(Base):
    """User like/dislike feedback on dining spots — mirrors UserSpotFeedback."""
    __tablename__ = "user_dining_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.google_sub"), nullable=False, index=True)
    place_id = Column(String, ForeignKey("dining_spots.place_id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    tag = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

DINING_CATEGORIES = [
    "fine_dining",
    "casual_dining",
    "street_food_quick_bite",
    "cafe_coffee",
    "dessert_bakery",
    "bar_nightlife_dining",
]

class Movie(Base):  # type: ignore[valid-type]
    """ORM model for TMDB movie catalog entries.

    Each row represents a movie fetched from the TMDB API.
    The ``personal_rating`` field stores Raghav's own IMDb rating
    (1–10 float, nullable) imported from an IMDb CSV export.
    """

    __tablename__ = "movies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tmdb_id = Column(Integer, unique=True, nullable=False, index=True)
    imdb_id = Column(String, unique=True, nullable=True, index=True)  # "tt..." string
    title = Column(String, nullable=False)
    overview = Column(String, nullable=True)
    genres_json = Column(String, nullable=True)       # JSON list of genre strings, e.g. '["Action","Drama"]'
    release_year = Column(Integer, nullable=True)
    poster_url = Column(String, nullable=True)         # Full TMDB poster URL
    vote_average = Column(Float, nullable=True)       # TMDB average vote (0–10 scale)
    personal_rating = Column(Float, nullable=True)     # Raghav's IMDb rating (1–10 scale)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        import json as _json
        return {
            "id": self.id,
            "tmdb_id": self.tmdb_id,
            "imdb_id": self.imdb_id,
            "title": self.title,
            "overview": self.overview,
            "genres": _json.loads(self.genres_json) if self.genres_json else [],
            "release_year": self.release_year,
            "poster_url": self.poster_url,
            "vote_average": self.vote_average,
            "personal_rating": self.personal_rating,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

class SpotifyPlayEvent(Base):  # type: ignore[valid-type]
    """ORM model for deduplicated incremental Spotify play history events."""

    __tablename__ = "spotify_play_events"
    __table_args__ = (
        UniqueConstraint("user_id", "played_at", name="uq_user_played_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("spotify_users.user_id"), nullable=False, index=True)
    track_id = Column(String, nullable=False, index=True)
    track_name = Column(String, nullable=True)
    artist_names_json = Column(String, nullable=True)   # JSON-encoded list of artist names
    artist_ids_json = Column(String, nullable=True)     # JSON-encoded list of artist IDs
    album_name = Column(String, nullable=True)
    album_image_url = Column(String, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    played_at = Column(DateTime, nullable=False, index=True)  # value from Spotify's played_at field
    synced_at = Column(DateTime, nullable=False, server_default=func.now())

    def to_dict(self) -> Dict[str, Any]:
        import json as _json
        return {
            "id": self.id,
            "user_id": self.user_id,
            "track_id": self.track_id,
            "track_name": self.track_name,
            "artist_names": _json.loads(self.artist_names_json) if self.artist_names_json else [],
            "artist_ids": _json.loads(self.artist_ids_json) if self.artist_ids_json else [],
            "album_name": self.album_name,
            "album_image_url": self.album_image_url,
            "duration_ms": self.duration_ms,
            "played_at": self.played_at.isoformat() if self.played_at else None,
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
        }

def init_db():
    """Create all tables in the database, run schema migrations, and log created tables."""
    registered_tables = list(Base.metadata.tables.keys())
    print(f"[database] Running Base.metadata.create_all() for {len(registered_tables)} registered models: {registered_tables}")
    try:
        Base.metadata.create_all(bind=_engine)
    except Exception as err:
        print(f"[database] ERROR executing Base.metadata.create_all(): {err}")
        raise err

    # Inline schema migration to add new columns to existing DB if missing
    if _engine.dialect.name == "sqlite":
        try:
            with _engine.begin() as conn:
                result = conn.execute(text("PRAGMA table_info(spotify_users)"))
                columns = [row[1] for row in result]
                if "spotify_account_id" not in columns:
                    conn.execute(text("ALTER TABLE spotify_users ADD COLUMN spotify_account_id TEXT"))
                if "spotify_display_name" not in columns:
                    conn.execute(text("ALTER TABLE spotify_users ADD COLUMN spotify_display_name TEXT"))
                if "sync_enabled" not in columns:
                    conn.execute(text("ALTER TABLE spotify_users ADD COLUMN sync_enabled BOOLEAN DEFAULT 0"))
                if "last_synced_at" not in columns:
                    conn.execute(text("ALTER TABLE spotify_users ADD COLUMN last_synced_at TIMESTAMP"))

                # Migration for spotify_play_events new columns
                pe_result = conn.execute(text("PRAGMA table_info(spotify_play_events)"))
                pe_columns = [row[1] for row in pe_result]
                if "album_name" not in pe_columns:
                    conn.execute(text("ALTER TABLE spotify_play_events ADD COLUMN album_name TEXT"))
                if "album_image_url" not in pe_columns:
                    conn.execute(text("ALTER TABLE spotify_play_events ADD COLUMN album_image_url TEXT"))
                if "duration_ms" not in pe_columns:
                    conn.execute(text("ALTER TABLE spotify_play_events ADD COLUMN duration_ms INTEGER"))

                # Migration for movies table
                m_result = conn.execute(text("PRAGMA table_info(movies)"))
                m_columns = [row[1] for row in m_result]
                if "vote_average" not in m_columns:
                    conn.execute(text("ALTER TABLE movies ADD COLUMN vote_average REAL"))

                conn.execute(text("DROP TABLE IF EXISTS restaurants"))
                conn.execute(text("DROP TABLE IF EXISTS restaurant_reviews"))
        except Exception as e:
            print(f"[database] SQLite migration warning: {e}")

    try:
        inspector = inspect(_engine)
        tables = inspector.get_table_names()
        print(f"[database] Database tables confirmed present ({_engine.dialect.name}): {tables}")
        return tables
    except Exception as e:
        print(f"[database] Warning: Failed to inspect table names: {e}")
        return []

try:
    init_db()
except Exception as e:
    print(f"[database] Top-level init_db notice ({e}); will initialize during app lifespan startup.")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----- public API (local) -----

def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        user = db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first()
        return user.to_dict() if user else None
    finally:
        db.close()

def get_anilist_user(user_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        user = db.query(AniListUser).filter(AniListUser.user_id == user_id).first()
        return user.to_dict() if user else None
    finally:
        db.close()

def upsert_anilist_user(
    user_id: str,
    anilist_id: int,
    anilist_username: str,
    access_token: str,
) -> None:
    db = SessionLocal()
    try:
        user = db.query(AniListUser).filter(AniListUser.user_id == user_id).first()
        if user:
            user.anilist_id = anilist_id
            user.anilist_username = anilist_username
            user.access_token = access_token
        else:
            user = AniListUser(
                user_id=user_id,
                anilist_id=anilist_id,
                anilist_username=anilist_username,
                access_token=access_token,
            )
            db.add(user)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[database] upsert_anilist_user({user_id}): {e}")
    finally:
        db.close()

def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Look up either a Spotify or Google user by internal user_id."""
    db = SessionLocal()
    try:
        user = db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first()
        if user:
            return user.to_dict()
        user = db.query(User).filter(User.id == int(user_id)).first()
        return user.to_dict() if user else None
    except (ValueError, TypeError):
        return None
    finally:
        db.close()

def get_user_by_google_sub(google_sub: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.google_sub == google_sub).first()
        return user.to_dict() if user else None
    finally:
        db.close()

def upsert_google_user(
    google_sub: str,
    email: str,
    name: Optional[str],
    picture_url: Optional[str],
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.google_sub == google_sub).first()
        if user:
            user.email = email
            user.name = name
            user.picture_url = picture_url
        else:
            user = User(
                google_sub=google_sub,
                email=email,
                name=name,
                picture_url=picture_url,
            )
            db.add(user)
        db.commit()
        db.refresh(user)
        return user.to_dict()
    except Exception as e:
        db.rollback()
        print(f"[database] upsert_google_user({google_sub}): {e}")
        raise
    finally:
        db.close()

def upsert_user(
    user_id: str,
    access_token: str,
    refresh_token: Optional[str],
    expires_at: int,
    spotify_account_id: Optional[str] = None,
    spotify_display_name: Optional[str] = None,
) -> None:
    db = SessionLocal()
    try:
        user = db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first()
        if user:
            user.access_token = access_token
            if refresh_token:
                user.refresh_token = refresh_token
            user.expires_at = expires_at
            if spotify_account_id:
                user.spotify_account_id = spotify_account_id
            if spotify_display_name:
                user.spotify_display_name = spotify_display_name
        else:
            user = SpotifyUser(
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                spotify_account_id=spotify_account_id,
                spotify_display_name=spotify_display_name,
            )
            db.add(user)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[database] upsert_user({user_id}): {e}")
    finally:
        db.close()

def delete_user(user_id: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first()
        if user:
            db.delete(user)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"[database] delete_user({user_id}): {e}")
    finally:
        db.close()

def get_dynamodb_resource():  # noqa: D103
    raise NotImplementedError("DynamoDB support has been removed; this project is Azure/SQL-only.")

def add_like(user_id: str, module: str, item_id: str) -> None:
    """Record that user liked item_id in the given module. Idempotent."""
    db = SessionLocal()
    try:
        existing = (
            db.query(UserLike)
            .filter(
                UserLike.user_id == user_id,
                UserLike.module == module,
                UserLike.item_id == item_id,
            )
            .first()
        )
        if not existing:
            like = UserLike(
                user_id=user_id,
                module=module,
                item_id=item_id,
                liked_at=int(time.time()),
            )
            db.add(like)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"[database] add_like({user_id}, {module}, {item_id}): {e}")
    finally:
        db.close()

def remove_like(user_id: str, module: str, item_id: str) -> None:
    """Remove a like. No-op if the like doesn't exist."""
    db = SessionLocal()
    try:
        like = (
            db.query(UserLike)
            .filter(
                UserLike.user_id == user_id,
                UserLike.module == module,
                UserLike.item_id == item_id,
            )
            .first()
        )
        if like:
            db.delete(like)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"[database] remove_like({user_id}, {module}, {item_id}): {e}")
    finally:
        db.close()

def get_likes(user_id: str, module: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all likes for a user, optionally filtered by module."""
    db = SessionLocal()
    try:
        q = db.query(UserLike).filter(UserLike.user_id == user_id)
        if module:
            q = q.filter(UserLike.module == module)
        return [row.to_dict() for row in q.order_by(UserLike.liked_at.desc()).all()]
    finally:
        db.close()

def upsert_spotify_import_profile(
    user_id: str,
    genre_profile_json: str,
    artist_summary_json: Optional[str] = None,
    total_plays: Optional[int] = None,
    unique_artists: Optional[int] = None,
) -> None:
    """Store or update an imported Spotify streaming history genre profile."""
    db = SessionLocal()
    try:
        row = db.query(SpotifyImportProfile).filter(
            SpotifyImportProfile.user_id == user_id
        ).first()
        if row:
            row.genre_profile_json = genre_profile_json
            row.artist_summary_json = artist_summary_json
            row.total_plays = total_plays
            row.unique_artists = unique_artists
            row.imported_at = datetime.now(timezone.utc)
        else:
            row = SpotifyImportProfile(
                user_id=user_id,
                genre_profile_json=genre_profile_json,
                artist_summary_json=artist_summary_json,
                total_plays=total_plays,
                unique_artists=unique_artists,
            )
            db.add(row)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[database] upsert_spotify_import_profile({user_id}): {e}")
    finally:
        db.close()

def get_spotify_import_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the imported Spotify genre profile for a user, if any."""
    db = SessionLocal()
    try:
        row = db.query(SpotifyImportProfile).filter(
            SpotifyImportProfile.user_id == user_id
        ).first()
        return row.to_dict() if row else None
    finally:
        db.close()

