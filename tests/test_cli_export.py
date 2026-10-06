from __future__ import annotations

import csv
import io
import json

import pytest
from conftest import card, catalog_page, item_page, member_page

from scrapeunblocker_vinted import cli
from scrapeunblocker_vinted.export import csv_string, sellers_to_csv, to_jsonl, write_csv
from scrapeunblocker_vinted.models import Listing, Seller
from scrapeunblocker_vinted.parsing import parse_item_page, parse_search_page


def test_parser_search_arguments():
    args = cli.build_parser().parse_args(
        [
            "search",
            "levis 501",
            "jeans",
            "-m",
            "uk",
            "--brand",
            "10",
            "--condition",
            "new,very_good",
            "--price-max",
            "30",
            "--sort",
            "price_asc",
            "-p",
            "3",
            "-n",
            "50",
            "--skip-promoted",
            "--seller-type",
            "private",
            "-f",
            "csv",
            "-o",
            "out.csv",
        ]
    )
    assert args.queries == ["levis 501", "jeans"]
    assert (args.market, args.pages, args.limit, args.format) == ("uk", 3, 50, "csv")
    assert cli._filters(args) == {
        "brand_ids": ["10"],
        "conditions": ["new,very_good"],
        "price_to": 30.0,
        "sort": "price_asc",
    }


def test_parser_other_commands():
    parser = cli.build_parser()
    seller = parser.parse_args(["seller", "123", "--listings", "--scrolls", "2"])
    assert (seller.sellers, seller.listings, seller.scrolls) == (["123"], True, 2)
    watch = parser.parse_args(["watch", "nike", "--interval", "30", "--max-polls", "2"])
    assert (watch.query, watch.interval, watch.max_polls) == ("nike", 30.0, 2)
    with pytest.raises(SystemExit):
        parser.parse_args(["search", "--sort", "cheapest"])
    with pytest.raises(SystemExit):
        parser.parse_args([])


class StubScraper:
    """Replaces VintedScraper in CLI tests."""

    instances: list[StubScraper] = []

    def __init__(self, **options):
        self.options = options
        self.calls = []
        StubScraper.instances.append(self)

    def search(self, query, **options):
        self.calls.append(("search", query, options))
        html = catalog_page([card(1), card(2, brand=None, title="Plain")], total_pages=1)
        return parse_search_page(html, "uk").listings

    def items(self, values, market=None, on_error=None):
        on_error("bad", ValueError("nope"))
        return [parse_item_page(item_page(), "uk")]

    def watch(self, query, **options):
        self.calls.append(("watch", query, options))
        options["seen"].update({"7", "8"})
        options["on_poll"](1, 0)
        yield parse_search_page(catalog_page([card(8)]), "uk").listings[0]


@pytest.fixture
def stub(monkeypatch):
    StubScraper.instances.clear()
    monkeypatch.setattr(cli, "VintedScraper", StubScraper)
    return StubScraper


def test_cli_search_json(stub, capsys):
    assert cli.main(["search", "levis", "-m", "uk", "--brand", "10", "-q"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [d["id"] for d in data] == ["1", "2"]
    scraper = stub.instances[0]
    assert scraper.options["market"] == "uk"
    _, query, options = scraper.calls[0]
    assert query == "levis" and options["brand_ids"] == ["10"] and options["pages"] == 1


def test_cli_search_csv_file(stub, tmp_path):
    out = tmp_path / "listings.csv"
    assert cli.main(["search", "levis", "-f", "csv", "-o", str(out), "-q"]) == 0
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM for Excel
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    assert [r["id"] for r in rows] == ["1", "2"]
    assert rows[1]["brand"] == ""


def test_cli_search_needs_a_query_or_filter(stub):
    with pytest.raises(SystemExit):
        cli.main(["search"])


def test_cli_item_skips_failures(stub, capsys):
    assert cli.main(["item", "bad", "555", "--pretty"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)[0]["id"] == "555"
    assert "skip bad" in captured.err


def test_cli_watch_writes_jsonl_and_state(stub, tmp_path, capsys):
    state = tmp_path / "seen_ids.txt"
    state.write_text("7\n", "utf-8")
    assert cli.main(["watch", "nike", "--state-file", str(state), "--max-polls", "1", "-q"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert [json.loads(line)["id"] for line in lines] == ["8"]
    assert state.read_text("utf-8").split() == ["7", "8"]
    _, _, options = stub.instances[0].calls[0]
    assert options["max_polls"] == 1


def test_cli_markets(capsys):
    assert cli.main(["markets"]) == 0
    out = capsys.readouterr().out
    assert "vinted.co.uk" in out and "PLN" in out


def test_cli_reports_bad_input(stub, capsys):
    stub.search = lambda self, q, **o: (_ for _ in ()).throw(ValueError("unknown condition"))
    assert cli.main(["search", "x", "-q"]) == 2
    assert "unknown condition" in capsys.readouterr().err


def test_csv_cells():
    listing = Listing(id="1", title="A", url=None, photos=["p1", "p2"], promoted=True)
    rows = list(csv.DictReader(io.StringIO(csv_string([listing]))))
    assert rows[0]["photos"] == "p1 | p2"
    assert rows[0]["promoted"] == "true"
    assert rows[0]["price"] == ""


def test_write_csv_dicts_and_jsonl():
    buffer = io.StringIO()
    assert write_csv([{"a": 1, "b": {"x": 1}}, {"a": 2, "c": [{"y": 2}]}], buffer) == 2
    rows = list(csv.DictReader(io.StringIO(buffer.getvalue())))
    assert rows[0]["b"] == '{"x": 1}' and rows[1]["c"] == '[{"y": 2}]'
    assert to_jsonl([{"a": "é"}]) == '{"a": "é"}\n'


def test_sellers_csv_excludes_listings():
    seller = Seller(id="1", login="x", url=None, listings=[Listing(id="9", title="t", url=None)])
    buffer = io.StringIO()
    sellers_to_csv([seller], buffer)
    header = buffer.getvalue().splitlines()[0].split(",")
    assert "listings" not in header and "login" in header


def test_member_page_fixture_is_parseable():
    from scrapeunblocker_vinted.parsing import parse_member_page

    assert parse_member_page(member_page(), "fr").login == "jane_closet"
