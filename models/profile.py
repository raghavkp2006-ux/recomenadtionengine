"""SQLAlchemy models for user profile, sync logs, taste controls, and public sharing."""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from models.base import Base


class SyncLog(Base):
    __tablename__ = "sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    domain = Column(String, nullable=False, index=True)  # spotify | anilist | movies | myntra | places | dining
    status = Column(String, nullable=False)  # ok | error | needs_reconnect | never
    items_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    synced_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "domain": self.domain,
            "status": self.status,
            "items_count": self.items_count,
            "error_message": self.error_message,
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
        }


DEFAULT_DOMAIN_WEIGHTS = {"music": 25, "anime": 25, "movies": 25, "fashion": 25}
DEFAULT_SLIDERS = {"energy": 50, "obscurity": 50, "novelty": 50}
DEFAULT_PINNED = {"artists": [], "genres": []}
DEFAULT_HIDDEN = {"artists": [], "genres": []}


class TasteControls(Base):
    __tablename__ = "taste_controls"

    user_id = Column(String, primary_key=True, index=True)
    domain_weights_json = Column(
        Text,
        nullable=False,
        default=json.dumps(DEFAULT_DOMAIN_WEIGHTS),
    )
    sliders_json = Column(
        Text,
        nullable=False,
        default=json.dumps(DEFAULT_SLIDERS),
    )
    pinned_json = Column(
        Text,
        nullable=False,
        default=json.dumps(DEFAULT_PINNED),
    )
    hidden_json = Column(
        Text,
        nullable=False,
        default=json.dumps(DEFAULT_HIDDEN),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def get_domain_weights(self) -> Dict[str, int]:
        try:
            return json.loads(self.domain_weights_json) if self.domain_weights_json else DEFAULT_DOMAIN_WEIGHTS.copy()
        except Exception:
            return DEFAULT_DOMAIN_WEIGHTS.copy()

    def get_sliders(self) -> Dict[str, int]:
        try:
            return json.loads(self.sliders_json) if self.sliders_json else DEFAULT_SLIDERS.copy()
        except Exception:
            return DEFAULT_SLIDERS.copy()

    def get_pinned(self) -> Dict[str, List[str]]:
        try:
            return json.loads(self.pinned_json) if self.pinned_json else DEFAULT_PINNED.copy()
        except Exception:
            return DEFAULT_PINNED.copy()

    def get_hidden(self) -> Dict[str, List[str]]:
        try:
            return json.loads(self.hidden_json) if self.hidden_json else DEFAULT_HIDDEN.copy()
        except Exception:
            return DEFAULT_HIDDEN.copy()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "domain_weights": self.get_domain_weights(),
            "sliders": self.get_sliders(),
            "pinned": self.get_pinned(),
            "hidden": self.get_hidden(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


DEFAULT_VISIBILITY = {
    "genres": False,
    "top_artists": False,
    "stats": False,
    "connections": False,
    "personality": False,
}


class PublicProfile(Base):
    __tablename__ = "public_profile"

    user_id = Column(String, primary_key=True, index=True)
    slug = Column(String(32), unique=True, nullable=True, index=True)
    is_public = Column(Boolean, nullable=False, default=False)
    visibility_json = Column(
        Text,
        nullable=False,
        default=json.dumps(DEFAULT_VISIBILITY),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def get_visibility(self) -> Dict[str, bool]:
        try:
            return json.loads(self.visibility_json) if self.visibility_json else DEFAULT_VISIBILITY.copy()
        except Exception:
            return DEFAULT_VISIBILITY.copy()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "slug": self.slug,
            "is_public": bool(self.is_public),
            "visibility": self.get_visibility(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
