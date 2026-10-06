"""Typed records returned by the scraper."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Listing:
    """One listing from a search page or a seller's wardrobe."""

    id: str
    title: str | None
    url: str | None
    brand: str | None = None
    size: str | None = None
    condition: str | None = None
    condition_code: str | None = None
    price: float | None = None
    currency: str | None = None
    service_fee: float | None = None
    total_price: float | None = None
    discount_price: float | None = None
    favourites: int | None = None
    promoted: bool | None = None
    seller_id: str | None = None
    seller_business: bool | None = None
    image: str | None = None
    photos: list[str] = field(default_factory=list)
    market: str | None = None
    query: str | None = None
    page: int | None = None
    position: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Item:
    """Full details of one item page."""

    id: str
    title: str | None
    url: str | None
    description: str | None = None
    brand: str | None = None
    brand_id: str | None = None
    size: str | None = None
    condition: str | None = None
    condition_code: str | None = None
    color: str | None = None
    material: str | None = None
    category: str | None = None
    catalog_id: str | None = None
    price: float | None = None
    currency: str | None = None
    favourites: int | None = None
    uploaded: str | None = None
    availability: str | None = None
    reserved: bool | None = None
    can_buy: bool | None = None
    instant_buy: bool | None = None
    photos: list[str] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)
    seller_id: str | None = None
    seller_login: str | None = None
    seller_business: bool | None = None
    seller_badges: list[str] = field(default_factory=list)
    seller_feedback_count: int | None = None
    seller_rating: float | None = None
    seller_location: str | None = None
    seller_last_seen: str | None = None
    market: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Seller:
    """A member (seller) profile, optionally with the listings in their wardrobe."""

    id: str
    login: str | None
    url: str | None
    business: bool | None = None
    city: str | None = None
    country: str | None = None
    country_code: str | None = None
    rating: float | None = None
    feedback_count: int | None = None
    positive_feedback: int | None = None
    neutral_feedback: int | None = None
    negative_feedback: int | None = None
    active_listings: int | None = None
    sold_count: int | None = None
    bought_count: int | None = None
    followers: int | None = None
    following: int | None = None
    last_seen: str | None = None
    on_holiday: bool | None = None
    verified_email: bool | None = None
    verified_google: bool | None = None
    verified_facebook: bool | None = None
    about: str | None = None
    photo: str | None = None
    market: str | None = None
    listings: list[Listing] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Category:
    """One node of a market's category tree."""

    id: str
    title: str
    path: str
    url: str | None
    depth: int
    parent_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchPage:
    """One parsed catalogue page."""

    listings: list[Listing]
    page: int | None = None
    total_pages: int | None = None
    total_entries: int | None = None
    per_page: int | None = None

    @property
    def has_next(self) -> bool:
        if not self.listings or self.page is None or self.total_pages is None:
            return False
        return self.page < self.total_pages
