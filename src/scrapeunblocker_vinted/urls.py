"""Build Vinted catalogue, item and member URLs."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from .markets import Market, condition_ids, get_market, market_from_url

#: Sort orders, as accepted by ``--sort`` (left) and sent to Vinted (right).
SORTS: dict[str, str] = {
    "relevance": "relevance",
    "newest": "newest_first",
    "price_asc": "price_low_to_high",
    "price_desc": "price_high_to_low",
}

#: Listings Vinted shows per catalogue page.
PER_PAGE = 96

#: Vinted serves at most this many pages (960 listings) for one search.
MAX_PAGES = 10

_ITEM_ID = re.compile(r"/items/(\d+)")
_MEMBER_ID = re.compile(r"/member/(\d+)")


def _ids(values: Iterable[int | str] | int | str | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (int, str)):
        values = [values]
    out: list[str] = []
    for value in values:
        for part in str(value).split(","):
            part = part.strip()
            if not part:
                continue
            if not part.isdigit():
                raise ValueError(f"expected a numeric Vinted ID, got {part!r}")
            if part not in out:
                out.append(part)
    return out


def _price(value: float | None) -> str | None:
    if value is None:
        return None
    if value < 0:
        raise ValueError("prices cannot be negative")
    return f"{value:g}"


def sort_param(sort: str | None) -> str | None:
    """Translate a ``--sort`` name (or a raw Vinted ``order`` value) to Vinted's value."""
    if sort is None:
        return None
    key = sort.strip().lower().replace("-", "_")
    if key in SORTS:
        return SORTS[key]
    if key in SORTS.values():
        return key
    raise ValueError(f"unknown sort {sort!r}; choose one of: {', '.join(SORTS)}")


def build_search_url(
    market: str | Market,
    query: str | None = None,
    *,
    catalog_ids: Iterable[int | str] | int | str | None = None,
    brand_ids: Iterable[int | str] | int | str | None = None,
    size_ids: Iterable[int | str] | int | str | None = None,
    color_ids: Iterable[int | str] | int | str | None = None,
    material_ids: Iterable[int | str] | int | str | None = None,
    conditions: str | list[str] | tuple[str, ...] | None = None,
    price_from: float | None = None,
    price_to: float | None = None,
    sort: str | None = None,
    page: int = 1,
) -> str:
    """Build a Vinted catalogue (search) URL.

    Args:
        market: Market code or domain (``fr``, ``uk``, ``vinted.de`` ...).
        query: Free-text search, e.g. ``"nike air max"``. Optional when you
            filter by category or brand instead.
        catalog_ids, brand_ids, size_ids, color_ids, material_ids: Vinted
            filter IDs, as they appear in a Vinted URL (``catalog[]=1206``,
            ``brand_ids[]=53`` ...). Use ``categories`` to look up category IDs.
        conditions: Condition names (``"new"``, ``"very_good"``, ...) or IDs.
        price_from, price_to: Price range in the market currency.
        sort: ``relevance`` (default), ``newest``, ``price_asc`` or ``price_desc``.
        page: 1-based page number (96 listings per page, at most 10 pages).
    """
    m = get_market(market)
    if page < 1:
        raise ValueError("page must be at least 1")
    if price_from is not None and price_to is not None and price_from > price_to:
        raise ValueError("price_from must not be greater than price_to")
    params: list[tuple[str, str]] = []
    if query and query.strip():
        params.append(("search_text", " ".join(query.split())))
    params += [("catalog[]", i) for i in _ids(catalog_ids)]
    params += [("brand_ids[]", i) for i in _ids(brand_ids)]
    params += [("size_ids[]", i) for i in _ids(size_ids)]
    params += [("color_ids[]", i) for i in _ids(color_ids)]
    params += [("material_ids[]", i) for i in _ids(material_ids)]
    params += [("status_ids[]", str(i)) for i in condition_ids(conditions)]
    low, high = _price(price_from), _price(price_to)
    if low is not None:
        params.append(("price_from", low))
    if high is not None:
        params.append(("price_to", high))
    order = sort_param(sort)
    if order:
        params.append(("order", order))
    if page > 1:
        params.append(("page", str(page)))
    query_string = urlencode(params, quote_via=quote, safe="[]")
    return f"{m.base_url}/catalog" + (f"?{query_string}" if query_string else "")


def is_catalog_url(url: str) -> bool:
    """True for a Vinted catalogue URL (``/catalog`` or ``/catalog/<id>-<slug>``)."""
    if market_from_url(url) is None:
        return False
    path = urlsplit(url if "://" in url else f"https://{url}").path
    return path.rstrip("/") == "/catalog" or path.startswith("/catalog/")


def with_page(url: str, page: int) -> str:
    """Return a catalogue URL (for example one copied from the browser, with
    all its filters) set to ``page``."""
    if page < 1:
        raise ValueError("page must be at least 1")
    parts = urlsplit(url if "://" in url else f"https://{url}")
    params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "page"]
    if page > 1:
        params.append(("page", str(page)))
    query_string = urlencode(params, quote_via=quote, safe="[]")
    return urlunsplit((parts.scheme or "https", parts.netloc, parts.path, query_string, ""))


def item_id(value: str | int) -> str:
    """Extract the numeric item ID from an ID or a Vinted item URL.

    Raises:
        ValueError: No item ID found.
    """
    text = str(value).strip()
    if text.isdigit():
        return text
    match = _ITEM_ID.search(text)
    if match:
        return match.group(1)
    raise ValueError(f"not a Vinted item ID or URL: {value!r}")


def member_id(value: str | int) -> str:
    """Extract the numeric member (seller) ID from an ID or a Vinted member URL.

    Raises:
        ValueError: No member ID found.
    """
    text = str(value).strip()
    if text.isdigit():
        return text
    match = _MEMBER_ID.search(text)
    if match:
        return match.group(1)
    raise ValueError(f"not a Vinted member ID or URL: {value!r}")


def build_item_url(market: str | Market, value: str | int) -> str:
    """Item page URL (``/items/<id>``) on ``market``."""
    return f"{get_market(market).base_url}/items/{item_id(value)}"


def build_member_url(market: str | Market, value: str | int) -> str:
    """Member (seller) profile URL (``/member/<id>``) on ``market``."""
    return f"{get_market(market).base_url}/member/{member_id(value)}"


def absolute_url(market: str | Market, path: str | None) -> str | None:
    """Make a site-relative Vinted path absolute for ``market``."""
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return get_market(market).base_url + (path if path.startswith("/") else f"/{path}")
