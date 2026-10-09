"""Profile endpoints: overview, connections status, resync, and domain disconnect."""

from datetime import datetime, timezone
import json
import math
import time
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
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
from models.profile import SyncLog, TasteControls, PublicProfile, DEFAULT_VISIBILITY
from services.auth import get_current_user_id
from services.sync_log import log_sync, get_latest_sync

router = APIRouter(prefix="/profile", tags=["profile"])
public_router = APIRouter(tags=["public_profile"])


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


@router.get("/insights")
def get_insights(
    range: str = Query("medium", pattern="^(short|medium|long)$"),
    refresh: bool = Query(False),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Computes taste insights from Spotify top artists/tracks:
    genres, entropy diversity, mainstream score, decades histogram,
    discovery rate, taste evolution, and rule-based personality.
    """
    from services.profile_insights import compute_profile_insights
    return compute_profile_insights(
        user_id=user_id,
        time_range_key=range,
        refresh=refresh,
        db=db,
    )


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


# ---------------------------------------------------------------------------
# PHASE 4: CONTROLS & FEEDBACK HISTORY
# ---------------------------------------------------------------------------

class DomainWeightsModel(BaseModel):
    music: int = Field(ge=0, le=100)
    anime: int = Field(ge=0, le=100)
    movies: int = Field(ge=0, le=100)
    fashion: int = Field(ge=0, le=100)


class SlidersModel(BaseModel):
    energy: int = Field(50, ge=0, le=100)
    obscurity: int = Field(50, ge=0, le=100)
    novelty: int = Field(50, ge=0, le=100)


class PinnedHiddenModel(BaseModel):
    artists: List[str] = Field(default_factory=list)
    genres: List[str] = Field(default_factory=list)


class UpdateTasteControlsPayload(BaseModel):
    domain_weights: Optional[DomainWeightsModel] = None
    sliders: Optional[SlidersModel] = None
    pinned: Optional[PinnedHiddenModel] = None
    hidden: Optional[PinnedHiddenModel] = None


@router.get("/controls")
def get_taste_controls(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Read stored taste controls for user, creating defaults if not yet present."""
    from models.profile import TasteControls
    row = db.query(TasteControls).filter(TasteControls.user_id == user_id).first()
    if not row:
        row = TasteControls(user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row.to_dict()


@router.put("/controls")
def update_taste_controls(
    payload: UpdateTasteControlsPayload,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Update taste controls.
    Validation:
      - domain_weights must be ints 0-100 summing to 100
      - sliders 0-100
      - pinned/hidden lists capped at 50 items each
    """
    from models.profile import TasteControls

    # Validate domain_weights
    if payload.domain_weights is not None:
        dw = payload.domain_weights
        total_w = dw.music + dw.anime + dw.movies + dw.fashion
        if total_w != 100:
            raise HTTPException(
                status_code=400,
                detail=f"domain_weights must sum to 100 (got {total_w})",
            )

    # Validate pinned
    if payload.pinned is not None:
        if len(payload.pinned.artists) > 50 or len(payload.pinned.genres) > 50:
            raise HTTPException(
                status_code=400,
                detail="pinned artists and genres are capped at 50 items each",
            )

    # Validate hidden
    if payload.hidden is not None:
        if len(payload.hidden.artists) > 50 or len(payload.hidden.genres) > 50:
            raise HTTPException(
                status_code=400,
                detail="hidden artists and genres are capped at 50 items each",
            )

    row = db.query(TasteControls).filter(TasteControls.user_id == user_id).first()
    if not row:
        row = TasteControls(user_id=user_id)
        db.add(row)

    if payload.domain_weights is not None:
        row.domain_weights_json = json.dumps(payload.domain_weights.dict())
    if payload.sliders is not None:
        row.sliders_json = json.dumps(payload.sliders.dict())
    if payload.pinned is not None:
        row.pinned_json = json.dumps(payload.pinned.dict())
    if payload.hidden is not None:
        row.hidden_json = json.dumps(payload.hidden.dict())

    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.get("/feedback-history")
def get_feedback_history(
    domain: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Returns feedback history rows, newest first, with title and domain."""
    items: List[Dict[str, Any]] = []

    # 1. RecommendationFeedback (movie, music)
    q_rf = db.query(RecommendationFeedback).filter(RecommendationFeedback.user_id == user_id)
    if domain:
        q_rf = q_rf.filter(RecommendationFeedback.domain == domain)
    for row in q_rf.order_by(desc(RecommendationFeedback.created_at)).limit(limit + offset).all():
        items.append({
            "id": row.id,
            "domain": row.domain,
            "item_id": row.item_id,
            "title": f"{row.domain.capitalize()} #{row.item_id}",
            "action": row.action,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })

    # 2. Tourist spot feedback
    if not domain or domain in ("places", "spots", "tourist"):
        for row in db.query(UserSpotFeedback).filter(UserSpotFeedback.user_id == user_id).order_by(desc(UserSpotFeedback.created_at)).limit(limit + offset).all():
            items.append({
                "id": row.id,
                "domain": "places",
                "item_id": row.place_id,
                "title": f"Spot #{row.place_id}",
                "action": f"Rated {row.rating}★",
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })

    # 3. Dining feedback
    if not domain or domain in ("dining", "cafes", "food"):
        for row in db.query(UserDiningFeedback).filter(UserDiningFeedback.user_id == user_id).order_by(desc(UserDiningFeedback.created_at)).limit(limit + offset).all():
            items.append({
                "id": row.id,
                "domain": "dining",
                "item_id": row.place_id,
                "title": f"Dining #{row.place_id}",
                "action": f"Rated {row.rating}★",
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })

    # 4. Myntra feedback
    if not domain or domain in ("fashion", "myntra"):
        for row in db.query(MyntraFeedback).filter(MyntraFeedback.user_id == user_id).order_by(desc(MyntraFeedback.created_at)).limit(limit + offset).all():
            items.append({
                "id": row.id,
                "domain": "fashion",
                "item_id": row.product_id,
                "title": f"Product #{row.product_id}",
                "action": row.feedback,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })

    # Sort merged newest first
    items.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return items[offset : offset + limit]


@router.delete("/feedback-history")
def reset_feedback_history(
    domain: Optional[str] = Query(None),
    confirm: bool = Query(False, description="Must be true to confirm reset"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Resets feedback for one domain, or all domains when omitted. Requires ?confirm=true."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Reset feedback history must be explicitly confirmed via ?confirm=true",
        )

    deleted_count = 0
    if not domain or domain in ("movie", "movies", "music"):
        q = db.query(RecommendationFeedback).filter(RecommendationFeedback.user_id == user_id)
        if domain:
            canonical_d = "movie" if domain == "movies" else domain
            q = q.filter(RecommendationFeedback.domain == canonical_d)
        deleted_count += q.delete(synchronize_session=False)

    if not domain or domain in ("places", "spots"):
        deleted_count += db.query(UserSpotFeedback).filter(UserSpotFeedback.user_id == user_id).delete(synchronize_session=False)

    if not domain or domain in ("dining", "cafes"):
        deleted_count += db.query(UserDiningFeedback).filter(UserDiningFeedback.user_id == user_id).delete(synchronize_session=False)

    if not domain or domain in ("fashion", "myntra"):
        deleted_count += db.query(MyntraFeedback).filter(MyntraFeedback.user_id == user_id).delete(synchronize_session=False)

    db.commit()
    return {
        "ok": True,
        "domain": domain or "all",
        "deleted": deleted_count,
        "message": f"Successfully reset feedback history for {domain or 'all domains'}",
    }


# ===========================================================================
# Phase 5: Timeline & Cross-Domain Bridges
# ===========================================================================

@router.get("/timeline")
def get_timeline(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Merged chronological feed of the user's latest interactions across all 6 domains."""
    timeline: List[Dict[str, Any]] = []

    # 1. Spotify plays
    try:
        spotify_plays = (
            db.query(SpotifyPlayEvent)
            .filter(SpotifyPlayEvent.user_id == user_id)
            .order_by(desc(SpotifyPlayEvent.played_at))
            .limit(limit)
            .all()
        )
        for p in spotify_plays:
            artists_list = json.loads(p.artist_names_json) if p.artist_names_json else []
            first_artist = artists_list[0] if artists_list else None
            timeline.append({
                "domain": "spotify",
                "title": p.track_name or "Unknown Track",
                "subtitle": f"Played track by {first_artist}" if first_artist else "Track played",
                "image": p.album_image_url,
                "at": p.played_at.isoformat() if p.played_at else datetime.now(timezone.utc).isoformat(),
            })
    except Exception:
        pass

    # 2. AniList / Anime likes
    try:
        anime_likes = (
            db.query(UserLike)
            .filter(UserLike.user_id == user_id)
            .order_by(desc(UserLike.liked_at))
            .limit(limit)
            .all()
        )
        for al in anime_likes:
            dt_str = datetime.fromtimestamp(al.liked_at, tz=timezone.utc).isoformat() if al.liked_at else datetime.now(timezone.utc).isoformat()
            timeline.append({
                "domain": "anilist" if al.module == "anime" else al.module,
                "title": f"Liked item #{al.item_id}",
                "subtitle": f"Favorited in {al.module}",
                "image": None,
                "at": dt_str,
            })
    except Exception:
        pass

    # 3. Movie feedback / Rec feedback
    try:
        movie_fb = (
            db.query(RecommendationFeedback)
            .filter(RecommendationFeedback.user_id == user_id)
            .order_by(desc(RecommendationFeedback.created_at))
            .limit(limit)
            .all()
        )
        for m in movie_fb:
            d_name = "movies" if m.domain == "movie" else m.domain
            timeline.append({
                "domain": d_name,
                "title": m.item_id or "Item",
                "subtitle": f"{m.feedback_type.title()} feedback on {d_name}",
                "image": None,
                "at": m.created_at.isoformat() if m.created_at else datetime.now(timezone.utc).isoformat(),
            })
    except Exception:
        pass

    # 4. Tourist spots
    try:
        spot_fb = (
            db.query(UserSpotFeedback)
            .filter(UserSpotFeedback.user_id == user_id)
            .order_by(desc(UserSpotFeedback.created_at))
            .limit(limit)
            .all()
        )
        for sf in spot_fb:
            timeline.append({
                "domain": "places",
                "title": f"Spot #{sf.spot_id}",
                "subtitle": f"Marked as {sf.feedback_type}",
                "image": None,
                "at": sf.created_at.isoformat() if sf.created_at else datetime.now(timezone.utc).isoformat(),
            })
    except Exception:
        pass

    # 5. Dining spots
    try:
        dine_fb = (
            db.query(UserDiningFeedback)
            .filter(UserDiningFeedback.user_id == user_id)
            .order_by(desc(UserDiningFeedback.created_at))
            .limit(limit)
            .all()
        )
        for df in dine_fb:
            timeline.append({
                "domain": "dining",
                "title": f"Place #{df.dining_id}",
                "subtitle": f"Marked as {df.feedback_type}",
                "image": None,
                "at": df.created_at.isoformat() if df.created_at else datetime.now(timezone.utc).isoformat(),
            })
    except Exception:
        pass

    # 6. Myntra events & feedback
    try:
        myntra_events = (
            db.query(MyntraEvent)
            .filter(MyntraEvent.user_id == user_id)
            .order_by(desc(MyntraEvent.created_at))
            .limit(limit)
            .all()
        )
        for me in myntra_events:
            timeline.append({
                "domain": "myntra",
                "title": f"Product #{me.product_id}",
                "subtitle": f"{me.event_type.replace('_', ' ').title()} in fashion",
                "image": None,
                "at": me.created_at.isoformat() if me.created_at else datetime.now(timezone.utc).isoformat(),
            })
    except Exception:
        pass

    timeline.sort(key=lambda x: x["at"] or "", reverse=True)
    return timeline[:limit]


@router.get("/bridges")
def get_bridges(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Calculates top 6 cross-domain bridges based on the user's genre signals and crosswalks."""
    from services.taste_profile import (
        GENRE_CROSSWALK,
        TOURISM_CROSSWALK,
        MOVIE_CROSSWALK,
        DINING_CROSSWALK,
    )
    from services.fashion_crosswalk import FASHION_CROSSWALK

    bridges: List[Dict[str, Any]] = []

    # Get user taste profile or insights genres
    sp_user = db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first()
    top_music_genres: List[str] = []
    if sp_user and sp_user.top_genres:
        try:
            tg = json.loads(sp_user.top_genres)
            if isinstance(tg, list):
                top_music_genres = [str(g).lower() for g in tg]
        except Exception:
            pass

    if not top_music_genres:
        top_music_genres = ["rock", "electronic", "pop", "indie", "jazz"]

    # 1. Music -> Anime bridge (via GENRE_CROSSWALK)
    for mg in top_music_genres:
        if mg in GENRE_CROSSWALK:
            targets = GENRE_CROSSWALK[mg]
            bridges.append({
                "from": {"domain": "music", "label": mg.title()},
                "to": {"domain": "anime", "label": targets[0].title() if targets else "Action"},
                "strength": 0.88,
                "reason": f"Listeners of {mg} frequently gravitate toward {', '.join(targets[:2])} stories.",
            })
            break

    # 2. Music -> Movie bridge (via MOVIE_CROSSWALK)
    for mg in top_music_genres:
        if mg in MOVIE_CROSSWALK:
            targets = MOVIE_CROSSWALK[mg]
            bridges.append({
                "from": {"domain": "music", "label": mg.title()},
                "to": {"domain": "movies", "label": targets[0].title() if targets else "Drama"},
                "strength": 0.82,
                "reason": f"{mg.title()} sonic textures map to cinematic {targets[0]} themes.",
            })
            break

    # 3. Music -> Places bridge (via TOURISM_CROSSWALK)
    for mg in top_music_genres:
        if mg in TOURISM_CROSSWALK:
            targets = TOURISM_CROSSWALK[mg]
            bridges.append({
                "from": {"domain": "music", "label": mg.title()},
                "to": {"domain": "places", "label": targets[0].replace("_", " ").title() if targets else "Outdoors"},
                "strength": 0.75,
                "reason": f"{mg.title()} energy correlates with {targets[0].replace('_', ' ')} destinations.",
            })
            break

    # 4. Music -> Dining bridge (via DINING_CROSSWALK)
    for mg in top_music_genres:
        if mg in DINING_CROSSWALK:
            targets = DINING_CROSSWALK[mg]
            bridges.append({
                "from": {"domain": "music", "label": mg.title()},
                "to": {"domain": "dining", "label": targets[0].replace("_", " ").title() if targets else "Cafes"},
                "strength": 0.72,
                "reason": f"Vibe matching connects {mg.title()} to {targets[0].replace('_', ' ')} spots.",
            })
            break

    # 5. Media -> Fashion bridge (via FASHION_CROSSWALK)
    for mg in ["action", "drama", "fantasy", "romance", "psychological"]:
        if mg in FASHION_CROSSWALK:
            f_attrs = FASHION_CROSSWALK[mg]
            first_color = f_attrs.get("colours", ["dark"])[0]
            bridges.append({
                "from": {"domain": "media", "label": mg.title()},
                "to": {"domain": "fashion", "label": f"{first_color.title()} Aesthetics"},
                "strength": 0.78,
                "reason": f"Apparel palettes ({first_color}, {f_attrs.get('patterns', ['solid'])[0]}) reflect {mg} tastes.",
            })
            break

    # 6. Anime -> Dining bridge
    bridges.append({
        "from": {"domain": "anime", "label": "Slice of Life"},
        "to": {"domain": "dining", "label": "Cozy Cafes"},
        "strength": 0.85,
        "reason": "Iyashikei and slice-of-life anime affinities strongly map to relaxed third-place cafes.",
    })

    return bridges[:6]


@router.get("/taste-tags")
def get_taste_tags(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Returns top 8 cross-domain taste tags representing the user's unified persona."""
    from services.taste_profile import GENRE_CROSSWALK, MOVIE_CROSSWALK

    tags = set()
    sp_user = db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first()
    if sp_user and sp_user.top_genres:
        try:
            tg = json.loads(sp_user.top_genres)
            if isinstance(tg, list):
                for g in tg[:5]:
                    g_clean = str(g).lower()
                    tags.add(f"{g_clean.title()} Connoisseur")
                    if g_clean in GENRE_CROSSWALK:
                        tags.add(f"{GENRE_CROSSWALK[g_clean][0].title()} Explorer")
                    if g_clean in MOVIE_CROSSWALK:
                        tags.add(f"{MOVIE_CROSSWALK[g_clean][0].title()} Cinephile")
        except Exception:
            pass

    # Add fallback tags if needed to guarantee at least 6-8 tags
    defaults = [
        "Aesthetic Minimalist",
        "Curated Nomad",
        "Night Owl Soundscape",
        "Café Hopper",
        "Visual Storyteller",
        "Eclectic Collector",
        "Dusk Harmonizer",
        "Urban Pathfinder",
    ]
    for d in defaults:
        if len(tags) >= 8:
            break
        tags.add(d)

    return list(tags)[:8]


# ===========================================================================
# Phase 6: Public Profile, Sharing, and Taste Compatibility
# ===========================================================================

class VisibilityToggles(BaseModel):
    genres: Optional[bool] = None
    top_artists: Optional[bool] = None
    stats: Optional[bool] = None
    connections: Optional[bool] = None
    personality: Optional[bool] = None


class UpdateVisibilityRequest(BaseModel):
    is_public: Optional[bool] = None
    visibility: Optional[VisibilityToggles] = None


def _get_or_create_public_profile(db: Session, user_id: str) -> PublicProfile:
    row = db.query(PublicProfile).filter(PublicProfile.user_id == user_id).first()
    if not row:
        slug = uuid.uuid4().hex[:10]
        row = PublicProfile(
            user_id=user_id,
            slug=slug,
            is_public=False,
            visibility_json=json.dumps(DEFAULT_VISIBILITY),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    elif not row.slug:
        row.slug = uuid.uuid4().hex[:10]
        db.commit()
        db.refresh(row)
    return row


@router.get("/visibility")
def get_profile_visibility(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Fetch current user's public profile status, slug, and privacy visibility toggles."""
    row = _get_or_create_public_profile(db, user_id)
    return row.to_dict()


@router.put("/visibility")
def update_profile_visibility(
    payload: UpdateVisibilityRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Updates is_public toggle and granular visibility settings for the user's public passport."""
    row = _get_or_create_public_profile(db, user_id)

    if payload.is_public is not None:
        row.is_public = bool(payload.is_public)

    if payload.visibility is not None:
        curr_vis = row.get_visibility()
        vis_dump = payload.visibility.model_dump(exclude_unset=True)
        for k, v in vis_dump.items():
            if v is not None:
                curr_vis[k] = bool(v)
        row.visibility_json = json.dumps(curr_vis)

    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@public_router.get("/public/profile/{slug}")
def get_public_profile(
    slug: str,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Public unauthenticated endpoint for public taste passport.
    Returns 404 if profile is private or not found.
    Sets Cache-Control: no-store.
    STRICT PRIVACY: Leaks ONLY toggled fields. NEVER returns user_id, email, google_sub, or tokens.
    """
    response.headers["Cache-Control"] = "no-store"

    pub = db.query(PublicProfile).filter(PublicProfile.slug == slug).first()
    if not pub or not pub.is_public:
        raise HTTPException(
            status_code=404,
            detail="Profile not found or is set to private.",
        )

    visibility = pub.get_visibility()
    target_user_id = pub.user_id

    # Resolve safe display name
    user_row = _resolve_user_row(db, target_user_id)
    display_name = "Taste Explorer"
    if user_row and user_row.name:
        display_name = user_row.name.split()[0]  # First name only for privacy

    # Build safe public payload
    public_data: Dict[str, Any] = {
        "slug": pub.slug,
        "display_name": display_name,
        "is_public": True,
        "visibility": visibility,
        "updated_at": pub.updated_at.isoformat() if pub.updated_at else None,
    }

    # Fetch insights data if any insights toggles are enabled
    needs_insights = any([
        visibility.get("genres"),
        visibility.get("top_artists"),
        visibility.get("stats"),
        visibility.get("personality"),
    ])

    insights = None
    if needs_insights:
        try:
            from services.profile_insights import compute_profile_insights
            insights = compute_profile_insights(user_id=target_user_id, time_range_key="medium", refresh=False, db=db)
        except Exception:
            pass

    if visibility.get("genres") and insights:
        public_data["top_genres"] = insights.get("top_genres", [])
    if visibility.get("top_artists") and insights:
        # Provide rarest/top artist if safe
        public_data["rarest"] = insights.get("rarest", {})
    if visibility.get("stats") and insights:
        public_data["diversity"] = insights.get("diversity", 0.0)
        public_data["mainstream_score"] = insights.get("mainstream_score", 0.0)
        public_data["obscurity_score"] = insights.get("obscurity_score", 0.0)
        public_data["decades"] = insights.get("decades", [])
    if visibility.get("personality") and insights:
        public_data["personality"] = insights.get("personality", {})

    if visibility.get("connections"):
        # Safe count of active connections
        active_domains = []
        if db.query(SpotifyUser).filter(SpotifyUser.user_id == target_user_id).first():
            active_domains.append("Spotify")
        if db.query(AniListUser).filter(AniListUser.user_id == target_user_id).first():
            active_domains.append("AniList")
        if db.query(MyntraConnection).filter(MyntraConnection.user_id == target_user_id).first():
            active_domains.append("Myntra")
        public_data["active_connections"] = active_domains

    return public_data


@router.get("/compatibility/{slug}")
def get_taste_compatibility(
    slug: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Computes taste compatibility (cosine similarity of genre distribution)
    between the logged-in user and the owner of the public profile slug.
    """
    other_pub = db.query(PublicProfile).filter(PublicProfile.slug == slug).first()
    if not other_pub or not other_pub.is_public:
        raise HTTPException(
            status_code=404,
            detail="Target profile not found or is set to private.",
        )

    from services.profile_insights import compute_profile_insights

    # 1. Current user genres
    my_insights = compute_profile_insights(user_id=user_id, time_range_key="medium", refresh=False, db=db)
    my_genres_map = {g["genre"].lower(): g["weight"] for g in my_insights.get("top_genres", [])}

    # 2. Target user genres
    other_insights = compute_profile_insights(user_id=other_pub.user_id, time_range_key="medium", refresh=False, db=db)
    other_genres_map = {g["genre"].lower(): g["weight"] for g in other_insights.get("top_genres", [])}

    all_genres = set(my_genres_map.keys()) | set(other_genres_map.keys())
    if not all_genres:
        return {
            "score_pct": 50,
            "shared_genres": [],
            "shared_artists": [],
            "message": "Both profiles are newly created. Baseline compatibility estimated at 50%.",
        }

    # Vector dot product and norms
    dot_product = sum(my_genres_map.get(g, 0.0) * other_genres_map.get(g, 0.0) for g in all_genres)
    norm_a = math.sqrt(sum(v * v for v in my_genres_map.values()))
    norm_b = math.sqrt(sum(v * v for v in other_genres_map.values()))

    if norm_a == 0 or norm_b == 0:
        sim = 0.5
    else:
        sim = dot_product / (norm_a * norm_b)

    score_pct = int(round(sim * 100))
    shared_genres = [g.title() for g in sorted(all_genres) if my_genres_map.get(g, 0) > 0 and other_genres_map.get(g, 0) > 0]

    return {
        "score_pct": max(1, min(100, score_pct)),
        "shared_genres": shared_genres[:5],
        "shared_artists": [],
        "message": f"{score_pct}% taste resonance across music and media genres.",
    }


# ===========================================================================
# Phase 7: Data Export / Wipe & Spotify Playlist Generation
# ===========================================================================

class CreatePlaylistRequest(BaseModel):
    name: str = "Poly_Taste Discovery"
    range: str = "medium"


@router.get("/export")
def export_user_data(
    response: Response,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Exports all user signals and history across domains as downloadable JSON.
    Excludes all tokens (spotify access/refresh tokens, session keys).
    Sets Content-Disposition header.
    """
    user_row = _resolve_user_row(db, user_id)
    email = user_row.email if user_row else "user"
    filename = f"polytaste-export-{email.split('@')[0]}.json"

    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Content-Type"] = "application/json"

    export_payload: Dict[str, Any] = {
        "version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {
            "display_name": user_row.name if user_row else None,
            "theme": user_row.theme if user_row else "dark",
        },
        "connections": {},
        "taste_controls": {},
        "feedback_history": [],
        "recent_plays": [],
    }

    # 1. Taste Controls
    ctrl = db.query(TasteControls).filter(TasteControls.user_id == user_id).first()
    if ctrl:
        export_payload["taste_controls"] = ctrl.to_dict()

    # 2. Connections summary (NO TOKENS)
    sp_user = db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).first()
    if sp_user:
        export_payload["connections"]["spotify"] = {
            "account_id": sp_user.spotify_account_id,
            "display_name": sp_user.spotify_display_name,
            "last_synced_at": sp_user.last_synced_at.isoformat() if sp_user.last_synced_at else None,
        }

    al_user = db.query(AniListUser).filter(AniListUser.user_id == user_id).first()
    if al_user:
        export_payload["connections"]["anilist"] = {
            "username": al_user.anilist_username,
        }

    my_conn = db.query(MyntraConnection).filter(MyntraConnection.user_id == user_id).first()
    if my_conn:
        export_payload["connections"]["myntra"] = {
            "connected_at": my_conn.created_at.isoformat() if my_conn.created_at else None,
        }

    # 3. Plays sample
    plays = (
        db.query(SpotifyPlayEvent)
        .filter(SpotifyPlayEvent.user_id == user_id)
        .order_by(desc(SpotifyPlayEvent.played_at))
        .limit(100)
        .all()
    )
    for p in plays:
        export_payload["recent_plays"].append({
            "track_id": p.track_id,
            "track_name": p.track_name,
            "album": p.album_name,
            "played_at": p.played_at.isoformat() if p.played_at else None,
        })

    # 4. Feedback
    fb = (
        db.query(RecommendationFeedback)
        .filter(RecommendationFeedback.user_id == user_id)
        .limit(100)
        .all()
    )
    for f in fb:
        export_payload["feedback_history"].append({
            "domain": f.domain,
            "item_id": f.item_id,
            "feedback": f.feedback_type,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        })

    return export_payload


@router.delete("/data")
def delete_user_data(
    confirm: str = Query("", description="Must be exactly 'DELETE' to confirm wipe"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Nuclear GDPR wipe: Deletes all user data, connections, tokens, logs, feedback,
    and profile controls across all tables for this user.
    Requires ?confirm=DELETE.
    """
    if confirm != "DELETE":
        raise HTTPException(
            status_code=400,
            detail="Account wipe must be confirmed by passing ?confirm=DELETE",
        )

    # Wipe SpotifyUser (deletes tokens)
    db.query(SpotifyUser).filter(SpotifyUser.user_id == user_id).delete(synchronize_session=False)
    db.query(SpotifyPlayEvent).filter(SpotifyPlayEvent.user_id == user_id).delete(synchronize_session=False)

    # Wipe AniListUser
    db.query(AniListUser).filter(AniListUser.user_id == user_id).delete(synchronize_session=False)
    db.query(UserLike).filter(UserLike.user_id == user_id).delete(synchronize_session=False)

    # Wipe Myntra
    db.query(MyntraConnection).filter(MyntraConnection.user_id == user_id).delete(synchronize_session=False)
    db.query(MyntraProfile).filter(MyntraProfile.user_id == user_id).delete(synchronize_session=False)
    db.query(MyntraEvent).filter(MyntraEvent.user_id == user_id).delete(synchronize_session=False)
    db.query(MyntraFeedback).filter(MyntraFeedback.user_id == user_id).delete(synchronize_session=False)

    # Wipe Feedback
    db.query(RecommendationFeedback).filter(RecommendationFeedback.user_id == user_id).delete(synchronize_session=False)
    db.query(UserSpotFeedback).filter(UserSpotFeedback.user_id == user_id).delete(synchronize_session=False)
    db.query(UserDiningFeedback).filter(UserDiningFeedback.user_id == user_id).delete(synchronize_session=False)

    # Wipe Profile state
    db.query(TasteControls).filter(TasteControls.user_id == user_id).delete(synchronize_session=False)
    db.query(PublicProfile).filter(PublicProfile.user_id == user_id).delete(synchronize_session=False)
    db.query(SyncLog).filter(SyncLog.user_id == user_id).delete(synchronize_session=False)

    db.commit()

    return {
        "ok": True,
        "message": "All data and connections for this user have been permanently wiped.",
    }


@router.post("/playlist")
def create_profile_playlist(
    payload: CreatePlaylistRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Creates a private Spotify playlist with the user's top recommended tracks.
    Never uses Spotify recommendation endpoints. Uses candidate search and top tracks.
    If scope playlist-modify-private is missing or fails, returns status 409 needs_reconnect.
    """
    import requests
    from routers.spotify import get_valid_access_token

    try:
        access_token = get_valid_access_token(user_id, db)
    except Exception:
        raise HTTPException(
            status_code=409,
            detail={"status": "needs_reconnect", "message": "Spotify reconnection required to create playlists"},
        )

    headers = {"Authorization": f"Bearer {access_token}"}

    # 1. Get user Spotify ID
    me_resp = requests.get("https://api.spotify.com/v1/me", headers=headers, timeout=5)
    if me_resp.status_code != 200:
        raise HTTPException(
            status_code=409,
            detail={"status": "needs_reconnect", "message": "Spotify session expired or insufficient permissions"},
        )
    spotify_account_id = me_resp.json().get("id")

    # 2. Get top tracks to include
    term_map = {"short": "short_term", "medium": "medium_term", "long": "long_term"}
    term = term_map.get(payload.range, "medium_term")
    tracks_resp = requests.get(
        f"https://api.spotify.com/v1/me/top/tracks?time_range={term}&limit=20",
        headers=headers,
        timeout=5,
    )
    track_uris = []
    if tracks_resp.status_code == 200:
        items = tracks_resp.json().get("items", [])
        track_uris = [item["uri"] for item in items if "uri" in item]

    # 3. Create private playlist
    create_body = {
        "name": payload.name or "Poly_Taste Curated",
        "description": "Generated by Poly_Taste multi-domain preference engine",
        "public": False,
    }
    create_resp = requests.post(
        f"https://api.spotify.com/v1/users/{spotify_account_id}/playlists",
        headers={**headers, "Content-Type": "application/json"},
        json=create_body,
        timeout=5,
    )

    if create_resp.status_code not in (200, 201):
        raise HTTPException(
            status_code=409,
            detail={
                "status": "needs_reconnect",
                "message": "Spotify scope playlist-modify-private is required. Please reconnect Spotify.",
            },
        )

    playlist_data = create_resp.json()
    playlist_id = playlist_data.get("id")
    playlist_url = playlist_data.get("external_urls", {}).get("spotify", "")

    # 4. Add tracks if any
    if track_uris and playlist_id:
        requests.post(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
            headers={**headers, "Content-Type": "application/json"},
            json={"uris": track_uris[:20]},
            timeout=5,
        )

    return {
        "ok": True,
        "playlist_url": playlist_url,
        "tracks_count": len(track_uris),
        "message": f"Successfully created private playlist '{payload.name}'",
    }




