from __future__ import annotations

import json

import pytest
from conftest import (
    DOT,
    FULL,
    IMG,
    card,
    catalog_page,
    flight_html,
    item_page,
    member_page,
    member_user,
    wardrobe_card,
)

from scrapeunblocker_vinted.parsing import (
    VintedParseError,
    decode_flight,
    first_value,
    iter_values,
    parse_categories,
    parse_item_page,
    parse_member_page,
    parse_price_text,
    parse_search_page,
    parse_wardrobe,
    split_size_condition,
)


def test_decode_flight_joins_chunks_and_skips_bootstrap_push():
    html = flight_html([{"a": 1}, ["x", {"b": 'quote " and newline\n'}]], chunks=4)
    flight = decode_flight(html)
    assert flight.count("\n") == 2
    assert first_value(flight, "b") == 'quote " and newline\n'


def test_decode_flight_without_payload():
    assert decode_flight("<html><script>var x = 1;</script></html>") == ""


def test_iter_values_matches_structural_keys_only():
    flight = 'a:{"k":1,"s":"{\\"k\\":2}","n":{"k":[3]}}\n'
    assert list(iter_values(flight, "k")) == [1, [3]]
    spaced = 'a:{"k": 1, "j":' + chr(10) + " [2]}"
    assert list(iter_values(spaced, "j")) == [[2]]


def test_parse_search_page_fields():
    page = parse_search_page(
        catalog_page([card(11, promoted=True, business=True), card(12)], page=2), "uk"
    )
    assert (page.page, page.total_pages, page.total_entries, page.per_page) == (2, 10, 960, 96)
    assert page.has_next
    first = page.listings[0]
    assert first.id == "11"
    assert first.title == "Nike Air Max 90"
    assert first.url == "https://www.vinted.co.uk/items/11-nike-air-max-90"
    assert (first.brand, first.size, first.condition, first.condition_code) == (
        "Nike",
        "42",
        "Very good",
        "very_good",
    )
    assert (first.price, first.service_fee, first.total_price, first.currency) == (
        25.0,
        1.95,
        26.95,
        "GBP",
    )
    assert first.favourites == 7
    assert first.promoted is True
    assert first.seller_id == "1001"
    assert first.seller_business is True
    assert first.image == IMG
    assert first.photos == [FULL]
    assert (first.market, first.page, first.position) == ("uk", 2, 1)
    assert page.listings[1].position == 2


def test_parse_search_page_brandless_and_sizeless_cards():
    cards = [
        card(1, "Grand vase", brand=None, size=None, condition="Good"),
        card(2, "Nike", brand="Nike", size="M"),
        card(3, "Coat", brand="Zara", size="S | 38" + DOT + "40", condition="New with tags"),
    ]
    listings = parse_search_page(catalog_page(cards), "uk").listings
    assert (listings[0].brand, listings[0].size, listings[0].condition) == (None, None, "Good")
    assert listings[1].brand == "Nike"  # title equal to brand is still a brand
    assert listings[2].size == "S | 38" + DOT + "40"
    assert listings[2].condition_code == "new_with_tags"


def test_parse_search_page_discount_and_currency_fallback():
    c = card(5, discount={"amount": "20.00", "currencyCode": "GBP"})
    c["productItem"]["price"] = {"amount": "25.00"}
    listing = parse_search_page(catalog_page([c]), "uk").listings[0]
    assert listing.discount_price == 20.0
    assert listing.currency == "GBP"  # from the market


def test_parse_search_page_past_last_page_is_empty():
    page = parse_search_page(catalog_page([], page=None), "fr")
    assert page.listings == []
    assert page.page is None
    assert not page.has_next


def test_last_page_has_no_next():
    page = parse_search_page(catalog_page([card(1)], page=3, total_pages=3), "fr")
    assert not page.has_next


def test_parse_search_page_without_data_raises():
    with pytest.raises(VintedParseError):
        parse_search_page("<html><body>Just a moment...</body></html>", "fr")
    with pytest.raises(VintedParseError):
        parse_search_page(flight_html([{"other": 1}]), "fr")


@pytest.mark.parametrize(
    "text, value",
    [
        ("15,00 €", 15.0),
        ("£18.99", 18.99),
        ("£1,234.50", 1234.5),
        ("1.234,50 €", 1234.5),
        ("1 500 Ft", 1500.0),
        ("12.000 Ft", 12000.0),
        ("45,00 zł", 45.0),
        ("350 Kč", 350.0),
        ("$7.5", 7.5),
        ("free", None),
        (None, None),
    ],
)
def test_parse_price_text(text, value):
    assert parse_price_text(text) == value


def test_split_size_condition():
    assert split_size_condition("M" + DOT + "Very good") == ("M", "Very good")
    assert split_size_condition("Good") == (None, "Good")
    assert split_size_condition("  W32  " + DOT + " New with tags ") == ("W32", "New with tags")
    assert split_size_condition(None) == (None, None)


