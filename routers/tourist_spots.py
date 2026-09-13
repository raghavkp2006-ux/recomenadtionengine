import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db, get_user
from services.auth import get_current_user_id
from services.taste_profile import compute_taste_profile
from services.tourist_spots import get_spots, get_spot_by_id, record_feedback, get_recommendations
from services.spotify_sync import refresh_spotify_token

router = APIRouter(prefix="/tourist-spots", tags=["tourist-spots"])


class TouristSpotResponse(BaseModel):
    place_id: str
    name: str
    category: str
    description: Optional[str] = None
    price_tier: str
    lat: float
    lng: float
    city: str

    model_config = {"from_attributes": True}


class FeedbackRequest(BaseModel):
    rating: int = Field(..., description="Rating must be 1 (like) or -1 (dislike)")
    tag: Optional[str] = None


class FeedbackResponse(BaseModel):
    status: str = "success"
    user_id: str
    place_id: str
    rating: int
    tag: Optional[str] = None


@router.get("", response_model=List[TouristSpotResponse])
def list_tourist_spots(
    category: Optional[str] = Query(default=None, description="Filter by spot category"),
    price_tier: Optional[str] = Query(default=None, description="Filter by price tier (free, paid, premium)"),
    db: Session = Depends(get_db),
):
    """
    List tourist spots, optionally filtered by category and/or price_tier.
    Public browsing endpoint — no authentication required.
    """
    return get_spots(db, category=category, price_tier=price_tier)


@router.get("/recommendations", response_model=List[TouristSpotResponse])
def get_tourist_spot_recommendations(
    limit: int = Query(default=20, ge=1, le=100, description="Max number of recommendations to return"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Get personalized tourist spot recommendations for the authenticated user,
    blending their Spotify music and Anime signals via the tourism crosswalk,
    with adjustments based on user spot feedback.
    Protected endpoint — requires authentication.
    """
    spotify_token: str | None = None
    try:
        user_record = get_user(user_id)
        if user_record:
            if user_record.get("expires_at", 0) > int(time.time()):
                spotify_token = user_record.get("access_token")
            else:
                # Token expired — refresh instead of silently giving up
                spotify_token = refresh_spotify_token(user_record)
    except Exception as e:
        print(f"[tourist_spots] Spotify token resolution failed for user {user_id}: {e}")

    taste_profile = compute_taste_profile(user_id, spotify_token=spotify_token)
    return get_recommendations(db=db, user_id=user_id, taste_profile=taste_profile, limit=limit)


@router.get("/{place_id}", response_model=TouristSpotResponse)
def get_tourist_spot(
    place_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve single tourist spot detail by place_id.
    Public endpoint — no authentication required.
    """
    spot = get_spot_by_id(db, place_id=place_id)
    if not spot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tourist spot '{place_id}' not found",
        )
    return spot


@router.post("/{place_id}/feedback", status_code=status.HTTP_201_CREATED, response_model=FeedbackResponse)
def post_spot_feedback(
    place_id: str,
    req: FeedbackRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Record user feedback (like/dislike) for a tourist spot.
    Protected endpoint — requires authentication.
    """
    if req.rating not in (1, -1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid rating '{req.rating}'. Rating must be 1 or -1.",
        )

    spot = get_spot_by_id(db, place_id=place_id)
    if not spot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tourist spot '{place_id}' not found",
        )

    try:
        feedback = record_feedback(
            db=db,
            user_id=user_id,
            place_id=place_id,
            rating=req.rating,
            tag=req.tag,
        )
        return FeedbackResponse(
            status="success",
            user_id=feedback.user_id,
            place_id=feedback.place_id,
            rating=feedback.rating,
            tag=feedback.tag,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
