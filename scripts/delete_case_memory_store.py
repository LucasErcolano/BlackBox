#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Delete one specific managed memory store by id or name.

Hard guard: refuses to delete `bb-platform-priors`.
Confirms interactively unless `--yes` is passed.

Usage:
    python scripts/delete_case_memory_store.py --id memstore_abc
    python scripts/delete_case_memory_store.py --name bb-case-foo --yes
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

PLATFORM_STORE_NAME = "bb-platform-priors"


def _resolve(client: Any, *, id_: str | None, name: str | None) -> dict[str, Any] | None:
    stores_api = getattr(getattr(client, "beta", None), "memory_stores", None)
    if stores_api is None:
        raise RuntimeError("client.beta.memory_stores not available on this SDK.")
    page = stores_api.list()
    items = getattr(page, "data", None)
    if items is None:
        try:
            items = list(page)
        except TypeError:
            items = []
    for item in items:
        iid = getattr(item, "id", None)
        iname = getattr(item, "name", None)
        if id_ is not None and iid == id_:
            return {"id": iid, "name": iname}
        if name is not None and iname == name:
            return {"id": iid, "name": iname}
    return None


def delete_store(client: Any, *, id_: str | None, name: str | None, yes: bool) -> int:
    if not id_ and not name:
        print("error: pass --id or --name", file=sys.stderr)
        return 2

    target = _resolve(client, id_=id_, name=name)
    if target is None:
        print(f"error: no store matched (id={id_!r}, name={name!r})", file=sys.stderr)
        return 1

    if target["name"] == PLATFORM_STORE_NAME:
        print(
            f"refused: {PLATFORM_STORE_NAME!r} is the platform priors store; "
            "deleting it would erase verified human-curated knowledge.",
            file=sys.stderr,
        )
        return 3

    if not yes:
        prompt = f"DELETE {target['name']} ({target['id']})? type 'yes' to confirm: "
        try:
            answer = input(prompt)
        except EOFError:
            answer = ""
        if answer.strip().lower() != "yes":
            print("aborted.")
            return 0

    stores_api = client.beta.memory_stores
    stores_api.delete(target["id"])
    print(f"deleted: {target['name']} ({target['id']})")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--id", dest="id_", help="store id to delete")
    p.add_argument("--name", help="store name to delete")
    p.add_argument("--yes", action="store_true", help="skip the confirm prompt")
    args = p.parse_args(argv)

    from black_box.analysis.client import build_client

    client = build_client()
    try:
        return delete_store(client, id_=args.id_, name=args.name, yes=args.yes)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
