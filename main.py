import os
import logging
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Response, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from database import get_dynamodb_resource, init_db
from routers import google_auth, spotify, spotify_import, anime, taste, anilist, connections, tourist_spots, movie, dining, myntra
from services.auth import get_current_user_id, create_session_cookie
from services.spotify_scheduler import start_scheduler, stop_scheduler
from pydantic import BaseModel
from fastapi import HTTPException


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure database schema and tables are created
    print("[main] Running application startup: initializing database schema...")
    tables = init_db()
    print(f"[main] Database schema verified on startup. Available tables: {tables}")
    # Startup: launch background scheduler
    print("[main] Starting Spotify background scheduler...")
    start_scheduler()
    yield
    # Shutdown: stop scheduler gracefully
    print("[main] Running application shutdown: stopping scheduler...")
    stop_scheduler()


app = FastAPI(title="Multi-Module Recommendation App", lifespan=lifespan)
logger = logging.getLogger("myntra")


@app.middleware("http")
async def myntra_request_logging(request: Request, call_next):
    if not request.url.path.startswith("/myntra"):
        return await call_next(request)
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.myntra_request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info("myntra_request request_id=%s route=%s status_code=%s duration_ms=%d", request_id, request.url.path, response.status_code, (time.perf_counter() - started) * 1000)
    return response


def _myntra_error(request: Request, status_code: int, code: str, message: str, details: dict | None = None):
    """Stable extension error contract without changing unrelated API routes."""
    request_id = getattr(request.state, "myntra_request_id", None) or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message, "request_id": request_id, "details": details or {}}}, headers={"X-Request-ID": request_id})


