#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Archive (delete) per-case memory stores older than N days.

Targets stores whose name matches the `bb-case-*` prefix. The shared
`bb-platform-priors` store is hard-skipped regardless of age.

Dry-run by default. Pass `--apply` to actually delete.

Usage:
    python scripts/archive_old_case_memory_stores.py
    python scripts/archive_old_case_memory_stores.py --days 14
    python scripts/archive_old_case_memory_stores.py --days 14 --apply
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

PLATFORM_STORE_NAME = "bb-platform-priors"
CASE_PREFIXES = ("bb-case-", "bb-forensic-learnings-")


def _parse_created_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _is_case_store(name: str | None) -> bool:
    if not name:
        return False
    return any(name.startswith(p) for p in CASE_PREFIXES)


def find_archivable(client: Any, *, days: int, now: datetime | None = None) -> list[dict[str, Any]]:
    beta = getattr(client, "beta", None)
    stores_api = getattr(beta, "memory_stores", None)
    if stores_api is None:
        raise RuntimeError("client.beta.memory_stores not available on this SDK.")
    page = stores_api.list()
    items = getattr(page, "data", None)
    if items is None:
        try:
            items = list(page)
        except TypeError:
            items = []
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    out: list[dict[str, Any]] = []
    for item in items:
        name = getattr(item, "name", None)
        if name == PLATFORM_STORE_NAME:
            continue
        if not _is_case_store(name):
            continue
        created = _parse_created_at(getattr(item, "created_at", None))
        if created is None or created > cutoff:
            continue
        out.append(
            {
                "id": getattr(item, "id", None),
                "name": name,
                "created_at": created.isoformat(timespec="seconds"),
            }
        )
    return out


def archive(client: Any, *, days: int, apply: bool) -> int:
    candidates = find_archivable(client, days=days)
    if not candidates:
        print(f"no case stores older than {days} days.")
        return 0

    stores_api = client.beta.memory_stores
    deleted = 0
    for c in candidates:
        if c["name"] == PLATFORM_STORE_NAME:
            print(f"skip: {c['name']} ({c['id']}) is the platform store; refusing.")
            continue
        if not apply:
            print(f"DRY-RUN would delete: {c['name']} ({c['id']}) created={c['created_at']}")
            continue
        try:
            stores_api.delete(c["id"])
            print(f"deleted: {c['name']} ({c['id']})")
            deleted += 1
        except Exception as exc:
            print(f"error deleting {c['name']} ({c['id']}): {exc}", file=sys.stderr)
    if not apply:
        print(f"DRY-RUN complete. {len(candidates)} stores match. pass --apply to delete.")
    else:
        print(f"deleted {deleted}/{len(candidates)} matching stores.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--days", type=int, default=30, help="age threshold in days (default: 30)")
    p.add_argument("--apply", action="store_true", help="actually delete (default: dry-run)")
    args = p.parse_args(argv)

    from black_box.analysis.client import build_client

    client = build_client()
    try:
        return archive(client, days=args.days, apply=args.apply)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