def test_parse_item_page():
    item = parse_item_page(item_page(extra={"isbn": "978-3"}), "uk")
    assert item.id == "555"
    assert item.title == "Levis 501 W32"
    assert item.url == "https://www.vinted.co.uk/items/555-levis-501-w32"
    assert item.description == "Great jeans.\n\nSmoke free home."
    assert (item.brand, item.brand_id, item.size) == ("Levi's", "10", "W32")
    assert (item.condition, item.condition_code) == ("Very good", "very_good")
    assert (item.color, item.material) == ("Blue", "Cotton, Denim")
    assert item.category == "Men Straight fit jeans"
    assert item.catalog_id == "1819"
    assert (item.price, item.currency) == (18.99, "GBP")
    assert item.favourites == 5
    assert item.uploaded == "17 hours ago"
    assert item.availability == "InStock"
    assert (item.reserved, item.can_buy, item.instant_buy) == (False, True, True)
    assert item.photos == [FULL + "?1", FULL + "?2"]
    assert item.attributes == {"isbn": "978-3"}
    assert item.seller_id == "987654321"
    assert item.seller_login == "DenimDealsUK"
    assert item.seller_business is True
    assert item.seller_badges == ["Pro"]
    assert item.seller_feedback_count == 4232
    assert item.seller_rating == 4.8
    assert item.seller_location == "Leeds, United Kingdom"
    assert item.seller_last_seen == "Last seen 29 min ago"


def test_parse_item_page_private_seller_without_size():
    item = parse_item_page(item_page(size=None, material=None, business=False, location=None), "fr")
    assert item.size is None and item.material is None
    assert item.seller_business is False and item.seller_badges == []
    assert item.seller_location is None


def test_parse_item_page_without_data_raises():
    with pytest.raises(VintedParseError):
        parse_item_page(flight_html([{"nothing": True}]), "fr")


def test_parse_member_page():
    seller = parse_member_page(member_page(), "fr")
    assert seller.id == "12345678"
    assert seller.login == "jane_closet"
    assert seller.url == "https://www.vinted.fr/member/12345678-jane_closet"
    assert (seller.city, seller.country, seller.country_code) == ("Lyon", "France", "FR")
    assert seller.rating == 5.0
    assert (seller.feedback_count, seller.positive_feedback, seller.negative_feedback) == (
        24,
        24,
        0,
    )
    assert (seller.active_listings, seller.sold_count, seller.bought_count) == (29, 24, 1)
    assert (seller.followers, seller.following) == (1, 0)
    assert seller.last_seen == "2026-10-06T08:32:39+02:00"
    assert seller.verified_email is True and seller.verified_google is False
    assert seller.about is None
    assert seller.photo.endswith("p.webp")
    assert seller.listings == []


def test_member_without_feedback_has_no_rating():
    seller = parse_member_page(
        member_page(member_user(feedback_count=0, feedback_reputation=0)), "fr"
    )
    assert seller.rating is None


def test_parse_member_page_without_data_raises():
    with pytest.raises(VintedParseError):
        parse_member_page(flight_html([{"user": {"id": 1}}]), "fr")


def test_parse_wardrobe_cards():
    html = member_page(
        cards=[
            wardrobe_card(
                1, "Nike Air Max Kids", "Nike", "33" + DOT + "Very good", "15,00 €", "16,45 €"
            ),
            wardrobe_card(
                2, "Vase", None, "Good", "3,00 €", "3,85 €", favourites=None, bumped=True
            ),
            wardrobe_card(1, "dupe", "Nike", "Good", "1 €", "2 €"),
        ]
    )
    listings = parse_wardrobe(html, "fr", seller_id="77")
    assert [x.id for x in listings] == ["1", "2"]
    a, b = listings
    assert (a.title, a.brand, a.size, a.condition_code) == (
        "Nike Air Max Kids",
        "Nike",
        "33",
        "very_good",
    )
    assert (a.price, a.total_price, a.service_fee, a.currency) == (15.0, 16.45, 1.45, "EUR")
    assert (a.favourites, a.promoted, a.seller_id) == (3, False, "77")
    assert a.url == "https://www.vinted.fr/items/1"
    assert a.image == IMG
    assert (b.title, b.brand, b.size, b.condition) == ("Vase", None, None, "Good")
    assert (b.favourites, b.promoted, b.position) == (0, True, 2)


def test_parse_categories():
    cats = parse_categories(catalog_page([]), "uk")
    assert [c.id for c in cats] == ["5", "2050", "257", "1918"]
    jeans = cats[2]
    assert jeans.path == "Men > Clothing > Jeans"
    assert (jeans.depth, jeans.parent_id) == (2, "2050")
    assert jeans.url == "https://www.vinted.co.uk/catalog/257-jeans"
    assert json.loads(json.dumps(jeans.to_dict()))["title"] == "Jeans"


def test_parse_categories_without_tree_raises():
    with pytest.raises(VintedParseError):
        parse_categories(catalog_page([], tree=[]), "uk")
