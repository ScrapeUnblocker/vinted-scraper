"""Turn Vinted pages (as returned by ``getPageSource``) into typed records.

Vinted is a Next.js app. Its pages stream their data to the browser as a
React Server Components payload pushed through ``self.__next_f.push([1, "..."])``
script calls. :func:`decode_flight` joins those chunks back together and
:func:`iter_values` pulls JSON values out of it by key:

* catalogue pages carry an ``initialCatalogState`` object (the listings,
  pagination, applied filters and the category tree);
* item pages carry the item, its "plugins" (attributes, description, seller
  header ...) and a schema.org ``jsonLd`` product;
* member pages carry the seller's ``user`` object.

A seller's wardrobe is loaded by the browser after the page renders, so it is
read from the rendered HTML (see :func:`parse_wardrobe`).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

from .markets import Market, condition_code, get_market
from .models import Category, Item, Listing, SearchPage, Seller
from .urls import absolute_url, build_item_url, build_member_url


class VintedError(Exception):
    """Base class for errors raised by this package."""


class VintedNotFoundError(VintedError):
    """The item or member does not exist (Vinted answered 404)."""


class VintedParseError(VintedError):
    """The page did not contain the Vinted data we expected (often a half-loaded page)."""


_PUSH = "self.__next_f.push("
_DECODER = json.JSONDecoder()
_UNDEFINED = "$undefined"
_SEPARATOR = " · "  # "33 · Very good"
_CARD_ID = re.compile(r"^product-item-id-(\d+)$")


# --------------------------------------------------------------------------- #
# Low-level helpers
# --------------------------------------------------------------------------- #


def decode_flight(html: str) -> str:
    """Join the ``self.__next_f.push([1, "..."])`` chunks of a Next.js page."""
    chunks: list[str] = []
    start = 0
    while True:
        i = html.find(_PUSH, start)
        if i < 0:
            break
        j = i + len(_PUSH)
        start = j
        try:
            value, end = _DECODER.raw_decode(html, j)
        except ValueError:
            continue
        start = end
        if isinstance(value, list) and len(value) > 1 and value[0] == 1:
            if isinstance(value[1], str):
                chunks.append(value[1])
    return "".join(chunks)


def iter_values(text: str, key: str) -> Iterator[Any]:
    """Yield every JSON value stored under ``"key":`` in ``text``.

    Only structural keys match: inside the payload, quotes that belong to
    string values are escaped, so ``"key":`` cannot match there.
    """
    needle = f'"{key}":'
    start = 0
    while True:
        i = text.find(needle, start)
        if i < 0:
            return
        j = i + len(needle)
        start = j
        while j < len(text) and text[j] in " \t\r\n":
            j += 1
        try:
            value, _ = _DECODER.raw_decode(text, j)
        except ValueError:
            continue
        yield value


def first_value(text: str, key: str, accept: Any = None) -> Any:
    """The first value under ``key`` for which ``accept(value)`` is true."""
    for value in iter_values(text, key):
        if accept is None or accept(value):
            return value
    return None


def clean(value: Any) -> Any:
    """Map the RSC ``"$undefined"`` marker (and blank strings) to ``None``."""
    if value == _UNDEFINED:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _text(value: Any) -> str | None:
    value = clean(value)
    if value is None:
        return None
    return " ".join(str(value).split()) or None


def _int(value: Any) -> int | None:
    value = clean(value)
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    value = clean(value)
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool | None:
    value = clean(value)
    return value if isinstance(value, bool) else None


def _id(value: Any) -> str | None:
    value = clean(value)
    return None if value is None else str(value)


def _money(value: Any) -> tuple[float | None, str | None]:
    """``{"amount": "15.00", "currencyCode": "EUR"}`` -> ``(15.0, "EUR")``."""
    if not isinstance(value, dict):
        return None, None
    currency = clean(value.get("currencyCode") or value.get("currency_code"))
    return _float(value.get("amount")), currency


def _rating(reputation: Any, feedback_count: int | None) -> float | None:
    """Vinted's 0-1 feedback reputation as a 0-5 star rating."""
    value = _float(reputation)
    if value is None or not feedback_count:
        return None
    return round(value * 5, 2)


