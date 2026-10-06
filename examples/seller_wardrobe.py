"""Export a Vinted seller's profile and wardrobe to CSV.

python examples/seller_wardrobe.py 12345678 --market fr
"""

from __future__ import annotations

import argparse

from scrapeunblocker_vinted import VintedScraper, listings_to_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("member", help="member ID or profile URL")
    parser.add_argument("--market", default="fr")
    parser.add_argument("--scrolls", type=int, default=3)
    args = parser.parse_args()

    vinted = VintedScraper(market=args.market)
    seller = vinted.seller(args.member, listings=True, scrolls=args.scrolls)

    print(f"{seller.login} - {seller.city or '?'}, {seller.country or '?'}")
    print(f"  rating {seller.rating} from {seller.feedback_count} reviews")
    print(f"  {seller.active_listings} active listings, {seller.sold_count} sold")
    print(f"  last seen {seller.last_seen}")

    output = f"wardrobe_{seller.id}.csv"
    listings_to_csv(seller.listings, output)
    print(f"{len(seller.listings)} listings written to {output}")


if __name__ == "__main__":
    main()
