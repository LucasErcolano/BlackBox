# SPDX-License-Identifier: MIT
"""Summarize data/costs.jsonl.

Real vs synthetic split keys on wall_time_s >= 0.1 (fixtures use tiny stubs).
Prints total at list price, by prompt_kind, top N entries.

Flags:
    --csv           emit CSV to stdout instead of the human table
    --chart PATH    save a cumulative-cost matplotlib curve to PATH
    --since DATE    filter by ts field if present (entries without ts pass through)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def filter_since(rows: list[dict], since: str | None) -> list[dict]:
    """Drop rows whose ts is older than `since`. Rows without ts are kept."""
    if not since:
        return rows
    cutoff = datetime.fromisoformat(since)
    out: list[dict] = []
    for r in rows:
        ts = r.get("ts")
        if ts is None:
            out.append(r)
            continue
        try:
            if datetime.fromisoformat(str(ts)) >= cutoff:
                out.append(r)
        except ValueError:
            out.append(r)
    return out


def emit_csv(rows: list[dict]) -> None:
    cols = [
        "prompt_kind", "model", "usd_cost", "wall_time_s",
        "cached_input_tokens", "cache_creation_tokens",
        "uncached_input_tokens", "output_tokens", "ts",
    ]
    w = csv.DictWriter(sys.stdout, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)


def save_chart(rows: list[dict], out_path: Path) -> None:
    """Cumulative USD spend vs call index. Line chart, NTSB palette."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    costs = [float(r.get("usd_cost", 0) or 0) for r in rows]
    cum: list[float] = []
    running = 0.0
    for c in costs:
        running += c
        cum.append(running)

    fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=140)
    ax.plot(range(1, len(cum) + 1), cum, color="#1c1c1a", linewidth=1.8)
    ax.set_xlabel("call #", color="#6b6b66")
    ax.set_ylabel("cumulative USD", color="#6b6b66")
    ax.set_title(f"Black Box — cumulative API spend (n={len(cum)}, ${cum[-1] if cum else 0:.2f})",
                 color="#1c1c1a", fontsize=11)
    ax.grid(True, alpha=0.25, linewidth=0.5)
    ax.set_facecolor("#fffdf8")
    fig.patch.set_facecolor("#f6f4ef")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="data/costs.jsonl")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--min-wall-s", type=float, default=0.1,
                    help="entries below this are flagged as test fixtures")
    ap.add_argument("--csv", action="store_true", help="emit CSV instead of table")
    ap.add_argument("--chart", default=None,
                    help="save cumulative-cost PNG to this path")
    ap.add_argument("--since", default=None,
                    help="YYYY-MM-DD; filter entries with ts older than this")
    args = ap.parse_args()

    rows = load(Path(args.path))
    rows = filter_since(rows, args.since)
    if not rows:
        print(f"no entries at {args.path}")
        return

    if args.csv:
        emit_csv(rows)
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

    if args.chart:
        chart_path = Path(args.chart)
        save_chart(rows, chart_path)
        print(f"\nchart -> {chart_path}")


if __name__ == "__main__":
    main()
