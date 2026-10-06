# Vinted Scraper

[![CI](https://github.com/ScrapeUnblocker/vinted-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/ScrapeUnblocker/vinted-scraper/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Powered by ScrapeUnblocker](https://img.shields.io/badge/powered%20by-ScrapeUnblocker-6f42c1.svg)](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)

**Scrape [Vinted](https://www.vinted.com) listings, item pages and seller profiles into clean
JSON or CSV, on all 23 Vinted country sites.** Search any keyword or category with Vinted's
own filters (brand, size, colour, material, condition, price). Sort by newest or by price,
and collect up to 960 listings per search. Each listing comes with its price, Buyer
Protection fee and total, brand, size and condition. Open any item to get the full
description, colour, material, category, photos and the seller's rating. Pull a seller's
profile and the listings in their wardrobe. Or leave `watch` running and get every new
listing that matches your search the moment it appears.

Powered by [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos):
the `getPageSource` API loads every Vinted page in a real browser and returns the HTML, and
this package turns the data embedded in it into typed records. A seller's wardrobe is
rendered by running **browser steps** (wait for the grid, then scroll) in the same request.
You don't need a Vinted account, session cookies, an access token, proxies, a headless
browser or retry logic of your own.

## Features

- **Search listings.** 96 listings per page and up to 10 pages per search (the most
  Vinted serves). Several queries in one run are merged and de-duplicated.
- **Vinted's own filters.** Category, brand, size, colour and material IDs (copied from any
  Vinted URL), condition by name (`new`, `very_good`, ...), and a price range. Sort by
  relevance, newest, price low-high or price high-low. Or paste a catalogue URL straight
  from your browser with every filter already set.
- **Clean listing records.** Item ID, title, URL, brand, size, condition (as Vinted prints
  it, plus a **normalized condition code** that is the same in every language), price,
  Buyer Protection fee, total price, currency, favourites, promoted flag, seller ID,
  private/Pro seller flag, thumbnail and photos.
- **Full item details.** Description, brand and brand ID, size, condition, colour, material,
  category, catalogue ID, price, favourites, upload age, availability, reserved and
  buy-now flags, every photo, extra attributes, and the seller's name, Pro badge, review
  count, star rating, location (Pro sellers) and last-seen time.
- **Seller profiles and wardrobes.** Name, city, country, star rating, positive/neutral/
  negative review counts, active listings, items sold and bought, followers, last login,
  holiday mode and verified email/Google/Facebook. With `--listings` you also get the
  listings in their wardrobe (20 at first, then about 20 more per scroll, up to about 100).
- **New-listing watcher.** `watch` polls a search sorted by newest and prints each new
  listing once, as JSON Lines. A state file remembers what you have already seen between
  runs, so it works well with cron.
- **Category lookup.** `categories --search jeans` lists the category IDs and full paths
  for any market, in that market's language.
- **23 country sites.** France, Belgium, Luxembourg, the Netherlands, Germany, Austria,
  Italy, Spain, Portugal, the UK, Ireland, the US, Poland, Lithuania, Czechia, Slovakia,
  Hungary, Romania, Sweden, Denmark, Finland, Greece and Croatia. Each request is routed
  through the market's own country.
- **Resilient.** Timeouts, transient API errors and half-loaded pages are retried with
  doubling backoff. Deleted items and unknown members are reported and skipped.
- **JSON, JSON Lines or CSV.** CSV files are UTF-8 with a BOM, so Excel shows accents and
  currency symbols correctly.
- **CLI + Python library.** Fully typed, and tested offline with a mocked client.

## Install

```bash
git clone https://github.com/ScrapeUnblocker/vinted-scraper.git
cd vinted-scraper
pip install .
```

Get an API key at [scrapeunblocker.com](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
and expose it as `SCRAPEUNBLOCKER_KEY` (the official SDK reads it from there):

```bash
export SCRAPEUNBLOCKER_KEY=your_key_here        # Windows PowerShell: $env:SCRAPEUNBLOCKER_KEY="your_key_here"
```

You can also copy `.env.example` to `.env` and load it with your tool of choice.

## CLI usage

```bash
# Search vinted.fr (default market), newest first, two pages
vinted-scraper search "nike air max" --sort newest --pages 2 --pretty

# UK, Levi's 501 in very good or good condition, up to GBP 30, to CSV
vinted-scraper search "levis 501" -m uk --condition very_good,good --price-max 30 -f csv -o levis.csv

# New Nike items (brand 53) from private sellers only, on vinted.de
vinted-scraper search "air force 1" -m de --brand 53 --condition new --seller-type private

# Paste a catalogue URL from your browser (filters included); the market comes from the URL
vinted-scraper search --url "https://www.vinted.it/catalog?search_text=borsa&order=newest_first" --pages 3

# Several queries, merged and de-duplicated
vinted-scraper search "carhartt jacket" "carhartt detroit" -m nl --limit 200 -f jsonl -o carhartt.jsonl

# Full details of items (IDs or URLs)
vinted-scraper item 10258844660 https://www.vinted.co.uk/items/10254485172 --pretty

# A seller (member ID or profile URL), plus the listings in their wardrobe
vinted-scraper seller 12345678 --listings --scrolls 4 -f csv -o wardrobe.csv

# Print new listings as they appear (JSON Lines), remembering what was already seen
vinted-scraper watch "arc'teryx beta" -m uk --price-max 150 --interval 120 --state-file seen_ids.txt

# Category IDs for a market, filtered by name
vinted-scraper categories -m uk --search jeans

# The supported country sites (no API call)
vinted-scraper markets
```

| Command | What it returns |
| --- | --- |
| `search [QUERY ...]` | Listings for each query (96 per page, `--pages` up to 10) |
| `item ITEM ...` | Full details of each item (ID or URL) |
| `seller MEMBER ...` | Seller profiles; `--listings` adds their wardrobe (`--scrolls 0-4`) |
| `watch [QUERY]` | New listings as JSON Lines, one poll every `--interval` seconds |
| `categories` | Category ID, title, full path, URL and parent for a market |
| `markets` | The 23 Vinted sites with their currency and language |

| Option | Meaning |
| --- | --- |
| `-m, --market` | Vinted site: `fr` (default), `uk`, `de`, `it`, `es`, `nl`, `pl`, `us`, ... |
| `--url` | A Vinted catalogue URL copied from the browser (replaces QUERY and filters) |
| `--category`, `--brand`, `--size`, `--color`, `--material` | Vinted filter IDs (repeat or comma-separate) |
| `--condition` | `new`, `new_with_tags`, `new_without_tags`, `very_good`, `good`, `satisfactory` |
| `--price-min`, `--price-max` | Price range in the market's currency |
| `--sort` | `relevance` (default), `newest`, `price_asc`, `price_desc` |
| `-p, --pages`, `-n, --limit` | Pages per query (1-10) and maximum listings per query |
| `--skip-promoted`, `--seller-type private\|business` | Drop promoted listings / keep one seller type |
| `-f, --format json\|jsonl\|csv`, `-o, --output`, `--pretty` | Output format, file and indentation |
| `--proxy-country`, `--retries`, `-q` | Route through another country, retries per page, no progress |

Run `vinted-scraper <command> --help` for every option. `python -m scrapeunblocker_vinted`
works too.

**Finding filter IDs.** Set the filters you want on the Vinted website and look at the URL:
`brand_ids[]=53` is the brand, `size_ids[]=...` the size, `catalog[]=...` the category. Or
skip the IDs and pass the whole URL with `--url`. `categories --search` finds category IDs
by name.

## Library usage

```python
from scrapeunblocker_vinted import VintedScraper, listings_to_csv

vinted = VintedScraper(market="uk")  # reads SCRAPEUNBLOCKER_KEY; or VintedScraper(api_key="...")

# Search with filters
listings = vinted.search(
    "levis 501",
    conditions=["very_good", "good"],
    price_to=30,
    sort="newest",
    pages=3,
    skip_promoted=True,
)
for x in listings[:5]:
    print(x.price, x.currency, x.size, x.condition_code, x.title, x.url)
listings_to_csv(listings, "levis.csv")

# Any market per call, or a URL copied from the browser
de = vinted.search("air force 1", market="de", brand_ids=[53], conditions="new")
it = vinted.search(url="https://www.vinted.it/catalog?search_text=borsa", pages=2)

# Several queries, merged and de-duplicated
jackets = vinted.search_many(["carhartt jacket", "carhartt detroit"], pages=2)

# Full item details
item = vinted.item(listings[0].id)
print(item.description, item.color, item.material, item.category, item.seller_rating)

# A seller and their wardrobe
seller = vinted.seller(item.seller_id, listings=True, scrolls=4)
print(seller.login, seller.rating, seller.sold_count, len(seller.listings))

# Category IDs
for category in vinted.categories(search="jeans"):
    print(category.id, category.path)

# New listings as they appear (runs until interrupted, or max_polls)
for new in vinted.watch("arc'teryx beta", price_to=150, interval=120):
    print("NEW", new.price, new.title, new.url)
```

`search`, `item`, `seller` and `watch` raise `VintedNotFoundError` for deleted items and
unknown members, and `ValueError` for invalid arguments. Pages that come back half-loaded
are retried automatically.

## Example output

One listing from `vinted-scraper search "nike air max" --sort newest --condition new`
(seller ID replaced, photos shortened):

```json
{
  "id": "10258844660",
  "title": "Nike air max plus",
  "url": "https://www.vinted.fr/items/10258844660-nike-air-max-plus",
  "brand": "Nike",
  "size": "39",
  "condition": "Neuf sans étiquette",
  "condition_code": "new_without_tags",
  "price": 75.0,
  "currency": "EUR",
  "service_fee": 4.45,
  "total_price": 79.45,
  "discount_price": null,
  "favourites": 0,
  "promoted": false,
  "seller_id": "123456789",
  "seller_business": false,
  "image": "https://images1.vinted.net/t/.../310x430/....webp",
  "photos": ["https://images1.vinted.net/t/.../f800/....webp"],
  "market": "fr",
  "query": "nike air max",
  "page": 1,
  "position": 1
}
```

The same item from `vinted-scraper item 10258844660` (seller details replaced):

```json
{
  "id": "10258844660",
  "title": "Nike air max plus",
  "url": "https://www.vinted.fr/items/10258844660-nike-air-max-plus",
  "description": "Scarpe nuove mai usate, le metto in vendita perché ho sbagliato a comprarle",
  "brand": "Nike",
  "brand_id": "53",
  "size": "39",
  "condition": "Neuf sans étiquette",
  "condition_code": "new_without_tags",
  "color": "Noir",
  "material": "Plastique",
  "category": "Hommes Baskets",
  "catalog_id": "1242",
  "price": 75.0,
  "currency": "EUR",
  "favourites": 0,
  "uploaded": "Il y a 15 heures",
  "availability": "InStock",
  "reserved": false,
  "can_buy": true,
  "instant_buy": true,
  "photos": ["https://images1.vinted.net/t/.../f800/....webp", "..."],
  "attributes": {},
  "seller_id": "123456789",
  "seller_login": "example_seller",
  "seller_business": false,
  "seller_badges": [],
  "seller_feedback_count": 1,
  "seller_rating": 5.0,
  "seller_location": null,
  "seller_last_seen": "Vu la dernière fois : il y a 15 heures",
  "market": "fr"
}
```

`examples/price_research.py "levis 501" --market uk --pages 1` (asking prices on one search
page; your numbers will differ):

```text
96 listings for 'levis 501' on vinted (uk)

condition          count    median       min       max
new_with_tags         14     23.32     16.60     45.00  GBP
new_without_tags      16     15.00     10.00     35.00  GBP
very_good             49     15.00      8.00     50.00  GBP
good                  14     11.34      5.33     21.34  GBP
satisfactory           3      6.00      4.00      7.00  GBP
```

## Good to know

- **Texts follow the market's language.** Condition labels, categories, colours, upload age
  ("Il y a 15 heures", "17 hours ago") and last-seen texts are what that Vinted site shows.
  Use `condition_code` to compare conditions across markets.
- **960 listings per search.** Vinted serves at most 10 pages of 96. To go further, split a
  search into several narrower ones (price ranges, sizes, categories, conditions) and merge
  them; `search_many` and the shared `seen` set de-duplicate for you.
- **Prices.** `price` is the seller's asking price, `service_fee` Vinted's Buyer Protection
  fee and `total_price` what the buyer pays before shipping. Shipping is not included.
- **Wardrobes** are rendered with browser steps: one wait plus up to four scrolls per
  request, which loads about 100 listings for a large wardrobe.
- **`watch`** spends one API call per poll. The first poll only records what is already
  listed (unless `--emit-existing`), so you only get listings that appear afterwards.
- **Business sellers** carry a `Pro` badge and `seller_business: true`. Their public location
  is included in item details; private sellers' locations are only on their profile.

## Responsible use

This project reads public pages that anyone can open without logging in. Respect Vinted's
terms of service, keep request volumes reasonable, and handle any personal data (such as
seller names and locations) according to the laws that apply to you, for example the GDPR.

## Project layout

```text
src/scrapeunblocker_vinted/
  __init__.py     package exports and version
  scraper.py      VintedScraper: search, watch, items, sellers, categories, retries
  parsing.py      Next.js payload decoding and the page parsers
  markets.py      the 23 country sites and the condition labels/codes
  urls.py         catalogue, item and member URL builders
  models.py       Listing, Item, Seller, Category, SearchPage dataclasses
  export.py       JSON, JSON Lines and CSV writers
  cli.py          the vinted-scraper command
examples/
  search_to_json.py      newest listings for a query, saved as JSON
  price_research.py      median/min/max asking price per condition
  new_listings_alert.py  print new listings under a price limit
  seller_wardrobe.py     a seller's profile and wardrobe to CSV
tests/            offline tests with synthetic Vinted pages and a fake client
```

## Development

```bash
make install   # pip install -e ".[dev]"
make lint      # ruff check .
make format    # ruff format .
make test      # pytest -q (offline, no API credit used)
```

Optionally run `pre-commit install` to lint and format on every commit.

## Links

- [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos): web scraping API with real browsers
- [ScrapeUnblocker documentation](https://docs.scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos): `getPageSource`, browser steps and the SDKs
- [Python SDK on PyPI](https://pypi.org/project/scrapeunblocker/)

## License

[MIT](LICENSE) © ScrapeUnblocker
