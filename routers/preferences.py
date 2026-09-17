from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from services.auth import get_current_user_id
from database import get_user_theme, update_user_theme

router = APIRouter(prefix="/preferences", tags=["preferences"])


class ThemeUpdate(BaseModel):
    theme: str = Field(..., pattern="^(dark|light)$")


@router.get("")
def get_preferences(user_id: str = Depends(get_current_user_id)):
    theme = get_user_theme(user_id)
    return {"theme": theme}


@router.put("")
def update_preferences(
    body: ThemeUpdate,
    user_id: str = Depends(get_current_user_id),
):
    updated = update_user_theme(user_id, body.theme)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"theme": updated}
