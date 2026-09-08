import os
import time
from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from services.auth import get_current_user_id
from database import get_user, get_anilist_user, get_db
from models.myntra import MyntraConnection

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("/status")
def connections_status(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    spotify_user = get_user(user_id)
    spotify_connected = spotify_user is not None

    anilist_user = get_anilist_user(user_id)
    anilist_connected = anilist_user is not None

    myntra_row = db.get(MyntraConnection, user_id)
    myntra_connected = bool(myntra_row is not None and myntra_row.enabled)

    return {
        "google": True,
        "spotify": spotify_connected,
        "anilist": anilist_connected,
        "myntra": myntra_connected,
    }
