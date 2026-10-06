from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from database import RecommendationFeedback, SessionLocal
from services.auth import get_current_user_id

router = APIRouter(prefix="/feedback", tags=["recommendation feedback"])


class FeedbackRequest(BaseModel):
    domain: str = Field(pattern="^(movie|music)$")
    item_id: str = Field(min_length=1, max_length=200)
    action: str = Field(pattern="^(shown|like|dislike|skip)$")


@router.post("")
def record_feedback(body: FeedbackRequest, user_id: str = Depends(get_current_user_id)):
    db = SessionLocal()
    try:
        db.add(RecommendationFeedback(user_id=user_id, domain=body.domain, item_id=body.item_id,
                                      action=body.action, created_at=datetime.now(timezone.utc)))
        db.commit()
        return {"ok": True}
    finally:
        db.close()
