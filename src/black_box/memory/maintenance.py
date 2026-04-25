# SPDX-License-Identifier: MIT
"""L1–L4 maintenance: age-based prune (L1) and dedup compaction (L2, L3).

Append-only JSONL keeps writes simple and replay deterministic, but the files
grow unbounded. This module provides idempotent compaction that preserves
semantics:

* L1 case: drop records older than `max_age_days` (per t_logged).
* L2 platform: per (platform, signature) keep the latest record by t_logged;
  hits are summed across all collapsed rows; confidence = max.
* L3 taxonomy: per (bug_class, signature) sum count, keep latest t_logged.

L4 eval is ground truth — never compacted, never pruned.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel

from .records import CaseRecord, PlatformPrior, TaxonomyCount
from .store import JsonlStore, default_memory_root


@dataclass
class CompactReport:
    layer: str
    before: int
    after: int
    path: Path

    @property
    def removed(self) -> int:
        return self.before - self.after


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [ln for ln in (line.strip() for line in f) if ln]


def _write_records(path: Path, records: Iterable[BaseModel], *, dry_run: bool) -> int:
    lines = [r.model_dump_json() for r in records]
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for ln in lines:
                f.write(ln + "\n")
    return len(lines)


def prune_case(root: Path | None = None, *, max_age_days: int = 30, dry_run: bool = False) -> CompactReport:
    path = (root or default_memory_root()) / "L1_case.jsonl"
    store = JsonlStore(path, CaseRecord)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    before = len(_read_lines(path))
    kept: list[CaseRecord] = []
    for rec in store.iter_all():
        try:
            t = datetime.fromisoformat(rec.t_logged)  # type: ignore[attr-defined]
        except ValueError:
            kept.append(rec)  # type: ignore[arg-type]
            continue
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        if t >= cutoff:
            kept.append(rec)  # type: ignore[arg-type]
    after = _write_records(path, kept, dry_run=dry_run)
    return CompactReport("L1_case", before, after, path)


def compact_platform(root: Path | None = None, *, dry_run: bool = False) -> CompactReport:
    path = (root or default_memory_root()) / "L2_platform.jsonl"
    store = JsonlStore(path, PlatformPrior)
    before = len(_read_lines(path))
    grouped: dict[tuple[str, str], PlatformPrior] = {}
    hits_sum: dict[tuple[str, str], int] = {}
    conf_max: dict[tuple[str, str], float] = {}
    for rec in store.iter_all():
        r: PlatformPrior = rec  # type: ignore[assignment]
        key = (r.platform, r.signature)
        hits_sum[key] = hits_sum.get(key, 0) + r.hits
        conf_max[key] = max(conf_max.get(key, 0.0), r.confidence)
        prev = grouped.get(key)
        if prev is None or r.t_logged > prev.t_logged:
            grouped[key] = r
    merged: list[PlatformPrior] = []
    for key, latest in grouped.items():
        merged.append(
            latest.model_copy(update={"hits": hits_sum[key], "confidence": conf_max[key]})
        )
    after = _write_records(path, merged, dry_run=dry_run)
    return CompactReport("L2_platform", before, after, path)


def compact_taxonomy(root: Path | None = None, *, dry_run: bool = False) -> CompactReport:
    path = (root or default_memory_root()) / "L3_taxonomy.jsonl"
    store = JsonlStore(path, TaxonomyCount)
    before = len(_read_lines(path))
    counts: dict[tuple[str, str], int] = {}
    latest_t: dict[tuple[str, str], str] = {}
    for rec in store.iter_all():
        r: TaxonomyCount = rec  # type: ignore[assignment]
        key = (r.bug_class, r.signature)
        counts[key] = counts.get(key, 0) + r.count
        if r.t_logged > latest_t.get(key, ""):
            latest_t[key] = r.t_logged
    merged = [
        TaxonomyCount(
            bug_class=bc, signature=sig, count=counts[(bc, sig)], t_logged=latest_t[(bc, sig)]
        )
        for (bc, sig) in counts
    ]
    after = _write_records(path, merged, dry_run=dry_run)
    return CompactReport("L3_taxonomy", before, after, path)


def run_all(
    root: Path | None = None, *, max_age_days: int = 30, dry_run: bool = False
) -> list[CompactReport]:
    return [
        prune_case(root, max_age_days=max_age_days, dry_run=dry_run),
        compact_platform(root, dry_run=dry_run),
        compact_taxonomy(root, dry_run=dry_run),
    ]


def _main() -> int:
    p = argparse.ArgumentParser(description="Prune + compact memory layers L1–L3 (L4 untouched).")
    p.add_argument("--root", type=Path, default=None)
    p.add_argument("--max-age-days", type=int, default=30, help="L1 age cutoff (default 30)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--prune", action="store_true", help="Run L1 prune only.")
    p.add_argument("--compact", action="store_true", help="Run L2+L3 compact only.")
    args = p.parse_args()
    if not args.prune and not args.compact:
        reports = run_all(args.root, max_age_days=args.max_age_days, dry_run=args.dry_run)
    else:
        reports = []
        if args.prune:
            reports.append(prune_case(args.root, max_age_days=args.max_age_days, dry_run=args.dry_run))
        if args.compact:
            reports.append(compact_platform(args.root, dry_run=args.dry_run))
            reports.append(compact_taxonomy(args.root, dry_run=args.dry_run))
    print(json.dumps([{"layer": r.layer, "before": r.before, "after": r.after, "removed": r.removed} for r in reports], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
