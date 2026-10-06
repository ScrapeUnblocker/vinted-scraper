"""Command-line interface: ``vinted-scraper <command> ...``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from . import __version__
from .export import (
    items_to_csv,
    listings_to_csv,
    sellers_to_csv,
    to_dict,
    to_json,
    to_jsonl,
    write_csv,
)
from .markets import CONDITIONS, DEFAULT_MARKET, MARKETS
from .scraper import MAX_SCROLLS, SELLER_TYPES, VintedScraper
from .urls import MAX_PAGES, SORTS

FORMATS = ("json", "jsonl", "csv")


def _stdout() -> TextIO:
    """stdout that always accepts UTF-8 (Windows consoles default to a legacy codepage)."""
    stream = sys.stdout
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # pragma: no cover - exotic streams
            pass
    return stream


def _log(args: argparse.Namespace, message: str) -> None:
    if not getattr(args, "quiet", False):
        print(message, file=sys.stderr, flush=True)


def _add_common(parser: argparse.ArgumentParser, *, output: bool = True) -> None:
    parser.add_argument(
        "-m",
        "--market",
        default=None,
        help=f"Vinted site: {', '.join(MARKETS)} (default: {DEFAULT_MARKET}, or the URL's site)",
    )
    if output:
        parser.add_argument("-f", "--format", choices=FORMATS, default="json")
        parser.add_argument("-o", "--output", help="Write to this file instead of stdout")
        parser.add_argument("--pretty", action="store_true", help="Indent JSON output")
    parser.add_argument(
        "--proxy-country", help="Route requests through this country (default: the market's)"
    )
    parser.add_argument("--retries", type=int, default=3, help="Retries per page (default 3)")
    parser.add_argument("-q", "--quiet", action="store_true", help="No progress on stderr")


def _add_filters(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("search filters")
    group.add_argument(
        "--url", help="A Vinted catalogue URL copied from the browser (filters included)"
    )
    group.add_argument(
        "--category", action="append", metavar="ID", help="Category ID (see `categories`)"
    )
    group.add_argument("--brand", action="append", metavar="ID", help="Brand ID, e.g. 53 (Nike)")
    group.add_argument("--size", action="append", metavar="ID", help="Size ID")
    group.add_argument("--color", action="append", metavar="ID", help="Colour ID")
    group.add_argument("--material", action="append", metavar="ID", help="Material ID")
    group.add_argument(
        "--condition",
        action="append",
        metavar="NAME",
        help=f"Condition: new, {', '.join(CONDITIONS)} (comma-separated or repeated)",
    )
    group.add_argument("--price-min", type=float, metavar="AMOUNT", help="Minimum price")
    group.add_argument("--price-max", type=float, metavar="AMOUNT", help="Maximum price")
    group.add_argument("--seller-type", choices=SELLER_TYPES, help="Only private or Pro sellers")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vinted-scraper",
        description="Scrape Vinted listings, items and sellers via the ScrapeUnblocker API.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search listings (96 per page, up to 10 pages)")
    search.add_argument("queries", nargs="*", metavar="QUERY", help="Search text(s)")
    _add_filters(search)
    search.add_argument("--sort", choices=list(SORTS), help="Sort order (default: relevance)")
    search.add_argument(
        "-p", "--pages", type=int, default=1, help=f"Pages per query (1-{MAX_PAGES}, default 1)"
    )
    search.add_argument("-n", "--limit", type=int, help="Maximum listings per query")
    search.add_argument(
        "--skip-promoted", action="store_true", help="Drop promoted (bumped) listings"
    )
    _add_common(search)

    item = sub.add_parser("item", help="Full details of one or more items")
    item.add_argument("items", nargs="+", metavar="ITEM", help="Item ID or URL")
    _add_common(item)

    seller = sub.add_parser("seller", help="Seller profiles, optionally with their wardrobe")
    seller.add_argument("sellers", nargs="+", metavar="MEMBER", help="Member ID or profile URL")
    seller.add_argument(
        "--listings", action="store_true", help="Include the listings in the seller's wardrobe"
    )
    seller.add_argument(
        "--scrolls",
        type=int,
        default=3,
        help=f"Wardrobe scrolls, 0-{MAX_SCROLLS} (each loads more listings, default 3)",
    )
    _add_common(seller)

    watch = sub.add_parser("watch", help="Print new listings as they appear (JSON Lines)")
    watch.add_argument("query", nargs="?", help="Search text")
    _add_filters(watch)
    watch.add_argument(
        "-i", "--interval", type=float, default=60.0, help="Seconds between polls (default 60)"
    )
    watch.add_argument("--max-polls", type=int, help="Stop after this many polls")
    watch.add_argument(
        "--emit-existing", action="store_true", help="Also print what is listed right now"
    )
    watch.add_argument("--state-file", help="Remember seen listing IDs here between runs")
    watch.add_argument("-o", "--output", help="Append JSON Lines to this file")
    _add_common(watch, output=False)

    categories = sub.add_parser("categories", help="A market's category IDs")
    categories.add_argument("--search", help="Keep categories whose path contains this text")
    _add_common(categories)

    sub.add_parser("markets", help="List the supported Vinted sites (no API call)")
    return parser


def _filters(args: argparse.Namespace) -> dict[str, Any]:
    filters: dict[str, Any] = {
        "catalog_ids": args.category,
        "brand_ids": args.brand,
        "size_ids": args.size,
        "color_ids": args.color,
        "material_ids": args.material,
        "conditions": args.condition,
        "price_from": args.price_min,
        "price_to": args.price_max,
    }
    if getattr(args, "sort", None):
        filters["sort"] = args.sort
    return {k: v for k, v in filters.items() if v not in (None, [])}


def _scraper(args: argparse.Namespace) -> VintedScraper:
    def on_retry(attempt: int, delay: float, error: BaseException) -> None:
        _log(args, f"  retry {attempt} in {delay:.0f}s ({type(error).__name__})")

    return VintedScraper(
        market=args.market or DEFAULT_MARKET,
        proxy_country=args.proxy_country,
        retries=args.retries,
        on_retry=on_retry,
    )


def _emit(args: argparse.Namespace, records: list[Any], csv_writer: Any = write_csv) -> None:
    if args.format == "csv":
        if args.output:
            csv_writer(records, args.output)
        else:
            csv_writer(records, _stdout())
    else:
        text = to_jsonl(records) if args.format == "jsonl" else to_json(records, pretty=args.pretty)
        if args.output:
            Path(args.output).write_text(text if text.endswith("\n") else text + "\n", "utf-8")
        else:
            out = _stdout()
            out.write(text if text.endswith("\n") else text + "\n")
            out.flush()
    if args.output:
        _log(args, f"wrote {len(records)} record(s) to {args.output}")


def cmd_search(args: argparse.Namespace) -> int:
    if not args.queries and not args.url and not _filters(args):
        raise SystemExit("error: give a search text, --url or at least one filter")
    if args.url and args.queries:
        raise SystemExit("error: use either QUERY or --url, not both")
    scraper = _scraper(args)
    filters = _filters(args)
    seen: set[str] = set()
    found = []
    for query in args.queries or [None]:
        label = query or args.url or "filters"

        def on_page(page: Any, label: str = label) -> None:
            _log(
                args,
                f"{label}: page {page.page or '-'}/{page.total_pages or '-'} "
                f"-> {len(page.listings)} listings",
            )

        found += scraper.search(
            query,
            pages=args.pages,
            limit=args.limit,
            url=args.url,
            market=args.market,
            seen=seen,
            skip_promoted=args.skip_promoted,
            seller_type=args.seller_type,
            on_page=on_page,
            **filters,
        )
    _log(args, f"{len(found)} unique listing(s)")
    _emit(args, found, listings_to_csv)
    return 0


def cmd_item(args: argparse.Namespace) -> int:
    scraper = _scraper(args)
    failures = 0

    def on_error(value: Any, error: Exception) -> None:
        nonlocal failures
        failures += 1
        _log(args, f"skip {value}: {error}")

    found = scraper.items(args.items, market=args.market, on_error=on_error)
    _emit(args, found, items_to_csv)
    return 1 if failures and not found else 0


def cmd_seller(args: argparse.Namespace) -> int:
    scraper = _scraper(args)
    found = []
    for value in args.sellers:
        try:
            profile = scraper.seller(
                value, listings=args.listings, scrolls=args.scrolls, market=args.market
            )
        except Exception as exc:
            _log(args, f"skip {value}: {exc}")
            continue
        extra = f", {len(profile.listings)} listing(s)" if args.listings else ""
        _log(args, f"{profile.login} ({profile.id}){extra}")
        found.append(profile)
    if args.format == "csv" and args.listings:
        _emit(args, [lst for p in found for lst in p.listings], listings_to_csv)
    else:
        _emit(args, found, sellers_to_csv)
    return 0 if found else 1


def _load_state(path: str | None) -> set[str]:
    if not path or not Path(path).exists():
        return set()
    return {line.strip() for line in Path(path).read_text("utf-8").splitlines() if line.strip()}


def cmd_watch(args: argparse.Namespace) -> int:
    if args.url and args.query:
        raise SystemExit("error: use either QUERY or --url, not both")
    if not args.query and not args.url and not _filters(args):
        raise SystemExit("error: give a search text, --url or at least one filter")
    scraper = _scraper(args)
    seen = _load_state(args.state_file)
    sink = open(args.output, "a", encoding="utf-8") if args.output else _stdout()

    def on_poll(number: int, new: int) -> None:
        if args.state_file:
            Path(args.state_file).write_text("".join(f"{i}\n" for i in sorted(seen)), "utf-8")
        _log(args, f"poll {number}: {new} new listing(s), {len(seen)} known")

    try:
        for listing in scraper.watch(
            args.query,
            interval=args.interval,
            max_polls=args.max_polls,
            emit_existing=args.emit_existing,
            seen=seen,
            url=args.url,
            market=args.market,
            seller_type=args.seller_type,
            on_poll=on_poll,
            **_filters(args),
        ):
            sink.write(json.dumps(to_dict(listing), ensure_ascii=False) + "\n")
            sink.flush()
    except KeyboardInterrupt:
        _log(args, "stopped")
    finally:
        if args.output:
            sink.close()
    return 0


def cmd_categories(args: argparse.Namespace) -> int:
    found = _scraper(args).categories(search=args.search, market=args.market)
    _log(args, f"{len(found)} categor{'y' if len(found) == 1 else 'ies'}")
    _emit(args, found)
    return 0


def cmd_markets(args: argparse.Namespace) -> int:
    out = _stdout()
    out.write(f"{'code':<6}{'site':<16}{'currency':<10}language\n")
    for m in MARKETS.values():
        out.write(f"{m.code:<6}{m.domain:<16}{m.currency:<10}{m.language}\n")
    return 0


COMMANDS = {
    "search": cmd_search,
    "item": cmd_item,
    "seller": cmd_seller,
    "watch": cmd_watch,
    "categories": cmd_categories,
    "markets": cmd_markets,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
