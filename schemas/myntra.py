"""Validated API contracts for Myntra page-derived events."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


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

    @field_validator("image_url", mode="before")
    @classmethod
    def clean_image_url(cls, value: Any) -> Optional[str]:
        if not value:
            return None
        if isinstance(value, dict):
            value = value.get("url") or value.get("contentUrl")
        if isinstance(value, str):
            value = value.strip()
            if not value or value.startswith("data:"):
                return None
            if value.startswith("//"):
                return "https:" + value
            if not (value.startswith("http://") or value.startswith("https://")):
                return None
            return value
        return None

    @field_validator("product_url", mode="before")
    @classmethod
    def clean_product_url(cls, value: Any) -> Optional[str]:
        if not value:
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            if value.startswith("//"):
                return "https:" + value
            if value.startswith("/"):
                return "https://www.myntra.com" + value
            if not (value.startswith("http://") or value.startswith("https://")):
                return None
            return value
        return None

    @field_validator("colour", "fit", mode="before")
    @classmethod
    def clean_short_str(cls, value: Any) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        value = value.strip()
        return value[:128] if value else None

    @field_validator("gender", mode="before")
    @classmethod
    def clean_gender(cls, value: Any) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        value = value.strip()
        return value[:64] if value else None

    @field_validator("pattern", "material", "occasion", "season", "seller", "brand", "category", "subcategory", mode="before")
    @classmethod
    def clean_medium_str(cls, value: Any) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        value = value.strip()
        return value[:255] if value else None

    @field_validator("title", mode="before")
    @classmethod
    def clean_title(cls, value: Any) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        value = value.strip()
        return value[:1000] if value else None


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

    @field_validator("page_url", mode="before")
    @classmethod
    def clean_page_url(cls, value: Any) -> Optional[str]:
        if not value:
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            if value.startswith("//"):
                return "https:" + value
            if not (value.startswith("http://") or value.startswith("https://")):
                return None
            return value
        return None


class MyntraBatchEventRequest(BaseModel):
    events: List[MyntraEventPayload] = Field(..., min_length=1, max_length=100)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def sanitize_raw_batch(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("events"), list):
            for ev in data["events"]:
                if isinstance(ev, dict) and isinstance(ev.get("product"), dict):
                    prod = ev["product"]
                    r = prod.get("rating")
                    if r is not None:
                        try:
                            rf = float(r)
                            if rf < 0 or rf > 5:
                                prod["rating"] = None
                        except (ValueError, TypeError):
                            prod["rating"] = None
                    d = prod.get("discount_percent")
                    if d is not None:
                        try:
                            df = float(d)
                            if df < 0 or df > 100:
                                prod["discount_percent"] = None
                        except (ValueError, TypeError):
                            prod["discount_percent"] = None
                    string_limits = [
                        ("colour", 128), ("fit", 128), ("gender", 64),
                        ("pattern", 255), ("material", 255), ("occasion", 255),
                        ("season", 255), ("seller", 255), ("brand", 255),
                        ("category", 255), ("subcategory", 255), ("title", 1000),
                    ]
                    for field, max_l in string_limits:
                        val = prod.get(field)
                        if isinstance(val, str) and len(val) > max_l:
                            prod[field] = val[:max_l]
        return data


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


class MyntraVerdictProductData(BaseModel):
    brand: Optional[str] = Field(default=None, max_length=255)
    title: Optional[str] = Field(default=None, max_length=1000)
    category: Optional[str] = Field(default=None, max_length=255)
    subcategory: Optional[str] = Field(default=None, max_length=255)
    gender: Optional[str] = Field(default=None, max_length=64)
    price: Optional[float] = Field(default=None, ge=0)
    colour: Optional[str] = Field(default=None, max_length=128)
    pattern: Optional[str] = Field(default=None, max_length=255)
    fit: Optional[str] = Field(default=None, max_length=128)
    material: Optional[str] = Field(default=None, max_length=255)
    occasion: Optional[str] = Field(default=None, max_length=255)
    image_url: Optional[str] = None
    product_url: Optional[str] = None

    model_config = ConfigDict(extra="ignore")

    @field_validator("colour", "fit", mode="before")
    @classmethod
    def clean_v_short_str(cls, value: Any) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        value = value.strip()
        return value[:128] if value else None

    @field_validator("gender", mode="before")
    @classmethod
    def clean_v_gender(cls, value: Any) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        value = value.strip()
        return value[:64] if value else None

    @field_validator("pattern", "material", "occasion", "brand", "category", "subcategory", mode="before")
    @classmethod
    def clean_v_medium_str(cls, value: Any) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        value = value.strip()
        return value[:255] if value else None

    @field_validator("title", mode="before")
    @classmethod
    def clean_v_title(cls, value: Any) -> Optional[str]:
        if not value or not isinstance(value, str):
            return None
        value = value.strip()
        return value[:1000] if value else None


class MyntraVerdictRequest(BaseModel):
    product_id: Optional[str] = Field(default=None, max_length=255)
    product: Optional[MyntraVerdictProductData] = None

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def validate_has_id_or_product(self) -> MyntraVerdictRequest:
        if not self.product_id and not self.product:
            raise ValueError("Either product_id or product must be provided")
        return self
