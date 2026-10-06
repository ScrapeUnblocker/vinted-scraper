"""Write records as JSON, JSON Lines or CSV."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Sequence
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, TextIO

from .models import Item, Listing, Seller

LIST_SEPARATOR = " | "


def to_dict(record: Any) -> dict[str, Any]:
    """A record (dataclass or dict) as a plain dict."""
    if hasattr(record, "to_dict"):
        return record.to_dict()
    if isinstance(record, dict):
        return dict(record)
    raise TypeError(f"cannot export {type(record).__name__}")


def to_json(records: Iterable[Any], *, pretty: bool = False) -> str:
    """Serialize records as a JSON array."""
    data = [to_dict(r) for r in records]
    return json.dumps(data, ensure_ascii=False, indent=2 if pretty else None)


def to_jsonl(records: Iterable[Any]) -> str:
    """Serialize records as JSON Lines (one object per line)."""
    return "".join(json.dumps(to_dict(r), ensure_ascii=False) + "\n" for r in records)


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        if all(not isinstance(v, (dict, list)) for v in value):
            return LIST_SEPARATOR.join(str(v) for v in value)
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False) if value else ""
    return value


def _columns(records: Sequence[Any]) -> list[str]:
    first = records[0]
    if is_dataclass(first):
        return [f.name for f in fields(first)]
    columns: list[str] = []
    for record in records:
        for key in to_dict(record):
            if key not in columns:
                columns.append(key)
    return columns


def write_csv(
    records: Iterable[Any],
    target: str | Path | TextIO,
    *,
    columns: Sequence[str] | None = None,
    exclude: Sequence[str] = (),
) -> int:
    """Write records as CSV. Lists become ``a | b`` cells, nested objects JSON.

    Files are written as UTF-8 with a BOM so Excel shows accents and currency
    symbols correctly. Returns the number of rows written.
    """
    rows = list(records)
    cols = [c for c in (columns or (_columns(rows) if rows else [])) if c not in exclude]

    def dump(handle: TextIO) -> None:
        writer = csv.DictWriter(handle, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for record in rows:
            data = to_dict(record)
            writer.writerow({c: _cell(data.get(c)) for c in cols})

    if isinstance(target, (str, Path)):
        with open(target, "w", encoding="utf-8-sig", newline="") as handle:
            dump(handle)
    else:
        dump(target)
    return len(rows)


def listings_to_csv(listings: Iterable[Listing], target: str | Path | TextIO) -> int:
    """Write search or wardrobe listings as CSV (one row per listing)."""
    return write_csv(listings, target)


def items_to_csv(items: Iterable[Item], target: str | Path | TextIO) -> int:
    """Write item details as CSV (one row per item)."""
    return write_csv(items, target)


def sellers_to_csv(sellers: Iterable[Seller], target: str | Path | TextIO) -> int:
    """Write seller profiles as CSV (one row per seller, without their listings)."""
    return write_csv(sellers, target, exclude=("listings",))


def csv_string(records: Iterable[Any], **options: Any) -> str:
    """CSV as a string (handy in notebooks and tests)."""
    buffer = io.StringIO()
    write_csv(records, buffer, **options)
    return buffer.getvalue()
