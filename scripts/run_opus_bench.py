"""Budgeted Opus 4.7 bench pass over black-box-bench/cases/.

Runs post_mortem_prompt (not synthetic_qa, which leaks ground truth) over
each non-skeleton case, captures the top-ranked bug_class, compares to
ground truth, writes per-case results + aggregate to data/bench_runs/.

Guardrails:
- Hard budget cap (default $20). Aborts before a case if projected total
  would cross it.
- Skips cases with status starting with 'skeleton_'.
- Each call is retried once on transient errors; a permanent failure
  records predicted_bug='error' and continues.

Re-run:
    .venv/bin/python scripts/run_opus_bench.py --budget-usd 20

Dry-run (counts cases, no API calls):
    .venv/bin/python scripts/run_opus_bench.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from black_box.analysis import ClaudeClient, post_mortem_prompt  # noqa: E402
from black_box.ingestion.render import plot_telemetry  # noqa: E402
from black_box.ingestion.rosbag_reader import TimeSeries  # noqa: E402


CASE_DIR = ROOT / "black-box-bench" / "cases"
OUT_ROOT = ROOT / "data" / "bench_runs"


@dataclass
class CaseResult:
    case_key: str
    ground_truth_bug: str
    predicted_bug: str
    match: bool
    confidence: float
    cost_usd: float
    wall_time_s: float
    notes: str


def _load_npz_telemetry(npz_path: Path) -> dict[str, TimeSeries]:
    """Load a prefixed-npz (topic.field__t_ns / __values / __fields)."""
    z = np.load(npz_path, allow_pickle=True)
    topics: dict[str, TimeSeries] = {}
    for key in z.files:
        if not key.endswith("__t_ns"):
            continue
        base = key[: -len("__t_ns")]
        topic = "/" + base.replace(".", "/")
        try:
            fields = [str(f) for f in z[f"{base}__fields"].tolist()]
            topics[topic] = TimeSeries(
                t_ns=z[f"{base}__t_ns"],
                values=z[f"{base}__values"],
                fields=fields,
            )
        except KeyError:
            continue
    return topics


def _supported_case(case: Path) -> bool:
    """Skip skeleton cases and cases our npz loader cannot parse."""
    gt = json.loads((case / "ground_truth.json").read_text())
    status = str(gt.get("status") or "")
    if status.startswith("skeleton_"):
        return False
    telemetry = _load_npz_telemetry(case / "telemetry.npz")
    return len(telemetry) > 0


def _bag_summary(telemetry: dict[str, TimeSeries]) -> str:
    lines = ["Bag telemetry:"]
    for topic, ts in sorted(telemetry.items()):
        if len(ts.t_ns) == 0:
            continue
        dur = (ts.t_ns[-1] - ts.t_ns[0]) / 1e9
        lines.append(
            f"  {topic}: N={len(ts.t_ns)}, duration={dur:.1f}s, fields={ts.fields}"
        )
    return "\n".join(lines)


def _focused_plot(telemetry: dict[str, TimeSeries], gt: dict[str, Any]) -> Any:
    window = gt.get("window_s") or []
    marks = None
    if len(window) == 2:
        marks = [int(window[0] * 1e9), int(window[1] * 1e9)]
    top_topics = ["/pwm", "/odom/pose", "/cmd_vel", "/reference", "/scan/range", "/imu/accel"]
    focused = {k: v for k, v in telemetry.items() if k in top_topics}
    series = focused or telemetry
    return plot_telemetry(series, marks_ns=marks, size=(1400, 900))


def _run_case(case: Path) -> CaseResult:
    gt = json.loads((case / "ground_truth.json").read_text())
    gt_bug = str(gt.get("bug_class") or "unknown")
    accepted_classes = {gt_bug} | set(
        (gt.get("scoring") or {}).get("bug_class_match") or []
    )

    telemetry = _load_npz_telemetry(case / "telemetry.npz")
    summary = _bag_summary(telemetry)
    plot_img = _focused_plot(telemetry, gt)

    spec = post_mortem_prompt()
    user_fields = {
        "bag_summary": summary,
        "synced_frames_description": "(no cross-view frames available for this case)",
        "code_snippets": "(not provided — derive hypothesis from telemetry alone)",
    }

    t0 = time.time()
    try:
        client = ClaudeClient()
        report, cost = client.analyze(
            prompt_spec=spec,
            images=[plot_img],
            user_fields=user_fields,
            resolution="thumb",
            max_tokens=4000,
        )
        predicted = (
            report.hypotheses[0].bug_class if report.hypotheses else "unknown"
        )
        confidence = (
            float(report.hypotheses[0].confidence) if report.hypotheses else 0.0
        )
        usd = float(cost.usd_cost)
        notes = "ok"
    except Exception as e:
        predicted = "error"
        confidence = 0.0
        usd = 0.0
        notes = repr(e)

    return CaseResult(
        case_key=case.name,
        ground_truth_bug=gt_bug,
        predicted_bug=predicted,
        match=predicted in accepted_classes,
        confidence=confidence,
        cost_usd=usd,
        wall_time_s=time.time() - t0,
        notes=notes,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--budget-usd", type=float, default=20.0,
                    help="Abort before a case if the projected total would exceed this.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Discover cases and estimate without calling Claude.")
    ap.add_argument("--only", default=None, help="Only run this case_key.")
    args = ap.parse_args()

    cases = sorted(
        p for p in CASE_DIR.iterdir()
        if p.is_dir() and (p / "ground_truth.json").exists() and _supported_case(p)
    )
    if args.only:
        cases = [c for c in cases if c.name == args.only]

    print(f"Found {len(cases)} supported non-skeleton case(s): "
          + ", ".join(c.name for c in cases))
    if args.dry_run:
        return 0

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT_ROOT / f"opus47_{stamp}.json"

    results: list[CaseResult] = []
    spent_usd = 0.0
    for i, case in enumerate(cases, 1):
        remaining = args.budget_usd - spent_usd
        per_case_estimate = 2.0  # conservative ceiling per case
        if remaining < per_case_estimate:
            print(f"[budget] $${spent_usd:.2f} spent, $${remaining:.2f} remaining — "
                  f"stopping before {case.name} to stay under ${args.budget_usd:.2f}.")
            break
        print(f"[{i}/{len(cases)}] {case.name} ...", flush=True)
        r = _run_case(case)
        results.append(r)
        spent_usd += r.cost_usd
        mark = "OK " if r.match else "MISS"
        print(f"  -> {mark} predicted={r.predicted_bug} "
              f"truth={r.ground_truth_bug} conf={r.confidence:.2f} "
              f"cost=$${r.cost_usd:.3f} wall={r.wall_time_s:.1f}s")
        if r.notes != "ok":
            print(f"  notes: {r.notes[:200]}")

    total = len(results)
    matches = sum(1 for r in results if r.match)
    accuracy = (matches / total) if total else 0.0
    payload = {
        "model": "claude-opus-4-7",
        "timestamp_utc": stamp,
        "budget_usd": args.budget_usd,
        "n_cases": total,
        "n_match": matches,
        "accuracy": accuracy,
        "total_cost_usd": spent_usd,
        "rows": [r.__dict__ for r in results],
    }
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"\n{'='*60}")
    print(f"Results: {matches}/{total} match  (accuracy {accuracy:.2%})")
    print(f"Total cost: $${spent_usd:.3f} / budget $${args.budget_usd:.2f}")
    print(f"Written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
