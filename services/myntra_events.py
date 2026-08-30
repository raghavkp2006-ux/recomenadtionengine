"""Persistence and retrieval for validated Myntra page-activity events."""

import json
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from models.myntra import MyntraEvent, MyntraProduct
from schemas.myntra import MyntraEventPayload


class EventOwnershipConflictError(ValueError):
    """Raised when a globally unique event ID belongs to another user."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _as_utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def _upsert_product(db: Session, product: dict[str, Any], occurred_at: datetime) -> None:
    """Upsert only products with a stable page-derived product identifier."""
    product_id = product.get("product_id")
    if not product_id:
        return

    row = db.query(MyntraProduct).filter(MyntraProduct.product_id == product_id).one_or_none()
    values = {
        "product_url": product.get("product_url"),
        "brand": product.get("brand"),
        "title": product.get("title"),
        "category": product.get("category"),
        "subcategory": product.get("subcategory"),
        "gender": product.get("gender"),
        "price": product.get("price"),
        "mrp": product.get("mrp"),
        "discount_percent": product.get("discount_percent"),
        "currency": product.get("currency", "INR"),
        "rating": product.get("rating"),
        "rating_count": product.get("rating_count"),
        "colour": product.get("colour"),
        "sizes_json": _json(product.get("sizes", [])),
        "fit": product.get("fit"),
        "material": product.get("material"),
        "pattern": product.get("pattern"),
        "occasion": product.get("occasion"),
        "season": product.get("season"),
        "seller": product.get("seller"),
        "image_url": product.get("image_url"),
        "attributes_json": _json(product.get("attributes", {})),
        "last_seen_at": occurred_at,
    }
    if row is None:
        db.add(MyntraProduct(product_id=product_id, first_seen_at=occurred_at, **values))
        return

    for key, value in values.items():
        setattr(row, key, value)


def ingest_event(db: Session, user_id: str, payload: MyntraEventPayload) -> tuple[MyntraEvent, bool]:
    """Store an event once. Returns ``(event, inserted)`` for idempotent clients."""
    event_id = str(payload.event_id)
    existing = db.query(MyntraEvent).filter(MyntraEvent.event_id == event_id).one_or_none()
    if existing is not None:
        if existing.user_id != user_id:
            raise EventOwnershipConflictError("event_id is already associated with another user")
        return existing, False

    data = payload.model_dump(mode="json")
    product = data.get("product")
    occurred_at = _as_utc(payload.occurred_at)
    event = MyntraEvent(
        event_id=event_id,
        user_id=user_id,
        event_type=payload.event_type.value,
        occurred_at=occurred_at,
        page_url=data.get("page_url"),
        product_id=product.get("product_id") if product else None,
        search_query=payload.search_query,
        product_json=_json(product) if product else None,
        metadata_json=_json(data.get("metadata", {})),
        extension_version=payload.extension_version,
        parser_version=payload.parser_version,
    )
    db.add(event)
    if product:
        _upsert_product(db, product, occurred_at)
    db.flush()
    return event, True


def serialize_event(event: MyntraEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "occurred_at": event.occurred_at.isoformat(),
        "page_url": event.page_url,
        "product_id": event.product_id,
        "search_query": event.search_query,
        "product": json.loads(event.product_json) if event.product_json else None,
        "metadata": json.loads(event.metadata_json) if event.metadata_json else {},
        "extension_version": event.extension_version,
        "parser_version": event.parser_version,
    }


def get_history(
    db: Session,
    user_id: str,
    *,
    event_type: Optional[str] = None,
    from_at: Optional[datetime] = None,
    to_at: Optional[datetime] = None,
    product_id: Optional[str] = None,
    brand: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[MyntraEvent]]:
    query = db.query(MyntraEvent).filter(MyntraEvent.user_id == user_id)
    if event_type:
        query = query.filter(MyntraEvent.event_type == event_type)
    if from_at:
        query = query.filter(MyntraEvent.occurred_at >= _as_utc(from_at))
    if to_at:
        query = query.filter(MyntraEvent.occurred_at <= _as_utc(to_at))
    if product_id:
        query = query.filter(MyntraEvent.product_id == product_id)
    if brand or category:
        query = query.join(MyntraProduct, MyntraProduct.product_id == MyntraEvent.product_id)
        if brand:
            query = query.filter(MyntraProduct.brand == brand)
        if category:
            query = query.filter(MyntraProduct.category == category)
    return query.count(), query.order_by(MyntraEvent.occurred_at.desc(), MyntraEvent.id.desc()).offset(offset).limit(limit).all()


def get_event_status(db: Session, user_id: str) -> dict[str, Any]:
    latest = (
        db.query(MyntraEvent)
        .filter(MyntraEvent.user_id == user_id)
        .order_by(MyntraEvent.occurred_at.desc())
        .first()
    )
    return {
        "total_events": db.query(MyntraEvent).filter(MyntraEvent.user_id == user_id).count(),
        "last_event_at": latest.occurred_at.isoformat() if latest else None,
        "pending_processing": 0,
    }
