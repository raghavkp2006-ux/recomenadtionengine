"""Sync log service for recording and querying domain sync events."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import engine, SessionLocal
from models.profile import SyncLog


def log_sync(
    db: Session,
    user_id: str,
    domain: str,
    status: str,
    items_count: int = 0,
    error: Optional[str] = None,
) -> SyncLog:
    """
    Log a sync event for a user and domain.
    status must be one of: ok | error | needs_reconnect | never
    """
    entry = SyncLog(
        user_id=user_id,
        domain=domain,
        status=status,
        items_count=items_count,
        error_message=str(error) if error else None,
        synced_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_latest_sync(db: Session, user_id: str, domain: str) -> Optional[SyncLog]:
    """Return the most recent sync_log entry for a user and domain."""
    return (
        db.query(SyncLog)
        .filter(SyncLog.user_id == user_id, SyncLog.domain == domain)
        .order_by(desc(SyncLog.synced_at))
        .first()
    )


def get_sync_history(
    db: Session, user_id: str, limit: int = 50, offset: int = 0
) -> List[SyncLog]:
    """Return sync history for a user, newest first."""
    return (
        db.query(SyncLog)
        .filter(SyncLog.user_id == user_id)
        .order_by(desc(SyncLog.synced_at))
        .offset(offset)
        .limit(limit)
        .all()
    )


def init_profile_tables():
    """Ensure sync_log, taste_controls, and public_profile exist in DB."""
    from models.profile import SyncLog, TasteControls, PublicProfile
    from models.base import Base

    Base.metadata.create_all(
        bind=engine,
        tables=[
            SyncLog.__table__,
            TasteControls.__table__,
            PublicProfile.__table__,
        ],
    )
