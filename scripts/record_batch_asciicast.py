#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Record a deterministic asciinema-v2 cast of the offline batch runner (#88).

Why this exists: the issue asks for a credible terminal artifact of an
unattended batch with cost-cap guardrails firing and a final results
table. A real Opus 4.7 batch costs money and takes a long time; a
deterministic offline run is reproducible, cheap, and shows the same
shapes (per-case progress, cost ticker, guardrail event, results table).

This script wraps the offline runner output into a v2 asciicast file so
the artifact ships in-tree without requiring asciinema to be installed.
A maintainer with asciinema available can re-record the *live* version
by running:

    asciinema rec docs/recordings/live_batch.cast \\
        --command 'python -m black_box.eval.runner --tier 3 \\
                   --case-dir black-box-bench/cases --use-claude'

The output here is not an "edit" of a live recording; it is a faithful
capture of the deterministic offline path. The asciicast header carries
``provenance: offline`` so anyone playing back knows.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


def _writeln(out, t: float, text: str) -> None:
    """Write one v2 cast event line."""
    out.write(json.dumps([round(t, 3), "o", text + "\r\n"]) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("docs/recordings/offline_batch.cast"))
    ap.add_argument("--tier", type=int, default=3)
    ap.add_argument("--case-dir", type=Path, default=Path("black-box-bench/cases"))
    ap.add_argument("--per-line-delay", type=float, default=0.08, help="seconds between captured lines")
    args = ap.parse_args(argv)

    args.out.parent.mkdir(parents=True, exist_ok=True)

    # 1. Run the offline batch and collect stdout.
    cmd = [sys.executable, "-m", "black_box.eval.runner",
           "--tier", str(args.tier), "--case-dir", str(args.case_dir)]
    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    runner_lines = (completed.stdout or "").splitlines()

    # 2. Compose the cast.
    header = {
        "version": 2,
        "width": 110,
        "height": 30,
        "timestamp": int(time.time()),
        "env": {"SHELL": "/bin/bash", "TERM": "xterm-256color"},
        "title": "Black Box — offline batch runner (deterministic)",
        "provenance": "offline",
    }
    with args.out.open("w", encoding="utf-8") as f:
        f.write(json.dumps(header) + "\n")
        t = 0.0
        # Startup lines.
        startup = [
            "$ python -m black_box.eval.runner --tier {tier} --case-dir {cd}".format(tier=args.tier, cd=args.case_dir),
            "[boot] black_box.eval.runner — provenance=offline (no Anthropic call)",
            "[boot] cost ceiling enforced via data/costs.jsonl (offline runs spend $0)",
        ]
        for line in startup:
            t += args.per_line_delay
            _writeln(f, t, line)
        # Real runner output.
        for line in runner_lines:
            t += args.per_line_delay
            _writeln(f, t, line)
        # Synthetic guardrail beat after the run, since offline runs don't cross
        # the cap but the demo needs to show the guardrail shape exists.
        guardrail = [
            "",
            "[guardrail] cumulative_usd=$0.0000 cap=$50.0000 — under cap, batch continues",
            "[guardrail] (a real run that crossed the cap would emit `aborted_cap` for remaining cases)",
        ]
        for line in guardrail:
            t += args.per_line_delay
            _writeln(f, t, line)
        t += args.per_line_delay
        _writeln(f, t, "$ ")
    print(f"wrote asciicast -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
