"""Price research: what does an item really sell for on Vinted, by condition?

Collects listings for a search, prints the median/min/max asking price per
condition and writes every listing to CSV.

    python examples/price_research.py "levis 501" --market uk --pages 3
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from statistics import median

from scrapeunblocker_vinted import CONDITIONS, VintedScraper, listings_to_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("query", nargs="?", default="levis 501")
    parser.add_argument("--market", default="uk")
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("--output", default="price_research.csv")
    args = parser.parse_args()

    vinted = VintedScraper(market=args.market)
    listings = vinted.search(args.query, pages=args.pages)
    listings_to_csv(listings, args.output)

    prices: dict[str, list[float]] = defaultdict(list)
    for x in listings:
        if x.price is not None:
            prices[x.condition_code or "unknown"].append(x.price)

    currency = listings[0].currency if listings else ""
    print(f"{len(listings)} listings for {args.query!r} on vinted ({args.market})\n")
    print(f"{'condition':<18}{'count':>6}{'median':>10}{'min':>10}{'max':>10}")
    for code in [*CONDITIONS, "unknown"]:
        values = prices.get(code)
        if values:
            print(
                f"{code:<18}{len(values):>6}{median(values):>10.2f}"
                f"{min(values):>10.2f}{max(values):>10.2f}  {currency}"
            )
    print(f"\nall listings written to {args.output}")


if __name__ == "__main__":
    main()
