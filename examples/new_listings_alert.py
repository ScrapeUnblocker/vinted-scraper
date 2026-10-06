"""Get alerted when a matching listing appears on Vinted.

Polls the newest listings for a search and prints each new one that is under
your price limit. Stop it with Ctrl+C.

    python examples/new_listings_alert.py "carhartt jacket" --market de --max-price 40
"""

from __future__ import annotations

import argparse

from scrapeunblocker_vinted import VintedScraper


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("query", nargs="?", default="carhartt jacket")
    parser.add_argument("--market", default="de")
    parser.add_argument("--max-price", type=float, default=40)
    parser.add_argument("--interval", type=float, default=120, help="seconds between polls")
    parser.add_argument("--polls", type=int, default=None, help="stop after N polls")
    args = parser.parse_args()

    vinted = VintedScraper(market=args.market)
    print(f"watching {args.query!r} on vinted ({args.market}) under {args.max_price} ...")
    try:
        for x in vinted.watch(
            args.query,
            price_to=args.max_price,
            interval=args.interval,
            max_polls=args.polls,
            on_poll=lambda n, new: print(f"  poll {n}: {new} new"),
        ):
            print(
                f"NEW {x.price:.2f} {x.currency} | {x.brand or '-'} | {x.size or '-'} | "
                f"{x.condition or '-'} | {x.title}\n    {x.url}"
            )
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
