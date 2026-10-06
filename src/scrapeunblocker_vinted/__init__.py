"""Scrape Vinted with the ScrapeUnblocker API.

Search listings on any of the 23 Vinted country sites, read full item pages
and seller profiles (with their wardrobe), and watch a search for new
listings. Pages are fetched through the ScrapeUnblocker ``getPageSource`` API,
which loads them in a real browser, and parsed into typed records.

    >>> from scrapeunblocker_vinted import VintedScraper
    >>> vinted = VintedScraper(market="uk")          # reads SCRAPEUNBLOCKER_KEY
    >>> listings = vinted.search("levis 501", conditions="very_good", pages=2)
    >>> item = vinted.item(listings[0].id)
"""

from .export import (
    csv_string,
    items_to_csv,
    listings_to_csv,
    sellers_to_csv,
    to_json,
    to_jsonl,
    write_csv,
)
from .markets import CONDITIONS, MARKETS, Market, condition_code, get_market
from .models import Category, Item, Listing, SearchPage, Seller
from .parsing import VintedError, VintedNotFoundError, VintedParseError
from .scraper import VintedScraper, wardrobe_steps
from .urls import SORTS, build_item_url, build_member_url, build_search_url

__version__ = "0.1.0"

__all__ = [
    "CONDITIONS",
    "MARKETS",
    "SORTS",
    "Category",
    "Item",
    "Listing",
    "Market",
    "SearchPage",
    "Seller",
    "VintedError",
    "VintedNotFoundError",
    "VintedParseError",
    "VintedScraper",
    "build_item_url",
    "build_member_url",
    "build_search_url",
    "condition_code",
    "csv_string",
    "get_market",
    "items_to_csv",
    "listings_to_csv",
    "sellers_to_csv",
    "to_json",
    "to_jsonl",
    "wardrobe_steps",
    "write_csv",
    "__version__",
]
