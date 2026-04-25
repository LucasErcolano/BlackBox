#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Export every memory path's version history from a managed memory store.

Output: `data/memory_exports/<store_id>/<sanitized_path>.versions.jsonl`,
one JSON line per version with version_id, created_at, sha256, size, and
optionally `content` if `--include-content` is set.

Usage:
    python scripts/export_memory_versions.py --store bb-platform-priors
    python scripts/export_memory_versions.py --store memstore_abc --include-content
    python scripts/export_memory_versions.py --store bb-platform-priors --output /tmp/exports
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable


def _resolve_store(stores_api: Any, key: str) -> Any:
    page = stores_api.list()
    items = getattr(page, "data", None)
    if items is None:
        try:
            items = list(page)
        except TypeError:
            items = []
    for item in items:
        if getattr(item, "id", None) == key or getattr(item, "name", None) == key:
            return item
    return None


def _safe_filename(path: str) -> str:
    return path.strip("/").replace("/", "__") or "_root"


def _list_paths(memories_api: Any, store_id: str) -> Iterable[Any]:
    page = memories_api.list(memory_store_id=store_id)
    items = getattr(page, "data", None)
    if items is None:
        try:
            items = list(page)
        except TypeError:
            items = []
    return items


def _list_versions(memories_api: Any, store_id: str, path: str) -> Iterable[Any]:
    versions_api = getattr(memories_api, "versions", None)
    if versions_api is not None:
        page = versions_api.list(memory_store_id=store_id, path=path)
    else:
        page = memories_api.list(memory_store_id=store_id, path=path, history=True)
    items = getattr(page, "data", None)
    if items is None:
        try:
            items = list(page)
        except TypeError:
            items = []
    return items


def _version_record(v: Any, *, include_content: bool) -> dict[str, Any]:
    content = getattr(v, "content", None)
    if isinstance(content, str):
        sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        size = len(content.encode("utf-8"))
    else:
        sha256 = getattr(v, "sha256", None)
        size = getattr(v, "size", None) or getattr(v, "byte_size", None)
    rec = {
        "version_id": getattr(v, "id", None) or getattr(v, "version_id", None),
        "created_at": str(getattr(v, "created_at", "") or ""),
        "sha256": sha256,
        "size": size,
    }
    if include_content:
        rec["content"] = content
    return rec


def export_versions(
    client: Any,
    *,
    store: str,
    output_root: Path,
    include_content: bool,
) -> tuple[int, int]:
    stores_api = getattr(getattr(client, "beta", None), "memory_stores", None)
    if stores_api is None:
        raise RuntimeError("client.beta.memory_stores not available on this SDK.")
    memories_api = getattr(stores_api, "memories", None)
    if memories_api is None:
        raise RuntimeError("client.beta.memory_stores.memories not available on this SDK.")

    target = _resolve_store(stores_api, store)
    if target is None:
        raise RuntimeError(f"no store found matching {store!r}")

    store_id = getattr(target, "id", store)
    out_dir = output_root / store_id
    out_dir.mkdir(parents=True, exist_ok=True)

    paths_seen = 0
    versions_seen = 0
    for memory in _list_paths(memories_api, store_id):
        path = getattr(memory, "path", None)
        if not path:
            continue
        paths_seen += 1
        out_file = out_dir / f"{_safe_filename(path)}.versions.jsonl"
        with out_file.open("w", encoding="utf-8") as fh:
            for v in _list_versions(memories_api, store_id, path):
                rec = _version_record(v, include_content=include_content)
                fh.write(json.dumps(rec, sort_keys=True) + "\n")
                versions_seen += 1
        print(f"wrote {out_file} (path={path})")
    return paths_seen, versions_seen


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--store", required=True, help="store name or id")
    p.add_argument(
        "--output",
        default="data/memory_exports",
        help="root output directory (default: data/memory_exports)",
    )
    p.add_argument("--include-content", action="store_true", help="include version body in dump")
    args = p.parse_args(argv)

    from black_box.analysis.client import build_client

    client = build_client()
    try:
        paths, versions = export_versions(
            client,
            store=args.store,
            output_root=Path(args.output),
            include_content=args.include_content,
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"done. paths={paths} versions={versions}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
