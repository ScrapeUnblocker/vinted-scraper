"""Search Vinted and save the listings as JSON.

python examples/search_to_json.py "nike air max" --market fr --pages 2
"""

from __future__ import annotations

import argparse
import json

from scrapeunblocker_vinted import VintedScraper


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("query", nargs="?", default="nike air max")
    parser.add_argument("--market", default="fr")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--output", default="listings.json")
    args = parser.parse_args()

    vinted = VintedScraper(market=args.market)  # reads SCRAPEUNBLOCKER_KEY
    listings = vinted.search(args.query, pages=args.pages, sort="newest", skip_promoted=True)

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump([x.to_dict() for x in listings], handle, ensure_ascii=False, indent=2)

    print(f"saved {len(listings)} listings to {args.output}")
    for x in listings[:5]:
        print(f"  {x.price:>8.2f} {x.currency}  {x.condition or '-':<22} {x.title}")


if __name__ == "__main__":
    main()
