from __future__ import annotations

import pytest
from conftest import (
    NotFound,
    StepFailed,
    TransientError,
    card,
    catalog_page,
    item_page,
    member_page,
    wardrobe_card,
)

from scrapeunblocker_vinted import VintedNotFoundError, VintedParseError, wardrobe_steps

UK = "https://www.vinted.co.uk/catalog?search_text=levis"


def test_search_walks_pages_until_the_last(make_scraper, fake_client):
    fake_client.add(UK, catalog_page([card(1), card(2)], page=1, total_pages=2))
    fake_client.add(UK + "&page=2", catalog_page([card(3)], page=2, total_pages=2))
    pages = []
    listings = make_scraper().search("levis", pages=5, on_page=pages.append)
    assert [x.id for x in listings] == ["1", "2", "3"]
    assert [p.page for p in pages] == [1, 2]
    assert all(x.query == "levis" for x in listings)
    assert [c[0] for c in fake_client.calls] == [UK, UK + "&page=2"]
    assert fake_client.calls[0][1] == {"proxy_country": "GB"}


def test_search_stops_on_an_empty_page(make_scraper, fake_client):
    fake_client.add(UK, catalog_page([card(1)], page=1))
    fake_client.add(UK + "&page=2", catalog_page([], page=None))
    assert len(make_scraper().search("levis", pages=3)) == 1
    assert len(fake_client.calls) == 2


def test_search_never_requests_past_page_ten(make_scraper, fake_client):
    fake_client.default = catalog_page([card(1)], page=1, total_pages=99)
    make_scraper().search("levis", pages=50)
    assert len(fake_client.calls) == 10


def test_search_limit_dedupe_and_client_filters(make_scraper, fake_client):
    fake_client.add(
        UK,
        catalog_page(
            [
                card(1, promoted=True),
                card(2, business=True),
                card(3),
                card(3),
                card(4),
            ],
            total_pages=1,
        ),
    )
    scraper = make_scraper()
    assert [x.id for x in scraper.search("levis", limit=2)] == ["1", "2"]
    assert [x.id for x in scraper.search("levis", skip_promoted=True)] == ["2", "3", "4"]
    assert [x.id for x in scraper.search("levis", seller_type="private")] == ["1", "3", "4"]
    assert [x.id for x in scraper.search("levis", seller_type="business")] == ["2"]
    seen = {"1", "2"}
    assert [x.id for x in scraper.search("levis", seen=seen)] == ["3", "4"]
    assert seen == {"1", "2", "3", "4"}


def test_search_many_dedupes_across_queries(make_scraper, fake_client):
    fake_client.add(UK, catalog_page([card(1), card(2)], total_pages=1))
    fake_client.add(
        "https://www.vinted.co.uk/catalog?search_text=501",
        catalog_page([card(2), card(3)], total_pages=1),
    )
    seen_queries = []
    found = make_scraper().search_many(
        ["levis", "501"], on_query=lambda q, r: seen_queries.append((q, len(r)))
    )
    assert [x.id for x in found] == ["1", "2", "3"]
    assert seen_queries == [("levis", 2), ("501", 1)]


def test_search_with_filters_and_url(make_scraper, fake_client):
    filtered = (
        "https://www.vinted.co.uk/catalog?search_text=levis&brand_ids[]=10"
        "&status_ids[]=2&price_to=30&order=newest_first"
    )
    fake_client.add(filtered, catalog_page([card(1)], total_pages=1))
    scraper = make_scraper()
    scraper.search("levis", brand_ids=10, conditions="very_good", price_to=30, sort="newest")
    browser_url = "https://www.vinted.de/catalog?search_text=samba&brand_ids[]=14"
    fake_client.add(browser_url, catalog_page([card(9, currency="EUR")], total_pages=1))
    listing = scraper.search(url=browser_url)[0]
    assert listing.market == "de" and listing.query == browser_url
    assert fake_client.calls[-1][1] == {"proxy_country": "DE"}


def test_search_validates_arguments(make_scraper):
    scraper = make_scraper()
    with pytest.raises(ValueError):
        scraper.search("x", pages=0)
    with pytest.raises(ValueError):
        scraper.search("x", seller_type="pro")
    with pytest.raises(ValueError, match="catalogue URL"):
        scraper.search(url="https://www.vinted.fr/items/1")
    with pytest.raises(TypeError, match="unknown search filter"):
        scraper.search("x", colour_ids=[1])


def test_transient_errors_are_retried_with_backoff(make_scraper, fake_client):
    fake_client.add(UK, TransientError("busy"), TransientError("busy"), catalog_page([card(1)]))
    retries = []
    scraper = make_scraper(backoff=2, on_retry=lambda a, d, e: retries.append((a, d)))
    assert len(scraper.search("levis")) == 1
    assert retries == [(1, 2.0), (2, 4.0)]
    assert scraper.sleeps == [2.0, 4.0]


def test_half_loaded_pages_are_retried(make_scraper, fake_client):
    fake_client.add(UK, "<html>Just a moment...</html>", catalog_page([card(1)]))
    assert len(make_scraper().search("levis")) == 1


