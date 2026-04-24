# SPDX-License-Identifier: MIT
"""Summarize data/costs.jsonl.

Real vs synthetic split keys on wall_time_s >= 0.1 (fixtures use tiny stubs).
Prints total at list price, by prompt_kind, top N entries.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="data/costs.jsonl")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--min-wall-s", type=float, default=0.1,
                    help="entries below this are flagged as test fixtures")
    args = ap.parse_args()

    rows = load(Path(args.path))
    if not rows:
        print(f"no entries at {args.path}")
        return

    real = [r for r in rows if (r.get("wall_time_s", 0) or 0) >= args.min_wall_s]
    fake = [r for r in rows if (r.get("wall_time_s", 0) or 0) < args.min_wall_s]

    def usd(rs: list[dict]) -> float:
        return sum((r.get("usd_cost", 0) or 0) for r in rs)

    print(f"entries       : {len(rows)}")
    print(f"real (wall>={args.min_wall_s}s): n={len(real):3d}  ${usd(real):7.2f}")
    print(f"fixtures      : n={len(fake):3d}  ${usd(fake):7.2f}")
    print(f"TOTAL         : ${usd(rows):7.2f}")
    print()

    by_kind: dict[str, list[int | float]] = {}
    for r in real:
        k = r.get("prompt_kind", "?")
        slot = by_kind.setdefault(k, [0, 0.0])
        slot[0] = int(slot[0]) + 1
        slot[1] = float(slot[1]) + float(r.get("usd_cost", 0) or 0)
    print("by prompt_kind (real only):")
    for k, (n, u) in sorted(by_kind.items(), key=lambda x: -float(x[1][1])):
        print(f"  {k:32s} n={n:>3}  ${float(u):6.2f}")
    print()

    print(f"top {args.top} real entries:")
    real.sort(key=lambda r: -(r.get("usd_cost", 0) or 0))
    for r in real[:args.top]:
        print(
            f"  ${r['usd_cost']:5.2f}  "
            f"cr={r.get('cached_input_tokens',0):>8,} "
            f"cw={r.get('cache_creation_tokens',0):>7,} "
            f"uc={r.get('uncached_input_tokens',0):>5,} "
            f"o={r.get('output_tokens',0):>6,}  "
            f"wall={r.get('wall_time_s',0):>4.0f}s  "
            f"{r.get('prompt_kind','?')}"
        )


if __name__ == "__main__":
    main()