def parse_price_text(text: str | None) -> float | None:
    """Parse a localized price such as ``"15,00 €"``, ``"£1,234.50"``,
    ``"1 500 Ft"`` or ``"45,00 zł"``."""
    if not text:
        return None
    digits = re.sub(r"[^0-9.,]", "", str(text)).strip(".,")
    if not digits or not any(ch.isdigit() for ch in digits):
        return None
    if "," in digits and "." in digits:
        if digits.rfind(",") > digits.rfind("."):
            digits = digits.replace(".", "").replace(",", ".")
        else:
            digits = digits.replace(",", "")
    elif "," in digits or "." in digits:
        sep = "," if "," in digits else "."
        head, _, tail = digits.rpartition(sep)
        if len(tail) in (1, 2) and digits.count(sep) == 1:
            digits = f"{head}.{tail}"
        else:
            digits = digits.replace(sep, "")
    try:
        return float(digits)
    except ValueError:
        return None


def split_size_condition(line: str | None) -> tuple[str | None, str | None]:
    """``"M · Very good"`` -> ``("M", "Very good")``; ``"Good"`` -> ``(None, "Good")``.

    Every listing has a condition; the size is only shown for sized categories.
    """
    text = _text(line)
    if not text:
        return None, None
    if _SEPARATOR in text:
        size, _, condition = text.rpartition(_SEPARATOR)
        return size.strip() or None, condition.strip() or None
    return None, text


def _brand_from_label(label: str | None, title: str | None, first_line: str | None) -> str | None:
    """The card's first line is the brand, or the title again when there is no brand.

    The accessibility label (``"<title>, Brand: Nike, Condition: ..."``) tells
    the two apart: a brand appears there as a labelled value.
    """
    first = _text(first_line)
    if not first:
        return None
    label = _text(label)
    if not label:
        return None if first == _text(title) else first
    rest = label
    if title and label.startswith(title):
        rest = label[len(title) :]
    if f": {first}," in rest or rest.endswith(f": {first}"):
        return first
    return None


def _catalog_state(flight: str) -> dict[str, Any]:
    state = first_value(
        flight, "initialCatalogState", lambda v: isinstance(v, dict) and "items" in v
    )
    if not isinstance(state, dict):
        raise VintedParseError("no Vinted catalogue data on the page")
    return state


# --------------------------------------------------------------------------- #
# Search (catalogue) pages
# --------------------------------------------------------------------------- #


def listing_from_card(card: dict[str, Any], market: str | Market) -> Listing | None:
    """Build a :class:`Listing` from one ``initialCatalogState.items.items`` entry."""
    m = get_market(market)
    product = card.get("productItem") if isinstance(card, dict) else None
    if not isinstance(product, dict):
        return None
    item_id = _id(product.get("id") or card.get("id"))
    if not item_id:
        return None
    box = product.get("itemBox") if isinstance(product.get("itemBox"), dict) else {}
    title = _text(product.get("title"))
    size, condition = split_size_condition(box.get("secondLine"))
    price, currency = _money(product.get("price"))
    fee, _ = _money(product.get("serviceFee"))
    total, _ = _money(product.get("totalItemPrice"))
    discount, _ = _money(product.get("priceWithDiscount"))
    user = product.get("user") if isinstance(product.get("user"), dict) else {}
    photos = [
        p["url"]
        for p in product.get("photos") or []
        if isinstance(p, dict) and isinstance(p.get("url"), str)
    ]
    return Listing(
        id=item_id,
        title=title,
        url=absolute_url(m, clean(product.get("url"))) or build_item_url(m, item_id),
        brand=_brand_from_label(box.get("accessibilityLabel"), title, box.get("firstLine")),
        size=size,
        condition=condition,
        condition_code=condition_code(condition),
        price=price,
        currency=currency or m.currency,
        service_fee=fee,
        total_price=total,
        discount_price=discount,
        favourites=_int(product.get("favouriteCount")),
        promoted=_bool(product.get("isPromoted")),
        seller_id=_id(user.get("id")),
        seller_business=_bool(user.get("isBusiness")),
        image=clean(product.get("thumbnailUrl")) or (photos[0] if photos else None),
        photos=photos,
        market=m.code,
    )


