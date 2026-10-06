"""Scrape Vinted through the ScrapeUnblocker ``getPageSource`` API.

ScrapeUnblocker loads every Vinted page in a real browser and returns the HTML;
:mod:`scrapeunblocker_vinted.parsing` turns it into :class:`Listing`,
:class:`Item`, :class:`Seller` and :class:`Category` records. A seller's
wardrobe is rendered by running browser steps (wait for the item grid, then
scroll) in the same request.

Timeouts, transient API errors and half-loaded pages are retried with doubling
backoff, so a long collection run keeps going.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Iterator, Sequence
from typing import Any, Callable

from .markets import Market, get_market, market_from_url
from .models import Category, Item, Listing, SearchPage, Seller
from .parsing import (
    VintedNotFoundError,
    VintedParseError,
    parse_categories,
    parse_item_page,
    parse_member_page,
    parse_search_page,
    parse_wardrobe,
)
from .urls import (
    MAX_PAGES,
    build_item_url,
    build_member_url,
    build_search_url,
    is_catalog_url,
    with_page,
)

#: Browser-step budget: one ``wait_for`` plus (scroll, wait) pairs, 10 steps max.
MAX_SCROLLS = 4

SELLER_TYPES = ("private", "business")

_TRANSIENT_NAMES = (
    "UpstreamOutageError",
    "RateLimitError",
    "ScrapeTimeoutError",
    "BrowserTimeoutError",
    "BlockedError",
    "ServerError",
    "ConnectionError",
)

_FILTERS = (
    "catalog_ids",
    "brand_ids",
    "size_ids",
    "color_ids",
    "material_ids",
    "conditions",
    "price_from",
    "price_to",
    "sort",
)


def _transient_errors() -> tuple[type[BaseException], ...]:
    """Best-effort tuple of ScrapeUnblocker exceptions worth retrying.

    Imported lazily so the package is usable (and unit-testable) even when the
    ``scrapeunblocker`` SDK is not installed or is an older release.
    """
    try:
        import scrapeunblocker  # type: ignore
    except Exception:  # pragma: no cover - depends on SDK availability
        return ()
    found = (getattr(scrapeunblocker, name, None) for name in _TRANSIENT_NAMES)
    return tuple(cls for cls in found if isinstance(cls, type))


def is_not_found(error: BaseException) -> bool:
    """True when the API reports that the target page answered 404/410."""
    return getattr(error, "status_code", None) in (404, 410) or type(error).__name__ in (
        "TargetNotFoundError",
        "NotFoundError",
    )


def is_step_failure(error: BaseException) -> bool:
    """True for the API's "a browser step could not run" error (it carries the page)."""
    return type(error).__name__ == "StepFailedError" or hasattr(error, "step_index")


def wardrobe_steps(scrolls: int = 3) -> list[dict[str, Any]]:
    """Browser steps that render a seller's wardrobe: wait for the item grid,
    then scroll to the bottom ``scrolls`` times to load more listings."""
    if not 0 <= scrolls <= MAX_SCROLLS:
        raise ValueError(f"scrolls must be between 0 and {MAX_SCROLLS}")
    steps: list[dict[str, Any]] = [
        {"action": "wait_for", "selector": '[data-testid="grid-item"]', "timeout_ms": 15000}
    ]
    for _ in range(scrolls):
        steps.append({"action": "scroll", "value": "bottom"})
        steps.append({"action": "wait", "value": 2000})
    return steps


