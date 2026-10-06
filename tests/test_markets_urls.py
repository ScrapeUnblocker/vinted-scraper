from __future__ import annotations

import pytest

from scrapeunblocker_vinted.markets import (
    MARKETS,
    condition_code,
    condition_ids,
    get_market,
    market_from_url,
)
from scrapeunblocker_vinted.urls import (
    absolute_url,
    build_item_url,
    build_member_url,
    build_search_url,
    is_catalog_url,
    item_id,
    member_id,
    sort_param,
    with_page,
)


@pytest.mark.parametrize(
    "value, code",
    [
        ("fr", "fr"),
        ("UK", "uk"),
        ("gb", "uk"),
        ("co.uk", "uk"),
        ("vinted.co.uk", "uk"),
        ("www.vinted.de", "de"),
        ("https://www.vinted.it/catalog?search_text=x", "it"),
        ("com", "us"),
        ("vinted.com", "us"),
        ("cs", "cz"),
    ],
)
def test_get_market_accepts_codes_domains_and_urls(value, code):
    assert get_market(value).code == code


def test_get_market_rejects_unknown():
    with pytest.raises(ValueError, match="unknown Vinted market"):
        get_market("xx")


def test_markets_table_is_consistent():
    assert len(MARKETS) == 23
    uk = MARKETS["uk"]
    assert (uk.domain, uk.country, uk.currency) == ("vinted.co.uk", "GB", "GBP")
    assert MARKETS["pl"].currency == "PLN"
    assert MARKETS["us"].base_url == "https://www.vinted.com"


def test_market_from_url():
    assert market_from_url("https://www.vinted.pl/items/1").code == "pl"
    assert market_from_url("https://example.com/items/1") is None


@pytest.mark.parametrize(
    "label, code",
    [
        ("Very good", "very_good"),
        ("Très bon état", "very_good"),
        ("Neu, mit Etikett", "new_with_tags"),
        ("Neu", "new_without_tags"),
        ("Nuovo senza cartellino", "new_without_tags"),
        ("Satisfactorio", "satisfactory"),
        ("Veelgebruikt", "satisfactory"),
        ("Nowy z metką", "new_with_tags"),
        ("  good ", "good"),
        ("Πολύ καλό", "very_good"),
        ("Something else", None),
        (None, None),
    ],
)
def test_condition_code_maps_localized_labels(label, code):
    assert condition_code(label) == code


def test_condition_ids():
    assert condition_ids("very_good") == [2]
    assert condition_ids("new") == [6, 1]
    assert condition_ids(["good,satisfactory", "good"]) == [3, 4]
    assert condition_ids(["New-With-Tags", "4"]) == [6, 4]
    assert condition_ids(None) == []
    with pytest.raises(ValueError, match="unknown condition"):
        condition_ids("mint")


def test_build_search_url_with_every_filter():
    url = build_search_url(
        "uk",
        "  levis   501 ",
        catalog_ids=[1206],
        brand_ids="10,53",
        size_ids=[208],
        color_ids=1,
        material_ids=["44"],
        conditions=["new", "very_good"],
        price_from=10,
        price_to=59.5,
        sort="newest",
        page=3,
    )
    assert url == (
        "https://www.vinted.co.uk/catalog?search_text=levis%20501&catalog[]=1206"
        "&brand_ids[]=10&brand_ids[]=53&size_ids[]=208&color_ids[]=1&material_ids[]=44"
        "&status_ids[]=6&status_ids[]=1&status_ids[]=2&price_from=10&price_to=59.5"
        "&order=newest_first&page=3"
    )


def test_build_search_url_minimal_and_page_one():
    assert build_search_url("fr", "nike") == "https://www.vinted.fr/catalog?search_text=nike"
    assert build_search_url("fr") == "https://www.vinted.fr/catalog"
    assert build_search_url("de", catalog_ids=5).endswith("/catalog?catalog[]=5")


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"page": 0}, "page"),
        ({"price_from": 50, "price_to": 10}, "price_from"),
        ({"price_from": -1}, "negative"),
        ({"brand_ids": ["nike"]}, "numeric"),
        ({"sort": "cheapest"}, "unknown sort"),
    ],
)
def test_build_search_url_validates(kwargs, message):
    with pytest.raises(ValueError, match=message):
        build_search_url("fr", "x", **kwargs)


def test_sort_param():
    assert sort_param("price_asc") == "price_low_to_high"
    assert sort_param("price-desc") == "price_high_to_low"
    assert sort_param("newest_first") == "newest_first"
    assert sort_param(None) is None


def test_with_page_keeps_browser_filters():
    url = "https://www.vinted.fr/catalog?search_text=nike&brand_ids[]=53&page=4"
    assert with_page(url, 2) == (
        "https://www.vinted.fr/catalog?search_text=nike&brand_ids[]=53&page=2"
    )
    assert with_page(url, 1) == "https://www.vinted.fr/catalog?search_text=nike&brand_ids[]=53"


def test_is_catalog_url():
    assert is_catalog_url("https://www.vinted.fr/catalog?search_text=x")
    assert is_catalog_url("https://www.vinted.co.uk/catalog/1206-outerwear")
    assert not is_catalog_url("https://www.vinted.fr/items/123")
    assert not is_catalog_url("https://example.com/catalog")


def test_item_and_member_ids():
    assert item_id("https://www.vinted.fr/items/1234567890-nike-air-max") == "1234567890"
    assert item_id(42) == "42"
    assert member_id("https://www.vinted.fr/member/12345678-jane") == "12345678"
    with pytest.raises(ValueError):
        item_id("https://www.vinted.fr/member/1")
    with pytest.raises(ValueError):
        member_id("nobody")


def test_item_member_and_absolute_urls():
    assert build_item_url("uk", "/items/5-x") == "https://www.vinted.co.uk/items/5"
    assert build_member_url("de", 7) == "https://www.vinted.de/member/7"
    assert absolute_url("fr", "/items/1-a") == "https://www.vinted.fr/items/1-a"
    assert absolute_url("fr", "https://x.test/a") == "https://x.test/a"
    assert absolute_url("fr", None) is None
