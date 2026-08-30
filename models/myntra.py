"""Persistent models for the user-authorized Myntra integration."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, UniqueConstraint, func

from models.base import Base


class MyntraEvent(Base):
    __tablename__ = "myntra_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(36), nullable=False, unique=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    page_url = Column(Text, nullable=True)
    product_id = Column(String, nullable=True, index=True)
    search_query = Column(String, nullable=True)
    product_json = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    extension_version = Column(String(64), nullable=False)
    parser_version = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MyntraProduct(Base):
    __tablename__ = "myntra_products"
    __table_args__ = (UniqueConstraint("product_id", name="uq_myntra_product_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, nullable=False, index=True)
    product_url = Column(Text, nullable=True)
    brand = Column(String, nullable=True, index=True)
    title = Column(String, nullable=True)
    category = Column(String, nullable=True, index=True)
    subcategory = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    mrp = Column(Float, nullable=True)
    discount_percent = Column(Float, nullable=True)
    currency = Column(String(3), nullable=False, default="INR")
    rating = Column(Float, nullable=True)
    rating_count = Column(Integer, nullable=True)
    colour = Column(String, nullable=True)
    sizes_json = Column(Text, nullable=True)
    fit = Column(String, nullable=True)
    material = Column(String, nullable=True)
    pattern = Column(String, nullable=True)
    occasion = Column(String, nullable=True)
    season = Column(String, nullable=True)
    seller = Column(String, nullable=True)
    image_url = Column(Text, nullable=True)
    attributes_json = Column(Text, nullable=True)
    first_seen_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MyntraProfile(Base):
    __tablename__ = "myntra_profiles"

    user_id = Column(String, primary_key=True)
    profile_json = Column(Text, nullable=False)
    profile_version = Column(String(32), nullable=False, default="myntra-1")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class MyntraFeedback(Base):
    __tablename__ = "myntra_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    product_id = Column(String, nullable=False, index=True)
    feedback = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now())


class MyntraConnection(Base):
    __tablename__ = "myntra_connections"

    user_id = Column(String, primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    collect_product_views = Column(Boolean, nullable=False, default=True)
    collect_search = Column(Boolean, nullable=False, default=True)
    collect_wishlist = Column(Boolean, nullable=False, default=True)
    collect_cart = Column(Boolean, nullable=False, default=True)
    collect_orders = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