def parse_search_page(html: str, market: str | Market) -> SearchPage:
    """Parse a catalogue page into listings plus pagination.

    A page past the last one parses to an empty :class:`SearchPage`.

    Raises:
        VintedParseError: The page has no catalogue data (for example a page
            that did not finish loading).
    """
    m = get_market(market)
    flight = decode_flight(html)
    if not flight:
        raise VintedParseError("no Next.js data on the page")
    state = _catalog_state(flight)
    block = state.get("items") if isinstance(state.get("items"), dict) else {}
    cards = clean(block.get("items")) or []
    pagination = clean(block.get("pagination"))
    pagination = pagination if isinstance(pagination, dict) else {}
    listings: list[Listing] = []
    for card in cards if isinstance(cards, list) else []:
        listing = listing_from_card(card, m)
        if listing is not None:
            listings.append(listing)
    page = _int(pagination.get("current_page"))
    for position, listing in enumerate(listings, 1):
        listing.page = page
        listing.position = position
    return SearchPage(
        listings=listings,
        page=page,
        total_pages=_int(pagination.get("total_pages")),
        total_entries=_int(pagination.get("total_entries")),
        per_page=_int(pagination.get("per_page")),
    )


def parse_categories(html: str, market: str | Market) -> list[Category]:
    """Flatten the category tree embedded in any catalogue page."""
    m = get_market(market)
    flight = decode_flight(html)
    state = _catalog_state(flight) if flight else {}
    data = state.get("data") if isinstance(state.get("data"), dict) else {}
    tree = data.get("catalogTree")
    if not isinstance(tree, list) or not tree:
        raise VintedParseError("no category tree on the page")
    out: list[Category] = []

    def walk(nodes: list[Any], trail: list[str], depth: int, parent: str | None) -> None:
        for node in nodes:
            if not isinstance(node, dict) or clean(node.get("id")) is None:
                continue
            title = _text(node.get("title")) or ""
            cid = str(node["id"])
            path = [*trail, title]
            out.append(
                Category(
                    id=cid,
                    title=title,
                    path=" > ".join(path),
                    url=absolute_url(m, clean(node.get("url"))),
                    depth=depth,
                    parent_id=parent,
                )
            )
            children = node.get("catalogs")
            if isinstance(children, list):
                walk(children, path, depth + 1, cid)

    walk(tree, [], 0, None)
    return out


# --------------------------------------------------------------------------- #
# Item pages
# --------------------------------------------------------------------------- #


def _is_plugin_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(p, dict) and "name" in p for p in value)
    )


