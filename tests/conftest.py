"""Shared fixtures: synthetic Vinted pages shaped like the real ones.

Vinted pages stream their data as a React Server Components payload pushed
through ``self.__next_f.push([1, "..."])`` script calls (one ``id:json`` row
per line). The builders below produce the same structure - catalogue state,
item plugins, member ``user`` object and the rendered wardrobe cards - so the
tests run offline and spend no API credit.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

IMG = "https://images1.vinted.net/t/abc/310x430/x.webp"
FULL = "https://images1.vinted.net/t/abc/f800/x.webp"
DOT = " · "


def flight_html(rows: list[Any], chunks: int = 2) -> str:
    """A page whose Next.js payload holds ``rows`` (each one a JSON-able value),
    split across ``chunks`` push calls, prettified like getPageSource output."""
    payload = "".join(
        f"{i + 10:x}:{json.dumps(row, ensure_ascii=False, separators=(',', ':'))}\n"
        for i, row in enumerate(rows)
    )
    size = max(1, len(payload) // chunks + 1)
    parts = [payload[i : i + size] for i in range(0, len(payload), size)]
    scripts = ["  <script>\n   (self.__next_f=self.__next_f||[]).push([0])\n  </script>"]
    for part in parts:
        scripts.append(
            "  <script>\n   self.__next_f.push("
            + json.dumps([1, part], ensure_ascii=False)
            + ")\n  </script>"
        )
    return "<!DOCTYPE html>\n<html>\n <head>\n" + "\n".join(scripts) + "\n </head>\n</html>"


def card(
    item_id: int,
    title: str = "Nike Air Max 90",
    *,
    brand: str | None = "Nike",
    size: str | None = "42",
    condition: str = "Very good",
    price: str = "25.00",
    fee: str = "1.95",
    total: str = "26.95",
    currency: str = "GBP",
    favourites: int = 7,
    promoted: bool = False,
    seller: int = 1001,
    business: bool = False,
    discount: Any = None,
) -> dict[str, Any]:
    """One ``initialCatalogState.items.items`` entry."""
    second = f"{size}{DOT}{condition}" if size else condition
    label = title
    if brand:
        label += f", Brand: {brand}"
    label += f", Condition: {condition}"
    if size:
        label += f", Size: {size}"
    label += f", £{price}, £{total}"
    return {
        "id": item_id,
        "productItem": {
            "id": item_id,
            "title": title,
            "url": f"/items/{item_id}-{title.lower().replace(' ', '-')}",
            "favouriteCount": favourites,
            "priceWithDiscount": discount,
            "price": {"amount": price, "currencyCode": currency},
            "serviceFee": {"amount": fee, "currencyCode": currency},
            "totalItemPrice": {"amount": total, "currencyCode": currency},
            "isPromoted": promoted,
            "isFavourite": False,
            "thumbnailUrl": IMG,
            "thumbnailUrls": [IMG],
            "dominantColor": "#DCD7D1",
            "user": {"id": seller, "photo": None, "thumbnailUrl": None, "isBusiness": business},
            "photos": [{"url": FULL, "thumbnails": [], "isMain": True, "imageNo": 1}],
            "itemBox": {
                "firstLine": brand or title,
                "secondLine": second,
                "exposure": "$undefined",
                "exposures": [],
                "accessibilityLabel": label,
                "badge": "$undefined",
                "itemId": str(item_id),
            },
        },
        "catalogTracking": {"contentSource": "search_promoted_items" if promoted else "search"},
    }


TREE = [
    {
        "id": 5,
        "title": "Men",
        "url": "/catalog/5-men",
        "catalogs": [
            {
                "id": 2050,
                "title": "Clothing",
                "url": "/catalog/2050-clothing",
                "catalogs": [
                    {"id": 257, "title": "Jeans", "url": "/catalog/257-jeans", "catalogs": []}
                ],
            }
        ],
    },
    {"id": 1918, "title": "Home", "url": "/catalog/1918-home", "catalogs": []},
]


def catalog_page(
    cards: list[dict[str, Any]],
    *,
    page: int = 1,
    total_pages: int = 10,
    total_entries: int = 960,
    tree: list[Any] | None = None,
    chunks: int = 2,
) -> str:
    """A catalogue page with ``cards``; ``page=None`` mimics a page past the last."""
    pagination: Any = (
        "$undefined"
        if page is None
        else {
            "current_page": page,
            "per_page": 96,
            "time": 1791275829,
            "total_entries": total_entries,
            "total_pages": total_pages,
        }
    )
    state = {
        "filters": {"query": "x", "page": page or 11, "perPage": 96},
        "dynamicFilters": {"dynamicFilters": []},
        "data": {"catalogTree": tree if tree is not None else TREE},
        "items": {
            "items": cards,
            "pagination": pagination,
            "searchTrackingParams": {},
            "uiState": "SUCCESS",
            "error": "$undefined",
        },
    }
    rows = [
        "$Sreact.fragment",
        ["$", "link", "1", {"rel": "stylesheet", "href": "/x.css"}],
        [
            "$",
            "$L85",
            None,
            {
                "flags": {"a": True},
                "children": [["$", "div", None, {"initialCatalogState": state}]],
            },
        ],
    ]
    return flight_html(rows, chunks=chunks)


def item_page(
    *,
    item_id: str = "555",
    title: str = "Levis 501 W32",
    description: str = "Great jeans.\n\nSmoke free home.",
    brand: str = "Levi's",
    size: str | None = "W32",
    condition: str = "Very good",
    color: str = "Blue",
    material: str | None = "Cotton, Denim",
    extra: dict[str, str] | None = None,
    price: str = "18.99",
    currency: str = "GBP",
    business: bool = True,
    location: str | None = "Leeds, United Kingdom",
    reputation: float = 0.96,
    feedback: int = 4232,
) -> str:
    attributes = [
        {
            "code": "brand",
            "data": {"id": "10", "title": "Brand", "url": "/brand/10-levis", "value": brand},
            "type": "favouritable",
        },
    ]
    if size:
        attributes.append({"code": "size", "data": {"id": 1233, "title": "Size", "value": size}})
    attributes.append(
        {"code": "status", "data": {"id": 50, "title": "Condition", "value": condition}}
    )
    if material:
        attributes.append({"code": "material", "data": {"title": "Material", "value": material}})
    attributes.append({"code": "color", "data": {"title": "Colour", "value": color}})
    for code, value in (extra or {}).items():
        attributes.append({"code": code, "data": {"title": code.title(), "value": value}})
    attributes.append(
        {"code": "upload_date", "data": {"title": "Uploaded", "value": "17 hours ago"}}
    )
    user_info = [{"key": "last-logged-in", "text": "Last seen  29 min ago"}]
    if location:
        user_info.insert(0, {"key": "location", "text": location})
        user_info.insert(1, {"key": "email-link", "text": "******@gmail.com"})
    plugins = [
        {"name": "summary", "type": "summary", "data": {"item_id": item_id, "lines": []}},
        {"name": "attributes", "type": "attributes", "data": {"attributes": attributes}},
        {"name": "description", "type": "description", "data": {"description": description}},
        {
            "name": "user_info_header",
            "type": "user_info_header",
            "data": {
                "badges": ["Pro"] if business else [],
                "business": business,
                "feedback_count": feedback,
                "feedback_reputation": reputation,
                "name": "DenimDealsUK",
                "seller_id": "987654321",
                "user_info": user_info,
            },
        },
        {"name": "shipping", "type": "shipping", "data": {"item_id": item_id}},
    ]
    side = {
        "brand_dto": {"id": "10", "slug": "levis", "title": brand},
        "business": business,
        "can_buy": True,
        "catalog_id": "1819",
        "currency": currency,
        "id": item_id,
        "instant_buy": True,
        "is_reserved": False,
        "photos": "$e0:props:value:photos",
        "plugins": "$33:props:plugins",
        "seller_id": "987654321",
        "title": title,
        "type": "sidebar",
    }
    core = {
        "id": item_id,
        "seller_id": "987654321",
        "price": {"amount": price.rstrip("0").rstrip("."), "currency_code": currency},
        "title": title,
        "photos": [{"id": "p1", "url": FULL + "?1"}, {"id": "p2", "url": FULL + "?2"}],
    }
    ld = {
        "@type": "Product",
        "name": title,
        "description": description,
        "image": FULL,
        "offers": {
            "@type": "Offer",
            "url": f"https://www.vinted.co.uk/items/{item_id}-levis-501-w32",
            "priceCurrency": currency,
            "price": float(price),
            "availability": "InStock",
            "itemCondition": "UsedCondition",
        },
        "category": "Men Straight fit jeans",
    }
    rows = [
        ["$", "$L7", None, {"value": core, "children": "$L8"}],
        ["$", "$L9", None, {"plugins": plugins}],
        ["$", "$La", None, {"data": {"data": {"favourite_count": 5, "item_id": item_id}}}],
        ["$", "$Lb", None, {"children": [{"item": side}]}],
        ["$", "script", None, {"jsonLd": ld}],
    ]
    return flight_html(rows, chunks=3)


def member_user(**overrides: Any) -> dict[str, Any]:
    user = {
        "id": 12345678,
        "login": "jane_closet",
        "profile_url": "https://www.vinted.fr/member/12345678-jane_closet",
        "about": "",
        "verification": {
            "email": {"valid": True, "available": True},
            "facebook": {"valid": False, "verified_at": None},
            "google": {"valid": False, "verified_at": None},
        },
        "business": False,
        "last_loged_on_ts": "2026-10-06T08:32:39+02:00",
        "feedback_count": 24,
        "feedback_reputation": 1,
        "photo": {"id": 1, "url": "https://images1.vinted.net/t/u/f800/p.webp"},
        "item_count": 29,
        "total_items_count": 53,
        "followers_count": 1,
        "following_count": 0,
        "positive_feedback_count": 24,
        "neutral_feedback_count": 0,
        "negative_feedback_count": 0,
        "is_on_holiday": False,
        "city": "Lyon",
        "country_code": "FR",
        "given_item_count": 24,
        "taken_item_count": 1,
        "country_title": "France",
        "country_iso_code": "FR",
    }
    user.update(overrides)
    return user


def wardrobe_card(
    item_id: int,
    title: str,
    brand: str | None,
    subtitle: str,
    price: str,
    total: str,
    *,
    favourites: int | None = 3,
    bumped: bool = False,
) -> str:
    """One rendered wardrobe card (prettified the way getPageSource returns it)."""
    pid = f"product-item-id-{item_id}"
    label = title + (f", brand: {brand}" if brand else "") + f", condition: x, {price}, {total}"
    fav = (
        f'<span data-testid="favourite-count-text">\n {favourites}\n</span>'
        if favourites is not None
        else ""
    )
    bump = f'<div data-testid="{pid}--bump-text">Bumped</div>' if bumped else ""
    return f"""
