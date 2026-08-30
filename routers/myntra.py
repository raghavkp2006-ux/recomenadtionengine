"""Authenticated ingestion and history endpoints for Myntra activity."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
import csv
import io
import json
from sqlalchemy.orm import Session

from database import get_db
from schemas.myntra import MyntraBatchEventRequest, MyntraConnectionPayload, MyntraEventPayload, MyntraFeedbackPayload
from services.auth import get_current_user_id
from services.myntra_events import EventOwnershipConflictError, get_event_status, get_history, ingest_event, serialize_event
from services.myntra_profile import get_profile, rebuild_profile
from services.myntra_recommender import recommendations
from services.myntra_agent import recommend_outfit
from services.myntra_rate_limit import allow as rate_limit_allow
from models.myntra import MyntraConnection, MyntraEvent, MyntraFeedback, MyntraProduct, MyntraProfile


router = APIRouter(prefix="/myntra", tags=["myntra"])


def check_ingestion_rate(user_id: str = Depends(get_current_user_id)) -> str:
    if not rate_limit_allow(user_id):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Myntra event ingestion rate limit exceeded")
    return user_id


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "myntra"}


@router.get("/connection")
def connection(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    row = db.get(MyntraConnection, user_id)
    if row is None:
        return {"enabled": False, "collect_product_views": True, "collect_search": True, "collect_wishlist": True, "collect_cart": True, "collect_orders": False}
    return {name: getattr(row, name) for name in ("enabled", "collect_product_views", "collect_search", "collect_wishlist", "collect_cart", "collect_orders")}


@router.post("/connection")
def update_connection(payload: MyntraConnectionPayload, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    row = db.get(MyntraConnection, user_id)
    if row is None:
        row = MyntraConnection(user_id=user_id)
        db.add(row)
    for name, value in payload.model_dump().items():
        setattr(row, name, value)
    db.commit()
    return connection(db, user_id)


@router.post("/events", status_code=status.HTTP_201_CREATED)
def post_event(
    payload: MyntraEventPayload,
    db: Session = Depends(get_db),
    user_id: str = Depends(check_ingestion_rate),
):
    try:
        event, inserted = ingest_event(db, user_id, payload)
    except EventOwnershipConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    return {"event": serialize_event(event), "inserted": inserted}


@router.post("/events/batch")
def post_event_batch(
    payload: MyntraBatchEventRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(check_ingestion_rate),
):
    accepted = 0
    duplicate_event_ids: list[str] = []
    for event_payload in payload.events:
        try:
            event, inserted = ingest_event(db, user_id, event_payload)
        except EventOwnershipConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        if inserted:
            accepted += 1
        else:
            duplicate_event_ids.append(event.event_id)
    db.commit()
    return {
        "accepted": accepted,
        "duplicates": len(duplicate_event_ids),
        "duplicate_event_ids": duplicate_event_ids,
    }


@router.get("/events/status")
def event_status(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return get_event_status(db, user_id)


@router.get("/history")
def history(
    event_type: Optional[str] = None,
    from_at: Optional[datetime] = Query(default=None, alias="from"),
    to_at: Optional[datetime] = Query(default=None, alias="to"),
    product_id: Optional[str] = None,
    brand: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    total, events = get_history(
        db,
        user_id,
        event_type=event_type,
        from_at=from_at,
        to_at=to_at,
        product_id=product_id,
        brand=brand,
        category=category,
        limit=limit,
        offset=offset,
    )
    return {"total": total, "limit": limit, "offset": offset, "events": [serialize_event(event) for event in events]}


@router.get("/history/products")
def product_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    total, events = get_history(db, user_id, limit=limit, offset=offset)
    products = []
    seen = set()
    for event in events:
        if event.product_id and event.product_id not in seen:
            seen.add(event.product_id)
            products.append(serialize_event(event)["product"])
    return {"total_events": total, "products": products}

@router.get("/profile")
def profile(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return get_profile(db, user_id)

@router.post("/profile/rebuild")
def rebuild(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    result = rebuild_profile(db, user_id); db.commit(); return result

@router.get("/recommendations")
def recommend(limit: int = Query(20, ge=1, le=100), category: Optional[str] = None, min_price: Optional[float] = None, max_price: Optional[float] = None, brand: Optional[str] = None, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return {"recommendations": recommendations(db, user_id, limit, category, min_price, max_price, brand)}

@router.get("/assistant/recommendations")
def assistant_recommendations(limit: int = Query(3, ge=1, le=20), category: Optional[str] = None, max_price: Optional[float] = Query(None, ge=0), brand: Optional[str] = None, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return recommend_outfit(db, user_id, limit=limit, category=category, max_price=max_price, brand=brand)

@router.get("/export.csv")
def export_csv(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    events = db.query(MyntraEvent).filter(MyntraEvent.user_id == user_id).order_by(MyntraEvent.occurred_at, MyntraEvent.event_id).all()
    columns = ["event_id", "user_id", "event_type", "occurred_at", "page_url", "product_id", "brand", "title", "category", "subcategory", "gender", "price", "mrp", "currency", "rating", "rating_count", "colour", "sizes", "fit", "material", "pattern", "occasion", "season", "seller", "image_url", "search_query", "dwell_seconds", "extension_version", "parser_version"]
    output = io.StringIO(newline=""); writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n"); writer.writeheader()
    for event in events:
        product = serialize_event(event)["product"] or {}; row = {name: product.get(name) for name in columns}; row.update({"event_id": event.event_id, "user_id": event.user_id, "event_type": event.event_type, "occurred_at": event.occurred_at.isoformat(), "page_url": event.page_url, "product_id": event.product_id, "search_query": event.search_query, "dwell_seconds": (serialize_event(event)["metadata"]).get("dwell_seconds"), "extension_version": event.extension_version, "parser_version": event.parser_version, "sizes": json.dumps(product.get("sizes", []), ensure_ascii=False)}); writer.writerow(row)
    return Response(output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=myntra-history.csv"})


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
def feedback(payload: MyntraFeedbackPayload, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    db.add(MyntraFeedback(user_id=user_id, product_id=payload.product_id, feedback=payload.feedback))
    db.commit()
    return {"product_id": payload.product_id, "feedback": payload.feedback}


@router.delete("/data", status_code=status.HTTP_204_NO_CONTENT)
def delete_data(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    # Products are shared page-derived catalog records; only the caller's events,
    # profile, feedback, and connection state are removed.
    db.query(MyntraEvent).filter(MyntraEvent.user_id == user_id).delete(synchronize_session=False)
    db.query(MyntraFeedback).filter(MyntraFeedback.user_id == user_id).delete(synchronize_session=False)
    db.query(MyntraProfile).filter(MyntraProfile.user_id == user_id).delete(synchronize_session=False)
    db.query(MyntraConnection).filter(MyntraConnection.user_id == user_id).delete(synchronize_session=False)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