def test_retries_are_bounded(make_scraper, fake_client):
    fake_client.add(UK, "<html>blocked</html>")
    scraper = make_scraper(retries=2, backoff=1, max_backoff=1.5)
    with pytest.raises(VintedParseError):
        scraper.search("levis")
    assert scraper.sleeps == [1.0, 1.5]


def test_non_transient_errors_are_raised_at_once(make_scraper, fake_client):
    fake_client.add(UK, RuntimeError("bad key"))
    with pytest.raises(RuntimeError):
        make_scraper().search("levis")
    assert len(fake_client.calls) == 1


def test_item_details_and_market_from_url(make_scraper, fake_client):
    fake_client.add("https://www.vinted.co.uk/items/555", item_page())
    fake_client.add("https://www.vinted.fr/items/555", item_page(currency="EUR"))
    scraper = make_scraper()
    assert scraper.item("555").currency == "GBP"
    item = scraper.item("https://www.vinted.fr/items/555-levis")
    assert item.market == "fr" and item.currency == "EUR"
    assert fake_client.calls[-1][1] == {"proxy_country": "FR"}


def test_item_not_found(make_scraper, fake_client):
    fake_client.add("https://www.vinted.co.uk/items/1", NotFound("404"))
    with pytest.raises(VintedNotFoundError):
        make_scraper().item(1)
    assert len(fake_client.calls) == 1


def test_items_reports_failures(make_scraper, fake_client):
    fake_client.add("https://www.vinted.co.uk/items/555", item_page())
    fake_client.add("https://www.vinted.co.uk/items/1", NotFound("404"))
    errors = []
    found = make_scraper().items([1, 555], on_error=lambda v, e: errors.append(v))
    assert [i.id for i in found] == ["555"] and errors == [1]


def test_seller_profile_only(make_scraper, fake_client):
    fake_client.add("https://www.vinted.co.uk/member/12345678", member_page())
    seller = make_scraper().seller("12345678")
    assert seller.login == "jane_closet" and seller.listings == []
    assert "steps" not in fake_client.calls[0][1]


def test_seller_with_wardrobe_uses_browser_steps(make_scraper, fake_client):
    page = member_page(cards=[wardrobe_card(1, "Shoes", "Nike", "33", "15,00 €", "16,45 €")])
    fake_client.add("https://www.vinted.fr/member/12345678", page)
    seller = make_scraper().seller(
        "https://www.vinted.fr/member/12345678-x", listings=True, scrolls=2
    )
    assert [x.id for x in seller.listings] == ["1"]
    assert seller.listings[0].seller_id == "12345678"
    options = fake_client.calls[0][1]
    assert options["proxy_country"] == "FR"
    assert options["steps"] == wardrobe_steps(2)


def test_empty_wardrobe_step_failure_still_returns_profile(make_scraper, fake_client):
    fake_client.add("https://www.vinted.co.uk/member/5", StepFailed(member_page(cards=[])))
    seller = make_scraper().seller(5, listings=True)
    assert seller.login == "jane_closet" and seller.listings == []


def test_wardrobe_steps_budget():
    steps = wardrobe_steps(4)
    assert len(steps) == 9 and steps[0]["action"] == "wait_for"
    assert len(wardrobe_steps(0)) == 1
    with pytest.raises(ValueError):
        wardrobe_steps(5)


def test_watch_primes_then_yields_new_listings(make_scraper, fake_client):
    url = "https://www.vinted.co.uk/catalog?search_text=levis&order=newest_first"
    fake_client.add(
        url,
        catalog_page([card(2), card(1)]),
        catalog_page([card(3), card(2), card(9, promoted=True), card(1)]),
        catalog_page([card(4), card(3), card(2)]),
    )
    polls = []
    scraper = make_scraper()
    found = list(
        scraper.watch("levis", interval=30, max_polls=3, on_poll=lambda n, k: polls.append((n, k)))
    )
    assert [x.id for x in found] == ["3", "4"]
    assert polls == [(1, 0), (2, 1), (3, 1)]
    assert scraper.sleeps == [30, 30]


def test_watch_with_known_ids_and_emit_existing(make_scraper, fake_client):
    url = "https://www.vinted.co.uk/catalog?search_text=levis&order=newest_first"
    fake_client.add(url, catalog_page([card(2), card(1)]))
    scraper = make_scraper()
    assert [x.id for x in scraper.watch("levis", max_polls=1, seen={"1"})] == ["2"]
    assert [x.id for x in scraper.watch("levis", max_polls=1, emit_existing=True)] == ["2", "1"]


def test_categories_with_search(make_scraper, fake_client):
    fake_client.add("https://www.vinted.co.uk/catalog", catalog_page([]))
    scraper = make_scraper()
    assert len(scraper.categories()) == 4
    assert [c.id for c in scraper.categories(search="JEANS")] == ["257"]


def test_proxy_country_override(make_scraper, fake_client):
    fake_client.add(UK, catalog_page([card(1)]))
    make_scraper(proxy_country="ie").search("levis")
    assert fake_client.calls[0][1] == {"proxy_country": "IE"}
