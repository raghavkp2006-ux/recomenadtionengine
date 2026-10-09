"""Profile endpoints: overview, connections status, resync, and domain disconnect."""

from datetime import datetime, timezone
import json
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import (
    SessionLocal,
    get_db,
    get_user_by_id,
    get_user,
    get_anilist_user,
    User,
    SpotifyUser,
    SpotifyPlayEvent,
    AniListUser,
    UserLike,
    RecommendationFeedback,
    UserSpotFeedback,
    UserDiningFeedback,
)
from models.myntra import MyntraConnection, MyntraEvent, MyntraFeedback, MyntraProfile
from models.profile import SyncLog
from services.auth import get_current_user_id
from services.sync_log import log_sync, get_latest_sync

router = APIRouter(prefix="/profile", tags=["profile"])


def _resolve_user_row(db: Session, user_id: str) -> Optional[User]:
    """Resolve a User record from numeric id, google_sub, or email."""
    try:
        u = db.query(User).filter(User.id == int(user_id)).first()
        if u:
            return u
    except (ValueError, TypeError):
        pass
    u = db.query(User).filter(User.google_sub == user_id).first()
    if u:
        return u
    return db.query(User).filter(User.email == user_id).first()


@router.get("/overview")
def get_profile_overview(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Returns user identity summary, Spotify connection snapshot,
    and activity counts across all domains.
    """
    user_row = _resolve_user_row(db, user_id)
    spotify_row = db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first()

    name = None
    email = None
    avatar_url = None
    member_since = None

    if user_row:
        name = user_row.name or (user_row.email.split("@")[0] if user_row.email else None)
        email = user_row.email
        avatar_url = user_row.picture_url
        member_since = user_row.created_at.isoformat() if user_row.created_at else None
    elif spotify_row:
        name = spotify_row.spotify_display_name or user_id
        email = ""
        avatar_url = None
        member_since = (
            spotify_row.last_synced_at.isoformat()
            if spotify_row.last_synced_at
            else datetime.now(timezone.utc).isoformat()
        )
    else:
        name = user_id
        email = ""
        avatar_url = None
        member_since = datetime.now(timezone.utc).isoformat()

    spotify_summary = None
    if spotify_row:
        spotify_summary = {
            "display_name": spotify_row.spotify_display_name or "Spotify User",
            "avatar": None,
        }

    # Cross-domain activity counts
    movies_rated = (
        db.query(RecommendationFeedback)
        .filter(
            RecommendationFeedback.user_id == user_id,
            RecommendationFeedback.domain == "movie",
        )
        .count()
    )

    places_rated = (
        db.query(UserSpotFeedback).filter(UserSpotFeedback.user_id == user_id).count()
        + db.query(UserDiningFeedback).filter(UserDiningFeedback.user_id == user_id).count()
    )

    anime_likes_count = (
        db.query(UserLike)
        .filter(UserLike.user_id == user_id, UserLike.module == "anime")
        .count()
    )

    products_viewed = (
        db.query(MyntraEvent).filter(MyntraEvent.user_id == user_id).count()
    )

    tracks_liked = (
        db.query(SpotifyPlayEvent).filter(SpotifyPlayEvent.user_id == user_id).count()
    )

    return {
        "name": name,
        "email": email,
        "avatar_url": avatar_url,
        "member_since": member_since,
        "spotify": spotify_summary,
        "counts": {
            "movies_rated": movies_rated,
            "places_rated": places_rated,
            "anime_logged": anime_likes_count,
            "products_viewed": products_viewed,
            "tracks_liked": tracks_liked,
        },
    }


@router.get("/connections")
def get_connections(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Returns connections status for spotify, anilist, myntra, movies, places, dining.
    Status: ok | error | needs_reconnect | never.
    """
    results = []

    # 1. Spotify
    spotify_row = db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first()
    spotify_latest = get_latest_sync(db, user_id, "spotify")
    spotify_connected = spotify_row is not None
    spotify_status = "never"
    spotify_items = 0
    spotify_error = None
    spotify_last_synced = None
    spotify_expires_at = None

    if spotify_connected and spotify_row:
        spotify_expires_at = spotify_row.expires_at
        spotify_items = (
            db.query(SpotifyPlayEvent).filter(SpotifyPlayEvent.user_id == user_id).count()
        )
        spotify_last_synced = (
            spotify_row.last_synced_at.isoformat() if spotify_row.last_synced_at else None
        )
        # Check token validity
        now_epoch = int(time.time())
        if spotify_row.expires_at and now_epoch > int(spotify_row.expires_at) and not spotify_row.refresh_token:
            spotify_status = "needs_reconnect"
            spotify_error = "Token expired and no refresh token available"
        elif not spotify_row.sync_enabled:
            spotify_status = "needs_reconnect"
            spotify_error = "Sync disabled"
        elif spotify_latest and spotify_latest.status == "error":
            spotify_status = "error"
            spotify_error = spotify_latest.error_message
        else:
            spotify_status = "ok"
    elif spotify_latest:
        spotify_status = spotify_latest.status
        spotify_error = spotify_latest.error_message
        spotify_last_synced = (
            spotify_latest.synced_at.isoformat() if spotify_latest.synced_at else None
        )

    results.append({
        "domain": "spotify",
        "connected": spotify_connected,
        "last_synced_at": spotify_last_synced,
        "status": spotify_status,
        "items_count": spotify_items,
        "error_message": spotify_error,
        "token_expires_at": spotify_expires_at,
    })

    # 2. AniList
    anilist_row = db.query(AniListUser).filter(AniListUser.user_id == user_id).first()
    anilist_latest = get_latest_sync(db, user_id, "anilist")
    anilist_connected = anilist_row is not None
    anilist_status = "never"
    anilist_items = db.query(UserLike).filter(UserLike.user_id == user_id, UserLike.module == "anime").count()
    anilist_error = None
    anilist_last_synced = None

    if anilist_connected and anilist_row:
        anilist_last_synced = (
            anilist_row.connected_at.isoformat() if anilist_row.connected_at else None
        )
        if anilist_latest and anilist_latest.status == "error":
            anilist_status = "error"
            anilist_error = anilist_latest.error_message
        elif not anilist_row.access_token:
            anilist_status = "needs_reconnect"
        else:
            anilist_status = "ok"
    elif anilist_latest:
        anilist_status = anilist_latest.status
        anilist_error = anilist_latest.error_message
        anilist_last_synced = (
            anilist_latest.synced_at.isoformat() if anilist_latest.synced_at else None
        )

    results.append({
        "domain": "anilist",
        "connected": anilist_connected,
        "last_synced_at": anilist_last_synced,
        "status": anilist_status,
        "items_count": anilist_items,
        "error_message": anilist_error,
    })

    # 3. Myntra
    myntra_conn = db.get(MyntraConnection, user_id)
    myntra_latest = get_latest_sync(db, user_id, "myntra")
    myntra_connected = bool(myntra_conn is not None and myntra_conn.enabled)
    myntra_events_count = (
        db.query(MyntraEvent).filter(MyntraEvent.user_id == user_id).count()
    )
    latest_event = (
        db.query(MyntraEvent)
        .filter(MyntraEvent.user_id == user_id)
        .order_by(desc(MyntraEvent.occurred_at))
        .first()
    )
    last_event_at = (
        latest_event.occurred_at.isoformat() if latest_event and latest_event.occurred_at else None
    )
    products_captured = (
        db.query(MyntraEvent.product_id)
        .filter(MyntraEvent.user_id == user_id, MyntraEvent.product_id.isnot(None))
        .distinct()
        .count()
    )

    myntra_status = "ok" if (myntra_connected or myntra_events_count > 0) else "never"
    if myntra_latest and myntra_latest.status in ("error", "needs_reconnect"):
        myntra_status = myntra_latest.status

    results.append({
        "domain": "myntra",
        "connected": myntra_connected,
        "last_synced_at": last_event_at or (myntra_conn.updated_at.isoformat() if myntra_conn and myntra_conn.updated_at else None),
        "status": myntra_status,
        "items_count": myntra_events_count,
        "error_message": myntra_latest.error_message if myntra_latest else None,
        "products_captured": products_captured,
        "last_event_at": last_event_at,
    })

    # 4. Movies
    movie_count = (
        db.query(RecommendationFeedback)
        .filter(
            RecommendationFeedback.user_id == user_id,
            RecommendationFeedback.domain == "movie",
        )
        .count()
    )
    movie_latest_feedback = (
        db.query(RecommendationFeedback)
        .filter(
            RecommendationFeedback.user_id == user_id,
            RecommendationFeedback.domain == "movie",
        )
        .order_by(desc(RecommendationFeedback.created_at))
        .first()
    )
    results.append({
        "domain": "movies",
        "connected": movie_count > 0,
        "last_synced_at": (
            movie_latest_feedback.created_at.isoformat()
            if movie_latest_feedback
            else None
        ),
        "status": "ok" if movie_count > 0 else "never",
        "items_count": movie_count,
        "error_message": None,
    })

    # 5. Places (Tourist spots)
    places_count = (
        db.query(UserSpotFeedback).filter(UserSpotFeedback.user_id == user_id).count()
    )
    places_latest = (
        db.query(UserSpotFeedback)
        .filter(UserSpotFeedback.user_id == user_id)
        .order_by(desc(UserSpotFeedback.created_at))
        .first()
    )
    results.append({
        "domain": "places",
        "connected": places_count > 0,
        "last_synced_at": (
            places_latest.created_at.isoformat() if places_latest else None
        ),
        "status": "ok" if places_count > 0 else "never",
        "items_count": places_count,
        "error_message": None,
    })

    # 6. Dining
    dining_count = (
        db.query(UserDiningFeedback).filter(UserDiningFeedback.user_id == user_id).count()
    )
    dining_latest = (
        db.query(UserDiningFeedback)
        .filter(UserDiningFeedback.user_id == user_id)
        .order_by(desc(UserDiningFeedback.created_at))
        .first()
    )
    results.append({
        "domain": "dining",
        "connected": dining_count > 0,
        "last_synced_at": (
            dining_latest.created_at.isoformat() if dining_latest else None
        ),
        "status": "ok" if dining_count > 0 else "never",
        "items_count": dining_count,
        "error_message": None,
    })

    return results


@router.post("/connections/{domain}/resync")
def resync_connection(
    domain: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Triggers domain sync, logs result, and returns the new status.
    """
    valid_domains = {"spotify", "anilist", "myntra", "movies", "places", "dining"}
    if domain not in valid_domains:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

    if domain == "spotify":
        from services.spotify_sync import sync_user_recent_plays
        result = sync_user_recent_plays(user_id)
        status_str = result.get("status", "ok")
        new_plays = result.get("new_plays", 0)
        items = db.query(SpotifyPlayEvent).filter(SpotifyPlayEvent.user_id == user_id).count()
        return {
            "domain": "spotify",
            "status": "needs_reconnect" if status_str in ("sync_disabled", "token_invalid") else status_str,
            "items_count": items,
            "new_items": new_plays,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "error_message": result.get("error"),
        }

    elif domain == "anilist":
        anilist_user = db.query(AniListUser).filter(AniListUser.user_id == user_id).first()
        if not anilist_user:
            log_sync(db, user_id, "anilist", "needs_reconnect", 0, "Not connected")
            return {
                "domain": "anilist",
                "status": "needs_reconnect",
                "items_count": 0,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "error_message": "AniList account not connected",
            }
        try:
            from services.anilist_client import fetch_user_anime_list
            items = fetch_user_anime_list(anilist_user.access_token, anilist_user.anilist_id)
            count = len(items) if items else 0
            log_sync(db, user_id, "anilist", "ok", items_count=count)
            return {
                "domain": "anilist",
                "status": "ok",
                "items_count": count,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "error_message": None,
            }
        except Exception as e:
            log_sync(db, user_id, "anilist", "needs_reconnect", 0, str(e))
            return {
                "domain": "anilist",
                "status": "needs_reconnect",
                "items_count": 0,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "error_message": str(e),
            }

    elif domain == "myntra":
        from services.myntra_profile import rebuild_profile
        rebuild_profile(db, user_id)
        db.commit()
        count = db.query(MyntraEvent).filter(MyntraEvent.user_id == user_id).count()
        return {
            "domain": "myntra",
            "status": "ok",
            "items_count": count,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "error_message": None,
        }

    elif domain == "movies":
        count = (
            db.query(RecommendationFeedback)
            .filter(RecommendationFeedback.user_id == user_id, RecommendationFeedback.domain == "movie")
            .count()
        )
        log_sync(db, user_id, "movies", "ok", items_count=count)
        return {
            "domain": "movies",
            "status": "ok",
            "items_count": count,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "error_message": None,
        }

    elif domain == "places":
        count = db.query(UserSpotFeedback).filter(UserSpotFeedback.user_id == user_id).count()
        log_sync(db, user_id, "places", "ok", items_count=count)
        return {
            "domain": "places",
            "status": "ok",
            "items_count": count,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "error_message": None,
        }

    elif domain == "dining":
        count = db.query(UserDiningFeedback).filter(UserDiningFeedback.user_id == user_id).count()
        log_sync(db, user_id, "dining", "ok", items_count=count)
        return {
            "domain": "dining",
            "status": "ok",
            "items_count": count,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "error_message": None,
        }


@router.delete("/connections/{domain}")
def disconnect_domain(
    domain: str,
    confirm: bool = Query(False, description="Must be true to confirm disconnect"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Removes ONLY the specified domain's stored tokens/signals for the user.
    Requires ?confirm=true. Never deletes the user account.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Disconnect must be explicitly confirmed via ?confirm=true",
        )

    valid_domains = {"spotify", "anilist", "myntra", "movies", "places", "dining"}
    if domain not in valid_domains:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

    if domain == "spotify":
        db.query(SpotifyPlayEvent).filter(SpotifyPlayEvent.user_id == user_id).delete(synchronize_session=False)
        db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).delete(synchronize_session=False)
    elif domain == "anilist":
        db.query(AniListUser).filter(AniListUser.user_id == user_id).delete(synchronize_session=False)
    elif domain == "myntra":
        db.query(MyntraEvent).filter(MyntraEvent.user_id == user_id).delete(synchronize_session=False)
        db.query(MyntraFeedback).filter(MyntraFeedback.user_id == user_id).delete(synchronize_session=False)
        db.query(MyntraProfile).filter(MyntraProfile.user_id == user_id).delete(synchronize_session=False)
        db.query(MyntraConnection).filter(MyntraConnection.user_id == user_id).delete(synchronize_session=False)
    elif domain == "movies":
        db.query(RecommendationFeedback).filter(
            RecommendationFeedback.user_id == user_id,
            RecommendationFeedback.domain == "movie",
        ).delete(synchronize_session=False)
    elif domain == "places":
        db.query(UserSpotFeedback).filter(UserSpotFeedback.user_id == user_id).delete(synchronize_session=False)
    elif domain == "dining":
        db.query(UserDiningFeedback).filter(UserDiningFeedback.user_id == user_id).delete(synchronize_session=False)

    log_sync(db, user_id, domain, "never", 0, None)
    db.commit()

    return {
        "ok": True,
        "domain": domain,
        "message": f"Successfully disconnected {domain} and cleared associated signals",
    }