def parse_item_page(html: str, market: str | Market) -> Item:
    """Parse an item page (``/items/<id>``) into an :class:`Item`.

    Raises:
        VintedParseError: The page has no item data.
    """
    m = get_market(market)
    flight = decode_flight(html)
    if not flight:
        raise VintedParseError("no Next.js data on the page")
    side = first_value(
        flight, "item", lambda v: isinstance(v, dict) and "seller_id" in v and "can_buy" in v
    )
    core = first_value(
        flight,
        "value",
        lambda v: isinstance(v, dict) and "seller_id" in v and isinstance(v.get("photos"), list),
    )
    plugin_list = first_value(flight, "plugins", _is_plugin_list) or []
    ld = first_value(
        flight, "jsonLd", lambda v: isinstance(v, dict) and v.get("@type") == "Product"
    )
    side = side if isinstance(side, dict) else {}
    core = core if isinstance(core, dict) else {}
    ld = ld if isinstance(ld, dict) else {}
    plugins = {p["name"]: p.get("data") or {} for p in plugin_list}
    item_id = _id(side.get("id") or core.get("id"))
    if not item_id or not plugins:
        raise VintedParseError("no item data on the page")

    attributes: dict[str, str] = {}
    brand_id = None
    for attr in plugins.get("attributes", {}).get("attributes") or []:
        if not isinstance(attr, dict) or not isinstance(attr.get("data"), dict):
            continue
        code, value = attr.get("code"), _text(attr["data"].get("value"))
        if code and value:
            attributes[str(code)] = value
        if code == "brand":
            brand_id = _id(attr["data"].get("id"))
    brand_dto = side.get("brand_dto") if isinstance(side.get("brand_dto"), dict) else {}

    header = plugins.get("user_info_header", {})
    info = {
        row.get("key"): _text(row.get("text"))
        for row in header.get("user_info") or []
        if isinstance(row, dict)
    }
    feedback_count = _int(header.get("feedback_count"))

    offers = ld.get("offers") if isinstance(ld.get("offers"), dict) else {}
    price, currency = _money(core.get("price"))
    if price is None:
        price = _float(offers.get("price"))
    currency = (
        currency or clean(side.get("currency")) or clean(offers.get("priceCurrency")) or m.currency
    )

    photos = [
        p["url"]
        for p in core.get("photos") or []
        if isinstance(p, dict) and isinstance(p.get("url"), str)
    ]
    if not photos and isinstance(ld.get("image"), str):
        photos = [ld["image"]]

    condition = attributes.get("status")
    favourite = first_value(flight, "favourite_count", lambda v: isinstance(v, int))
    known = {"brand", "size", "status", "color", "material", "upload_date"}
    return Item(
        id=item_id,
        title=_text(side.get("title") or core.get("title") or ld.get("name")),
        url=clean(offers.get("url")) or build_item_url(m, item_id),
        description=clean(plugins.get("description", {}).get("description"))
        or clean(ld.get("description")),
        brand=attributes.get("brand") or _text(brand_dto.get("title")),
        brand_id=brand_id or _id(brand_dto.get("id")),
        size=attributes.get("size"),
        condition=condition,
        condition_code=condition_code(condition),
        color=attributes.get("color"),
        material=attributes.get("material"),
        category=_text(ld.get("category")),
        catalog_id=_id(side.get("catalog_id")),
        price=price,
        currency=currency,
        favourites=favourite,
        uploaded=attributes.get("upload_date"),
        availability=_text(offers.get("availability")),
        reserved=_bool(side.get("is_reserved")),
        can_buy=_bool(side.get("can_buy")),
        instant_buy=_bool(side.get("instant_buy")),
        photos=photos,
        attributes={k: v for k, v in attributes.items() if k not in known},
        seller_id=_id(side.get("seller_id") or core.get("seller_id") or header.get("seller_id")),
        seller_login=_text(header.get("name")),
        seller_business=_bool(header.get("business")) if header else _bool(side.get("business")),
        seller_badges=[str(b) for b in header.get("badges") or [] if isinstance(b, str)],
        seller_feedback_count=feedback_count,
        seller_rating=_rating(header.get("feedback_reputation"), feedback_count),
        seller_location=info.get("location"),
        seller_last_seen=info.get("last-logged-in"),
        market=m.code,
    )


# --------------------------------------------------------------------------- #
# Member (seller) pages
# --------------------------------------------------------------------------- #


