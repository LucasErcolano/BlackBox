# SPDX-License-Identifier: MIT
"""Regenerate markdown reports for the 3 hero cases from saved analysis.json.

Reads:  data/final_runs/<case>/analysis.json
Writes: data/final_runs/<case>/report.md
        demo_assets/pdfs/<case>.md   (mirror — same dir currently hosts the old PDFs)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/hz/Desktop/BlackBox/src")
from black_box.reporting import build_report  # noqa: E402

CASES = [
    ("sanfer_tunnel", "post_mortem", 3626.7),
    ("car_1", "scenario_mining", 970.2),
    ("boat_lidar", "scenario_mining", 416.76),
]

RUNS = Path("data/final_runs")
MIRROR = Path("demo_assets/pdfs")


def main() -> int:
    MIRROR.mkdir(parents=True, exist_ok=True)
    for case, mode, dur in CASES:
        src = RUNS / case / "analysis.json"
        if not src.exists():
            print(f"skip {case}: no analysis.json")
            continue
        data = json.loads(src.read_text())
        case_meta = {
            "case_key": case,
            "mode": mode,
            "duration_s": dur,
        }
        out = RUNS / case / "report.md"
        build_report(data, artifacts={}, out_pdf=out, case_meta=case_meta)
        mirror = MIRROR / f"{case}.md"
        mirror.write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"{case}: {out} ({out.stat().st_size/1024:.1f} KB) + mirror {mirror}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
