#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""List all native Anthropic Managed Agents memory stores in the org.

Usage:
    python scripts/list_managed_memory_stores.py
    python scripts/list_managed_memory_stores.py --json

Falls back gracefully if the installed anthropic SDK predates `memory_stores`.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any


def _fmt_ts(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat(timespec="seconds")
    return str(value)


def _row(item: Any) -> dict[str, Any]:
    return {
        "id": getattr(item, "id", None),
        "name": getattr(item, "name", None),
        "created_at": _fmt_ts(getattr(item, "created_at", None)),
        "size": getattr(item, "size", None) or getattr(item, "byte_size", None),
        "memory_count": getattr(item, "memory_count", None),
        "description": getattr(item, "description", None),
    }


def list_stores(client: Any) -> list[dict[str, Any]]:
    beta = getattr(client, "beta", None)
    stores_api = getattr(beta, "memory_stores", None)
    if stores_api is None:
        raise RuntimeError(
            "client.beta.memory_stores not available on this anthropic SDK; "
            "upgrade to a build that exposes managed memory stores."
        )
    page = stores_api.list()
    items = getattr(page, "data", None)
    if items is None:
        try:
            items = list(page)
        except TypeError:
            items = []
    return [_row(item) for item in items]


def _print_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("(no memory stores)")
        return
    headers = ["id", "name", "created_at", "size", "memory_count"]
    widths = {h: max(len(h), max((len(str(r.get(h) or "")) for r in rows), default=0)) for h in headers}
    line = "  ".join(h.ljust(widths[h]) for h in headers)
    print(line)
    print("  ".join("-" * widths[h] for h in headers))
    for r in rows:
        print("  ".join(str(r.get(h) or "").ljust(widths[h]) for h in headers))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = p.parse_args(argv)

    from black_box.analysis.client import build_client

    client = build_client()
    try:
        rows = list_stores(client)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        _print_table(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