<div data-testid="grid-item">
 <div data-testid="{pid}">
  <img data-testid="{pid}--image--img" src="{IMG}" alt="{label}"/>
  <a data-testid="{pid}--overlay-link" href="/items/{item_id}" title="{label}"></a>
  <button data-testid="{pid}--favourite">{fav}</button>
  <p data-testid="{pid}--description-title">
   {brand or title}
  </p>
  <p data-testid="{pid}--description-subtitle">
   {subtitle}
  </p>
  <p data-testid="{pid}--price-text">
   {price}
  </p>
  <div data-testid="{pid}--breakdown">
   <span data-testid="total-combined-price">
    {total}
   </span>
  </div>
  {bump}
 </div>
</div>"""


def member_page(user: dict[str, Any] | None = None, cards: list[str] | None = None) -> str:
    """A member page; with ``cards`` it is the steps-rendered page with the wardrobe."""
    rows = [["$", "$L1", None, {"children": [{"user": user or member_user()}]}]]
    html = flight_html(rows)
    if cards is not None:
        html = html.replace("</html>", "<body>" + "".join(cards) + "</body></html>")
    return html


class FakeClient:
    """Stands in for ``scrapeunblocker.Client``: serves queued responses per URL.

    A response is HTML (str) or an exception instance to raise. Every call is
    recorded as ``(url, options)``.
    """

    def __init__(self, responses: dict[str, list[Any]] | None = None, default: Any = None):
        self.responses = {k: list(v) for k, v in (responses or {}).items()}
        self.default = default
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def add(self, url: str, *responses: Any) -> None:
        self.responses.setdefault(url, []).extend(responses)

    def get_page_source(self, url: str, **options: Any) -> str:
        self.calls.append((url, options))
        queue = self.responses.get(url)
        if queue:
            response = queue.pop(0) if len(queue) > 1 else queue[0]
        elif self.default is not None:
            response = self.default
        else:
            raise AssertionError(f"unexpected URL {url}")
        if isinstance(response, BaseException):
            raise response
        return response


class TransientError(Exception):
    """A retryable error for tests."""


class NotFound(Exception):
    """Mimics the SDK's TargetNotFoundError (status_code 404)."""

    status_code = 404


class StepFailed(Exception):
    """Mimics the SDK's StepFailedError (carries the page at failure time)."""

    def __init__(self, html: str):
        super().__init__("step 0 (wait_for) failed")
        self.html = html
        self.step_index = 0


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()


@pytest.fixture
def make_scraper(fake_client: FakeClient):
    from scrapeunblocker_vinted import VintedScraper

    sleeps: list[float] = []

    def build(**options: Any) -> VintedScraper:
        options.setdefault("market", "uk")
        options.setdefault("transient_errors", (TransientError,))
        scraper = VintedScraper(client=fake_client, sleep=sleeps.append, **options)
        scraper.sleeps = sleeps  # type: ignore[attr-defined]
        return scraper

    return build