def parse_member_page(html: str, market: str | Market) -> Seller:
    """Parse a member page (``/member/<id>``) into a :class:`Seller` (no listings).

    Raises:
        VintedParseError: The page has no member data.
    """
    m = get_market(market)
    flight = decode_flight(html)
    user = first_value(
        flight,
        "user",
        lambda v: isinstance(v, dict) and "login" in v and "feedback_count" in v,
    )
    if not isinstance(user, dict) or clean(user.get("id")) is None:
        raise VintedParseError("no member data on the page")
    verification = user.get("verification") if isinstance(user.get("verification"), dict) else {}

    def verified(kind: str) -> bool | None:
        entry = verification.get(kind)
        return _bool(entry.get("valid")) if isinstance(entry, dict) else None

    photo = user.get("photo") if isinstance(user.get("photo"), dict) else {}
    feedback_count = _int(user.get("feedback_count"))
    member = str(user["id"])
    return Seller(
        id=member,
        login=_text(user.get("login")),
        url=clean(user.get("profile_url")) or build_member_url(m, member),
        business=_bool(user.get("business")),
        city=_text(user.get("city")),
        country=_text(user.get("country_title")),
        country_code=_text(user.get("country_code") or user.get("country_iso_code")),
        rating=_rating(user.get("feedback_reputation"), feedback_count),
        feedback_count=feedback_count,
        positive_feedback=_int(user.get("positive_feedback_count")),
        neutral_feedback=_int(user.get("neutral_feedback_count")),
        negative_feedback=_int(user.get("negative_feedback_count")),
        active_listings=_int(user.get("item_count")),
        sold_count=_int(user.get("given_item_count")),
        bought_count=_int(user.get("taken_item_count")),
        followers=_int(user.get("followers_count")),
        following=_int(user.get("following_count")),
        last_seen=_text(user.get("last_loged_on_ts")),
        on_holiday=_bool(user.get("is_on_holiday")),
        verified_email=verified("email"),
        verified_google=verified("google"),
        verified_facebook=verified("facebook"),
        about=clean(user.get("about")),
        photo=clean(photo.get("url")),
        market=m.code,
    )


def parse_wardrobe(html: str, market: str | Market, seller_id: str | None = None) -> list[Listing]:
    """Parse the listing cards rendered on a member page (the seller's wardrobe)."""
    from bs4 import BeautifulSoup  # local import keeps the JSON parsers dependency-free

    m = get_market(market)
    soup = BeautifulSoup(html, "html.parser")
    listings: list[Listing] = []
    seen: set[str] = set()
    for card in soup.find_all(attrs={"data-testid": _CARD_ID}):
        match = _CARD_ID.match(card.get("data-testid", ""))
        if not match or match.group(1) in seen:
            continue
        item_id = match.group(1)
        seen.add(item_id)

        def part(suffix: str, root: Any = card, item: str = item_id) -> Any:
            return root.find(attrs={"data-testid": f"product-item-id-{item}--{suffix}"})

        def text_of(node: Any) -> str | None:
            return _text(node.get_text(" ", strip=True)) if node is not None else None

        link = part("overlay-link")
        label = _text(link.get("title")) if link is not None else None
        first_line = text_of(part("description-title"))
        size, condition = split_size_condition(text_of(part("description-subtitle")))
        brand = None
        title = first_line
        if label and first_line and f": {first_line}," in label:
            cut = label.rfind(", ", 0, label.find(f": {first_line},"))
            if cut > 0:
                brand, title = first_line, label[:cut]
        image = part("image--img")
        fav = card.find(attrs={"data-testid": "favourite-count-text"})
        price = parse_price_text(text_of(part("price-text")))
        total = parse_price_text(text_of(card.find(attrs={"data-testid": "total-combined-price"})))
        fee = round(total - price, 2) if price is not None and total is not None else None
        href = link.get("href") if link is not None else None
        listings.append(
            Listing(
                id=item_id,
                title=title,
                url=absolute_url(m, href) or build_item_url(m, item_id),
                brand=brand,
                size=size,
                condition=condition,
                condition_code=condition_code(condition),
                price=price,
                currency=m.currency,
                service_fee=fee,
                total_price=total,
                favourites=_int(text_of(fav)) if fav is not None else 0,
                promoted=part("bump-text") is not None,
                seller_id=seller_id,
                image=image.get("src") if image is not None else None,
                market=m.code,
                position=len(listings) + 1,
            )
        )
    return listings
