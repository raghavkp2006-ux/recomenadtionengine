"""Validated API contracts for Myntra page-derived events."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class MyntraEventType(str, Enum):
    PRODUCT_VIEW = "product_view"
    PRODUCT_CLICK = "product_click"
    SEARCH = "search"
    LISTING_VIEW = "listing_view"
    WISHLIST_ADD = "wishlist_add"
    WISHLIST_REMOVE = "wishlist_remove"
    CART_ADD = "cart_add"
    CART_REMOVE = "cart_remove"
    PURCHASE = "purchase"
    ORDER_VIEW = "order_view"
    PRODUCT_DETAIL_VIEW = "product_detail_view"
    FILTER_INTERACTION = "filter_interaction"
    RECOMMENDATION_CLICK = "recommendation_click"
    EXTENSION_SYNC = "extension_sync"
    LONG_PRODUCT_VIEW = "long_product_view"


class MyntraProductPayload(BaseModel):
    platform: Literal["myntra"] = "myntra"
    product_id: Optional[str] = Field(default=None, max_length=255)
    product_url: Optional[HttpUrl] = None
    brand: Optional[str] = Field(default=None, max_length=255)
    title: Optional[str] = Field(default=None, max_length=1000)
    category: Optional[str] = Field(default=None, max_length=255)
    subcategory: Optional[str] = Field(default=None, max_length=255)
    gender: Optional[str] = Field(default=None, max_length=64)
    price: Optional[float] = Field(default=None, ge=0)
    mrp: Optional[float] = Field(default=None, ge=0)
    discount_percent: Optional[float] = Field(default=None, ge=0, le=100)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    rating_count: Optional[int] = Field(default=None, ge=0)
    colour: Optional[str] = Field(default=None, max_length=128)
    sizes: List[str] = Field(default_factory=list, max_length=100)
    fit: Optional[str] = Field(default=None, max_length=128)
    material: Optional[str] = Field(default=None, max_length=255)
    pattern: Optional[str] = Field(default=None, max_length=255)
    occasion: Optional[str] = Field(default=None, max_length=255)
    season: Optional[str] = Field(default=None, max_length=255)
    seller: Optional[str] = Field(default=None, max_length=255)
    image_url: Optional[HttpUrl] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    source: Literal["dom_or_structured_page_data"] = "dom_or_structured_page_data"
    captured_at: Optional[datetime] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class MyntraEventPayload(BaseModel):
    event_id: UUID
    platform: Literal["myntra"] = "myntra"
    event_type: MyntraEventType
    occurred_at: datetime
    page_url: Optional[HttpUrl] = None
    product: Optional[MyntraProductPayload] = None
    search_query: Optional[str] = Field(default=None, max_length=500)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    extension_version: str = Field(..., min_length=1, max_length=64)
    parser_version: Optional[str] = Field(default=None, max_length=64)

    model_config = ConfigDict(extra="forbid")

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class MyntraBatchEventRequest(BaseModel):
    events: List[MyntraEventPayload] = Field(..., min_length=1, max_length=100)

    model_config = ConfigDict(extra="forbid")


class MyntraConnectionPayload(BaseModel):
    enabled: bool
    collect_product_views: bool = True
    collect_search: bool = True
    collect_wishlist: bool = True
    collect_cart: bool = True
    collect_orders: bool = False

    model_config = ConfigDict(extra="forbid")


class MyntraFeedbackPayload(BaseModel):
    product_id: str = Field(min_length=1, max_length=255)
    feedback: Literal["like", "dislike", "not_interested", "clicked", "purchased"]

    model_config = ConfigDict(extra="forbid")