class VintedScraper:
    """Search listings, read item pages and seller profiles on any Vinted country site.

    Args:
        api_key: ScrapeUnblocker key. If omitted, the SDK reads
            ``SCRAPEUNBLOCKER_KEY`` from the environment.
        client: A pre-built client (or any object exposing
            ``get_page_source(url, proxy_country=..., steps=...)``). Mainly for testing.
        market: Default Vinted site: ``fr`` (default), ``uk``, ``de``, ``it``,
            ``es``, ``nl``, ``pl``, ``us`` ... (see :data:`~scrapeunblocker_vinted.MARKETS`).
        proxy_country: Country to route requests through. Defaults to the
            market's own country, which is what Vinted expects to see.
        retries: Extra attempts per page on transient failures.
        backoff: Seconds before the first retry; doubles on every further retry.
        max_backoff: Upper bound for a single wait between retries.
        timeout: Per-request timeout passed to the SDK client.
        transient_errors: Exception classes treated as retryable. Defaults to
            the ScrapeUnblocker transient set.
        on_retry: Optional callback ``(attempt, delay_seconds, error)`` invoked
            before every retry (handy for progress output).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: Any | None = None,
        market: str | Market = "fr",
        proxy_country: str | None = None,
        retries: int = 3,
        backoff: float = 3.0,
        max_backoff: float = 60.0,
        timeout: float = 180.0,
        transient_errors: Sequence[type[BaseException]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        on_retry: Callable[[int, float, BaseException], None] | None = None,
    ) -> None:
        if client is None:
            from scrapeunblocker import Client  # local import: optional dep

            client = Client(api_key=api_key, timeout=timeout)
        self._client = client
        self.market = get_market(market)
        self.proxy_country = proxy_country.upper() if proxy_country else None
        self.retries = max(0, int(retries))
        self.backoff = float(backoff)
        self.max_backoff = float(max_backoff)
        self.on_retry = on_retry
        transient = tuple(transient_errors) if transient_errors is not None else _transient_errors()
        self._transient = (*transient, VintedParseError)
        self._sleep = sleep

    # ------------------------------------------------------------------ #
    # Low-level fetching
    # ------------------------------------------------------------------ #

    def _market(self, market: str | Market | None, url: str | None = None) -> Market:
        if market is not None:
            return get_market(market)
        if url:
            found = market_from_url(url)
            if found is not None:
                return found
        return self.market

    def _fetch(
        self,
        url: str,
        parse: Callable[[str], Any],
        market: Market,
        *,
        steps: list[dict[str, Any]] | None = None,
    ) -> Any:
        """Fetch ``url`` and parse it, retrying transient failures with backoff.

        With ``steps``, a step that cannot run (for example "wait for the item
        grid" on a seller with an empty wardrobe) is not an error: the API
        returns the page as it was at that moment, and that page is parsed.
        """
        attempt = 0
        while True:
            try:
                options: dict[str, Any] = {"proxy_country": self.proxy_country or market.country}
                if steps:
                    options["steps"] = steps
                try:
                    html = self._client.get_page_source(url, **options)
                except Exception as exc:
                    page = getattr(exc, "html", None)
                    if not (steps and is_step_failure(exc) and isinstance(page, str) and page):
                        raise
                    html = page
                return parse(html if isinstance(html, str) else "")
            except Exception as exc:
                if is_not_found(exc):
                    raise VintedNotFoundError(f"not found on Vinted: {url}") from exc
                if not isinstance(exc, self._transient) or attempt >= self.retries:
                    raise
                attempt += 1
                delay = min(self.backoff * 2 ** (attempt - 1), self.max_backoff)
                if self.on_retry is not None:
                    self.on_retry(attempt, delay, exc)
                self._sleep(delay)

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def search_url(
        self,
        query: str | None = None,
        *,
        page: int = 1,
        url: str | None = None,
        market: str | Market | None = None,
        **filters: Any,
    ) -> str:
        """The catalogue URL :meth:`search_page` would fetch."""
        unknown = set(filters) - set(_FILTERS)
        if unknown:
            raise TypeError(f"unknown search filter(s): {', '.join(sorted(unknown))}")
        if url:
            if not is_catalog_url(url):
                raise ValueError(f"not a Vinted catalogue URL: {url!r}")
            return with_page(url, page)
        return build_search_url(self._market(market), query, page=page, **filters)

    def search_page(
        self,
        query: str | None = None,
        *,
        page: int = 1,
        url: str | None = None,
        market: str | Market | None = None,
        **filters: Any,
    ) -> SearchPage:
        """Fetch one catalogue page (up to 96 listings).

        Args:
            query: Free-text search (``"nike air max"``). Optional with filters.
            page: 1-based page number (Vinted serves at most 10 pages).
            url: A Vinted catalogue URL copied from the browser, with any
                filters already applied. Replaces ``query`` and ``filters``.
            market: Market for this call (defaults to the scraper's market, or
                the URL's market when ``url`` is given).
            **filters: ``catalog_ids``, ``brand_ids``, ``size_ids``,
                ``color_ids``, ``material_ids``, ``conditions``, ``price_from``,
                ``price_to``, ``sort`` (see :func:`~scrapeunblocker_vinted.build_search_url`).
        """
        m = self._market(market, url)
        target = self.search_url(query, page=page, url=url, market=m, **filters)
        return self._fetch(target, lambda html: parse_search_page(html, m), m)

    def iter_search(
        self,
        query: str | None = None,
        *,
        pages: int = 1,
        limit: int | None = None,
        url: str | None = None,
        market: str | Market | None = None,
        seen: set[str] | None = None,
        skip_promoted: bool = False,
        seller_type: str | None = None,
        on_page: Callable[[SearchPage], None] | None = None,
        **filters: Any,
    ) -> Iterator[Listing]:
        """Yield listings page by page; see :meth:`search` for the arguments."""
        if pages < 1:
            raise ValueError("pages must be at least 1")
        if limit is not None and limit < 1:
            raise ValueError("limit must be at least 1")
        if seller_type is not None and seller_type not in SELLER_TYPES:
            raise ValueError(f"seller_type must be one of {SELLER_TYPES}, got {seller_type!r}")
        seen = set() if seen is None else seen
        label = " ".join(query.split()) if query else url
        yielded = 0
        for number in range(1, min(pages, MAX_PAGES) + 1):
            result = self.search_page(query, page=number, url=url, market=market, **filters)
            if on_page is not None:
                on_page(result)
            for listing in result.listings:
                if listing.id in seen:
                    continue
                if skip_promoted and listing.promoted:
                    continue
                if seller_type == "private" and listing.seller_business:
                    continue
                if seller_type == "business" and not listing.seller_business:
                    continue
                seen.add(listing.id)
                listing.query = label
                yield listing
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            if not result.has_next:
                return

    def search(
        self,
        query: str | None = None,
        *,
        pages: int = 1,
        limit: int | None = None,
        url: str | None = None,
        market: str | Market | None = None,
        seen: set[str] | None = None,
        skip_promoted: bool = False,
        seller_type: str | None = None,
        on_page: Callable[[SearchPage], None] | None = None,
        **filters: Any,
    ) -> list[Listing]:
        """Search Vinted and collect listings across pages.

        Args:
            query: Free-text search, e.g. ``"levis 501"``.
            pages: Pages to fetch (96 listings each, at most 10). Stops early
                when Vinted has no more results.
            limit: Return at most this many listings.
            url: A Vinted catalogue URL copied from the browser (filters included).
            market: Market for this call.
            seen: Shared set of listing IDs; listings already in it are skipped.
                Pass the same set to several calls to de-duplicate across queries.
            skip_promoted: Drop promoted ("bumped") listings.
            seller_type: ``"private"`` or ``"business"`` to keep only those sellers.
            on_page: Callback invoked with every fetched :class:`SearchPage`.
            **filters: Search filters, see :meth:`search_page`.
        """
        return list(
            self.iter_search(
                query,
                pages=pages,
                limit=limit,
                url=url,
                market=market,
                seen=seen,
                skip_promoted=skip_promoted,
                seller_type=seller_type,
                on_page=on_page,
                **filters,
            )
        )

    def search_many(
        self,
        queries: Iterable[str],
        *,
        on_query: Callable[[str, list[Listing]], None] | None = None,
        **options: Any,
    ) -> list[Listing]:
        """Run :meth:`search` for several queries, merged and de-duplicated."""
        seen: set[str] = options.pop("seen", None) or set()
        results: list[Listing] = []
        for query in queries:
            found = self.search(query, seen=seen, **options)
            if on_query is not None:
                on_query(query, found)
            results.extend(found)
        return results

    def watch(
        self,
        query: str | None = None,
        *,
        interval: float = 60.0,
        max_polls: int | None = None,
        emit_existing: bool = False,
        seen: set[str] | None = None,
        url: str | None = None,
        market: str | Market | None = None,
        skip_promoted: bool = True,
        seller_type: str | None = None,
        on_poll: Callable[[int, int], None] | None = None,
        **filters: Any,
    ) -> Iterator[Listing]:
        """Poll the newest listings and yield each one the first time it appears.

        Every poll fetches the first catalogue page sorted newest first (one
        API call). The first poll only records what is already listed, unless
        ``emit_existing`` is set.

        Args:
            query, url, market, seller_type, **filters: As for :meth:`search`.
                ``sort`` is forced to ``newest`` unless ``url`` is given.
            interval: Seconds between polls.
            max_polls: Stop after this many polls (``None`` = run until interrupted).
            emit_existing: Also yield the listings found by the first poll.
            seen: IDs already known (e.g. loaded from a state file); updated in place.
            skip_promoted: Ignore promoted listings (default), which are not new.
            on_poll: Callback ``(poll_number, new_listings)`` after every poll.
        """
        if interval < 0:
            raise ValueError("interval must not be negative")
        if not url:
            filters["sort"] = "newest"
        seen = set() if seen is None else seen
        prime = not emit_existing and not seen
        poll = 0
        while max_polls is None or poll < max_polls:
            if poll:
                self._sleep(interval)
            poll += 1
            fresh = self.search(
                query,
                url=url,
                market=market,
                seen=seen,
                skip_promoted=skip_promoted,
                seller_type=seller_type,
                **filters,
            )
            if on_poll is not None:
                on_poll(poll, 0 if prime else len(fresh))
            if prime:
                prime = False
                continue
            yield from fresh

    # ------------------------------------------------------------------ #
    # Items, sellers, categories
    # ------------------------------------------------------------------ #

    def item(self, value: str | int, *, market: str | Market | None = None) -> Item:
        """Full details of one item, by ID or Vinted item URL.

        Raises:
            VintedNotFoundError: The item does not exist (or was deleted).
        """
        m = self._market(market, str(value))
        return self._fetch(build_item_url(m, value), lambda html: parse_item_page(html, m), m)

    def items(
        self,
        values: Iterable[str | int],
        *,
        market: str | Market | None = None,
        on_error: Callable[[str | int, Exception], None] | None = None,
    ) -> list[Item]:
        """Details for several items. Items that fail are passed to ``on_error``
        (and skipped) when it is given; otherwise the first failure is raised."""
        found: list[Item] = []
        for value in values:
            try:
                found.append(self.item(value, market=market))
            except Exception as exc:
                if on_error is None:
                    raise
                on_error(value, exc)
        return found

    def seller(
        self,
        value: str | int,
        *,
        listings: bool = False,
        scrolls: int = 3,
        market: str | Market | None = None,
    ) -> Seller:
        """A seller's profile by member ID or URL, optionally with their wardrobe.

        Args:
            value: Member ID (``12345678``) or profile URL.
            listings: Also return the listings in the seller's wardrobe. They are
                rendered with browser steps in the same request.
            scrolls: Scrolls to the bottom of the wardrobe (0-4); each one loads
                another batch of listings.

        Raises:
            VintedNotFoundError: The member does not exist.
        """
        m = self._market(market, str(value))
        url = build_member_url(m, value)
        if not listings:
            return self._fetch(url, lambda html: parse_member_page(html, m), m)

        def parse(html: str) -> Seller:
            profile = parse_member_page(html, m)
            profile.listings = parse_wardrobe(html, m, seller_id=profile.id)
            return profile

        return self._fetch(url, parse, m, steps=wardrobe_steps(scrolls))

    def categories(
        self, *, search: str | None = None, market: str | Market | None = None
    ) -> list[Category]:
        """The market's category tree, flattened (one API call).

        Args:
            search: Keep only categories whose path contains this text
                (case-insensitive), e.g. ``"jeans"``.
        """
        m = self._market(market)
        found = self._fetch(f"{m.base_url}/catalog", lambda html: parse_categories(html, m), m)
        if search:
            needle = search.casefold()
            found = [c for c in found if needle in c.path.casefold()]
        return found