@app.exception_handler(HTTPException)
async def myntra_http_error(request: Request, exc: HTTPException):
    if request.url.path.startswith("/myntra"):
        code = {401: "MYNTRA_NOT_CONNECTED", 409: "MYNTRA_DUPLICATE_EVENT", 429: "MYNTRA_RATE_LIMITED"}.get(exc.status_code, "MYNTRA_REQUEST_FAILED")
        return _myntra_error(request, exc.status_code, code, str(exc.detail))
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def myntra_validation_error(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/myntra"):
        return _myntra_error(request, 422, "MYNTRA_EVENT_VALIDATION_ERROR", "Request validation failed", {"errors": exc.errors()})
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
allowed_origins = (
    [origin.strip().rstrip("/") for origin in allowed_origins_env.split(",") if origin.strip()]
    if allowed_origins_env
    else list({FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"})
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(google_auth.router)
app.include_router(spotify.router)
app.include_router(spotify_import.router)
app.include_router(anime.router)
app.include_router(movie.router)
app.include_router(taste.router)
app.include_router(anilist.router)
app.include_router(connections.router)
app.include_router(tourist_spots.router)
app.include_router(dining.router)
app.include_router(myntra.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Recommendation App API! Visit /docs for Swagger UI"}

@app.get("/auth/me")
def get_me(user_id: str = Depends(get_current_user_id)):
    return {"user_id": user_id}

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/auth/login")
def login(req: LoginRequest, response: Response):
    if req.email and req.password:
        session_cookie = create_session_cookie(user_id=req.email)
        response.set_cookie(
            key="session",
            value=session_cookie,
            httponly=True,
            samesite="none",
            secure=True,
            path="/",
            max_age=30 * 24 * 60 * 60
        )
        return {"message": "Login successful", "user_id": req.email}
    else:
        raise HTTPException(status_code=401, detail="Invalid email or password. Please try again.")

@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(key="session", path="/", httponly=True, samesite="none", secure=True)
    return {"message": "Logged out successfully"}

@app.get("/api/activity")
def get_activity():
    return []

@app.get("/api/recent")
def get_recent():
    return []

@app.get("/api/recommendations")
def get_recommendations(category: str | None = None):
    return []

@app.get("/debug/counts")
def debug_counts():
    from sqlalchemy.orm import Session
    from sqlalchemy import func
    from database import (
        SessionLocal,
        User,
        SpotifyUser,
        SpotifyPlayEvent,
        UserLike,
        AniListUser,
        SpotifyImportProfile,
        TouristSpot,
        UserSpotFeedback,
        DiningSpot,
        UserDiningFeedback,
        Movie,
    )
    db: Session = SessionLocal()
    try:
        per_user_events = (
            db.query(SpotifyPlayEvent.user_id, func.count(SpotifyPlayEvent.id))
            .group_by(SpotifyPlayEvent.user_id)
            .all()
        )
        users = db.query(User).all()
        spotify_users = db.query(SpotifyUser).all()
        anilist_users = db.query(AniListUser).all()
        import_profiles = db.query(SpotifyImportProfile).all()

        return {
            "counts": {
                "users": db.query(User).count(),
                "spotify_users": db.query(SpotifyUser).count(),
                "spotify_play_events": db.query(SpotifyPlayEvent).count(),
                "user_likes": db.query(UserLike).count(),
                "anilist_users": db.query(AniListUser).count(),
                "spotify_import_profiles": db.query(SpotifyImportProfile).count(),
                "tourist_spots": db.query(TouristSpot).count(),
                "user_spot_feedback": db.query(UserSpotFeedback).count(),
                "dining_spots": db.query(DiningSpot).count(),
                "user_dining_feedback": db.query(UserDiningFeedback).count(),
                "movies": db.query(Movie).count(),
            },
            "play_events_per_user": [{"user_id": u, "count": c} for u, c in per_user_events],
            "users": [
                {"id": u.id, "google_sub": u.google_sub, "email": u.email, "name": u.name}
                for u in users
            ],
            "spotify_users": [
                {
                    "user_id": s.user_id,
                    "spotify_account_id": s.spotify_account_id,
                    "spotify_display_name": s.spotify_display_name,
                    "sync_enabled": s.sync_enabled,
                    "last_synced_at": s.last_synced_at.isoformat() if s.last_synced_at else None,
                }
                for s in spotify_users
            ],
            "anilist_users": [
                {
                    "user_id": a.user_id,
                    "anilist_id": a.anilist_id,
                    "anilist_username": a.anilist_username,
                }
                for a in anilist_users
            ],
            "spotify_import_profiles": [
                {
                    "user_id": p.user_id,
                    "total_plays": p.total_plays,
                    "unique_artists": p.unique_artists,
                }
                for p in import_profiles
            ],
        }
    finally:
        db.close()

@app.get("/debug/spotify-recs")
def debug_spotify_recs(request: Request, user_id: str | None = None):
    """
    Debug endpoint to run the exact Spotify recommendation pipeline for user_id
    and return diagnostic output for every step.
    Can be accessed with a session cookie or via ?user_id=<id>
    """
    import json as _json
    from sqlalchemy.orm import Session
    from database import SessionLocal, SpotifyUser, SpotifyPlayEvent
    from services.auth import get_current_user_id
    from services.spotify_sync import get_valid_access_token
    from routers.spotify import (
        get_genre_profile_from_history,
        compute_genre_profile,
        normalize_genres,
        search_candidates,
        score_candidate_tracks,
        fetch_artists_bulk,
    )
    import requests

    resolved_user_id = user_id
    if not resolved_user_id:
        try:
            resolved_user_id = get_current_user_id(request)
        except Exception as e:
            resolved_user_id = None

    if not resolved_user_id:
        return {
            "error": "No user_id provided or authenticated. Pass ?user_id=<id> (e.g. ?user_id=2) or log in with session cookie."
        }

    db: Session = SessionLocal()
    diagnostics: dict = {
        "user_id": str(resolved_user_id),
        "step0_db_check": {},
        "step1_spotify_token": {},
        "step2_top_artists_api": {},
        "step3_history_profile": {},
        "step4_final_genre_profile": {},
        "step5_candidate_search": {},
        "step6_recommendations": {},
    }

    try:
        # Step 0: Check DB rows
        sp_user = db.query(SpotifyUser).filter(SpotifyUser.user_id == str(resolved_user_id)).first()
        play_events_count = db.query(SpotifyPlayEvent).filter(SpotifyPlayEvent.user_id == str(resolved_user_id)).count()
        sample_events = (
            db.query(SpotifyPlayEvent)
            .filter(SpotifyPlayEvent.user_id == str(resolved_user_id))
            .order_by(SpotifyPlayEvent.played_at.desc())
            .limit(3)
            .all()
        )

        diagnostics["step0_db_check"] = {
            "spotify_user_exists": sp_user is not None,
            "spotify_user_info": sp_user.to_dict() if sp_user else None,
            "play_events_count": play_events_count,
            "sample_events": [
                {
                    "id": ev.id,
                    "track_id": ev.track_id,
                    "track_name": ev.track_name,
                    "artist_names": _json.loads(ev.artist_names_json) if ev.artist_names_json else [],
                    "artist_ids": _json.loads(ev.artist_ids_json) if ev.artist_ids_json else [],
                    "played_at": ev.played_at.isoformat() if ev.played_at else None,
                }
                for ev in sample_events
            ],
        }

        # Step 1: Token verification
        token = None
        try:
            token = get_valid_access_token(str(resolved_user_id))
            diagnostics["step1_spotify_token"] = {"valid": True, "token_preview": token[:10] + "..." if token else None}
        except Exception as e:
            diagnostics["step1_spotify_token"] = {"valid": False, "error": str(e)}

        if not token:
            diagnostics["error"] = "Cannot test Spotify API without valid access token"
            return diagnostics

        headers = {"Authorization": f"Bearer {token}"}

        # Step 2: Top artists from Spotify
        artists = []
        try:
            artists_resp = requests.get("https://api.spotify.com/v1/me/top/artists?limit=50", headers=headers, timeout=6)
            diagnostics["step2_top_artists_api"] = {
                "status_code": artists_resp.status_code,
                "items_count": len(artists_resp.json().get("items", [])) if artists_resp.status_code == 200 else 0,
            }
            if artists_resp.status_code == 200:
                artists = artists_resp.json().get("items", [])
        except Exception as e:
            diagnostics["step2_top_artists_api"] = {"error": str(e)}

        # Step 3: History genre profile
        history_profile = {}
        try:
            history_profile = get_genre_profile_from_history(str(resolved_user_id), token)
            diagnostics["step3_history_profile"] = history_profile
        except Exception as e:
            diagnostics["step3_history_profile"] = {"error": str(e)}

        # Step 4: Final profile
        user_profile = {}
        if artists:
            for a in artists:
                a["genres"] = normalize_genres(a.get("genres", []))
            user_profile = compute_genre_profile(artists)

        if not user_profile:
            user_profile = history_profile

        diagnostics["step4_final_genre_profile"] = user_profile

        # Step 5: Candidate search (genres + artist names fallback)
        top_genres = sorted(user_profile, key=user_profile.get, reverse=True)[:5] if user_profile else []
        exclude_ids = set()
        raw_candidates = []
        if top_genres:
            raw_candidates = search_candidates(top_genres, exclude_ids, token)

        # Collect top artist names from DB play events and top/artists
        top_artist_names = []
        for ev in sample_events:
            if ev.artist_names_json:
                try:
                    for name in _json.loads(ev.artist_names_json):
                        if name and name not in top_artist_names:
                            top_artist_names.append(name)
                except Exception:
                    pass
        for a in artists:
            aname = a.get("name")
            if aname and aname not in top_artist_names:
                top_artist_names.append(aname)

        if not raw_candidates and top_artist_names:
            seen_cand_ids = set(exclude_ids)
            for aname in top_artist_names[:8]:
                try:
                    s_resp = requests.get(
                        "https://api.spotify.com/v1/search",
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
                    pass

        diagnostics["step5_candidate_search"] = {
            "top_genres": top_genres,
            "top_artist_names": top_artist_names[:8],
            "raw_candidates_found": len(raw_candidates),
            "sample_candidates": [c.get("name") for c in raw_candidates[:3]],
        }

        # Step 6: Scored recommendations
        track_genres_map: dict = {}
        scored = score_candidate_tracks(raw_candidates, user_profile, track_genres_map)
        if not scored and raw_candidates:
            for idx, cand in enumerate(raw_candidates):
                cand_copy = dict(cand)
                cand_copy["score"] = round(max(0.95 - (idx * 0.03), 0.5), 3)
                cand_copy["matched_genres"] = top_genres[:2] if top_genres else ["music"]
                scored.append(cand_copy)

        diagnostics["step6_recommendations"] = {
            "scored_count": len(scored),
            "sample_recommendations": scored[:3],
        }

        return diagnostics
    finally:
        db.close()

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
