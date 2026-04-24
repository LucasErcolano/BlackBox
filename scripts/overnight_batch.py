"""Overnight batch runner for black-box-bench cases.

Iterates every case in ``black-box-bench/cases/`` (synthetic + skeleton
stubs), streams per-case progress to stdout, writes per-case JSON +
per-run manifest + an end-of-run table under
``data/bench_runs/batch_<date>[_suffix]/``.

Two modes:
  --dry-run        Stub predictor that echoes ground truth. Zero API $.
                   Use this to prove the plumbing works before burning
                   real budget. Output table + manifest are real-shape.
  (live, default)  Real ``post_mortem_prompt`` on Opus 4.7 per
                   ``scripts/run_opus_bench.py`` semantics. Budget-gated.

Budget guardrail:
  Before each case, the script reads ``data/costs.jsonl`` and checks
  cumulative ``usd_cost`` against ``--budget-usd`` (default $50). If the
  floor (cumulative + per-case ceiling) would cross the cap, the run
  aborts cleanly — writes the partial manifest, flags the remaining
  cases as ``skipped_budget``, and exits 0.

End-of-run table columns (per issue #25):
  case | wall-s | $ | bug_class_match | top-hyp confidence

Re-run:
  PYTHONPATH=src python scripts/overnight_batch.py --dry-run
  PYTHONPATH=src python scripts/overnight_batch.py --budget-usd 50
  PYTHONPATH=src python scripts/overnight_batch.py --only pid_saturation_01
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "black-box-bench" / "cases"
COSTS_PATH = ROOT / "data" / "costs.jsonl"
OUT_ROOT = ROOT / "data" / "bench_runs"

PER_CASE_USD_CEILING = 2.0  # conservative ceiling used by the budget gate
DEFAULT_BUDGET_USD = 50.0


# ---------------------------------------------------------------------------
# Row schema
# ---------------------------------------------------------------------------
@dataclass
class CaseRow:
    case_key: str
    ground_truth_bug: str
    predicted_bug: str
    bug_class_match: bool
    confidence: float
    cost_usd: float
    wall_time_s: float
    status: str  # "ok" | "skeleton" | "error" | "skipped_budget"
    source: str  # "stub" | "claude" | "skipped"
    notes: str = ""

    def table_row(self) -> dict[str, str]:
        return {
            "case": self.case_key,
            "wall-s": f"{self.wall_time_s:.1f}",
            "$": f"{self.cost_usd:.3f}",
            "bug_class_match": "OK" if self.bug_class_match else (
                "SKIP" if self.status != "ok" else "MISS"
            ),
            "top-hyp confidence": f"{self.confidence:.2f}",
        }


@dataclass
class BatchManifest:
    batch_id: str
    mode: str  # "dry-run" | "live"
    model: str
    started_utc: str
    finished_utc: str | None = None
    budget_usd: float = DEFAULT_BUDGET_USD
    baseline_cost_usd: float = 0.0
    spent_usd: float = 0.0
    n_cases: int = 0
    n_match: int = 0
    rows: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Budget guardrail — read data/costs.jsonl
# ---------------------------------------------------------------------------
def cumulative_cost_usd(costs_path: Path = COSTS_PATH) -> float:
    """Sum every ``usd_cost`` line in costs.jsonl. Missing file -> 0.0."""
    if not costs_path.exists():
        return 0.0
    total = 0.0
    for line in costs_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            total += float(entry.get("usd_cost") or 0.0)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return total


# ---------------------------------------------------------------------------
# Case discovery — synthetic + skeleton
# ---------------------------------------------------------------------------
def discover_cases(case_dir: Path, only: str | None = None) -> list[Path]:
    if not case_dir.exists():
        return []
    cases = sorted(
        p for p in case_dir.iterdir()
        if p.is_dir() and (p / "ground_truth.json").exists()
    )
    if only:
        cases = [c for c in cases if c.name == only]
    return cases


def load_gt(case: Path) -> dict[str, Any]:
    return json.loads((case / "ground_truth.json").read_text())


def gt_bug_class(gt: dict[str, Any]) -> str:
    return str(gt.get("bug_class") or gt.get("bug_id") or "unknown")


def gt_accepted_classes(gt: dict[str, Any]) -> set[str]:
    primary = gt_bug_class(gt)
    scoring = gt.get("scoring") or {}
    alts = scoring.get("bug_class_match") or []
    out = {primary} if primary and primary != "unknown" else set()
    for a in alts:
        if isinstance(a, str):
            out.add(a)
    return out


def is_skeleton(gt: dict[str, Any]) -> bool:
    return str(gt.get("status") or "").startswith("skeleton")


# ---------------------------------------------------------------------------
# Predictors
# ---------------------------------------------------------------------------
def stub_predict(case: Path, gt: dict[str, Any]) -> CaseRow:
    """Dry-run stub: synthetic cases echo ground truth at mid confidence.

    Skeleton cases (no bag yet) stay ``unknown`` with a 0.0 confidence,
    so the table honestly shows them as ``SKIP`` rather than a fake
    match.
    """
    gt_bug = gt_bug_class(gt)
    accepted = gt_accepted_classes(gt)
    skeleton = is_skeleton(gt)

    if skeleton:
        return CaseRow(
            case_key=case.name,
            ground_truth_bug=gt_bug,
            predicted_bug="unknown",
            bug_class_match=False,
            confidence=0.0,
            cost_usd=0.0,
            wall_time_s=0.0,
            status="skeleton",
            source="stub",
            notes="skeleton_awaiting_bag",
        )

    # Synthetic case: stub "predicts" the ground truth with a fixed
    # mid-band confidence (0.77 matches the shape of real Opus runs).
    predicted = gt_bug
    return CaseRow(
        case_key=case.name,
        ground_truth_bug=gt_bug,
        predicted_bug=predicted,
        bug_class_match=predicted in accepted,
        confidence=0.77,
        cost_usd=0.0,
        wall_time_s=0.0,
        status="ok",
        source="stub",
        notes="dry-run: stub predictor echoed ground truth",
    )


def claude_predict(case: Path, gt: dict[str, Any]) -> CaseRow:
    """Real Opus 4.7 post_mortem pass.

    Lifted from ``scripts/run_opus_bench.py`` semantics so the same
    telemetry-only prompt is used. Soft-imports so --dry-run works in
    envs without numpy / SDK.
    """
    gt_bug = gt_bug_class(gt)
    accepted = gt_accepted_classes(gt)
    skeleton = is_skeleton(gt)

    if skeleton:
        return CaseRow(
            case_key=case.name,
            ground_truth_bug=gt_bug,
            predicted_bug="unknown",
            bug_class_match=False,
            confidence=0.0,
            cost_usd=0.0,
            wall_time_s=0.0,
            status="skeleton",
            source="skipped",
            notes="skeleton_awaiting_bag — live run cannot score without a bag",
        )

    try:
        import numpy as np  # type: ignore
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(ROOT / ".env")
        sys.path.insert(0, str(ROOT / "src"))
        from black_box.analysis import ClaudeClient, post_mortem_prompt  # type: ignore
        from black_box.ingestion.render import plot_telemetry  # type: ignore
        from black_box.ingestion.rosbag_reader import TimeSeries  # type: ignore
    except Exception as e:
        return CaseRow(
            case_key=case.name,
            ground_truth_bug=gt_bug,
            predicted_bug="error",
            bug_class_match=False,
            confidence=0.0,
            cost_usd=0.0,
            wall_time_s=0.0,
            status="error",
            source="claude",
            notes=f"import_error:{e!r}",
        )

    # Load telemetry with the same prefixed-npz convention used by
    # scripts/run_opus_bench.py. Cases whose npz layout the loader can't
    # parse (e.g. rtk_heading_break_01) are flagged but not fatal.
    telemetry: dict[str, Any] = {}
    try:
        z = np.load(case / "telemetry.npz", allow_pickle=True)
        for key in z.files:
            if not key.endswith("__t_ns"):
                continue
            base = key[: -len("__t_ns")]
            topic = "/" + base.replace(".", "/")
            try:
                fields = [str(f) for f in z[f"{base}__fields"].tolist()]
                telemetry[topic] = TimeSeries(
                    t_ns=z[f"{base}__t_ns"],
                    values=z[f"{base}__values"],
                    fields=fields,
                )
            except KeyError:
                continue
    except Exception as e:
        return CaseRow(
            case_key=case.name,
            ground_truth_bug=gt_bug,
            predicted_bug="error",
            bug_class_match=False,
            confidence=0.0,
            cost_usd=0.0,
            wall_time_s=0.0,
            status="error",
            source="claude",
            notes=f"telemetry_load_failed:{e!r}",
        )

    if not telemetry:
        return CaseRow(
            case_key=case.name,
            ground_truth_bug=gt_bug,
            predicted_bug="unknown",
            bug_class_match=False,
            confidence=0.0,
            cost_usd=0.0,
            wall_time_s=0.0,
            status="error",
            source="claude",
            notes="telemetry empty or npz schema mismatch",
        )

    window = gt.get("window_s") or []
    marks = None
    if len(window) == 2 and all(isinstance(x, (int, float)) for x in window):
        marks = [int(window[0] * 1e9), int(window[1] * 1e9)]
    top_topics = {
        "/pwm", "/odom/pose", "/cmd_vel", "/reference",
        "/scan/range", "/imu/accel",
    }
    focused = {k: v for k, v in telemetry.items() if k in top_topics} or telemetry

    summary_lines = ["Bag telemetry:"]
    for topic, ts in sorted(telemetry.items()):
        if len(ts.t_ns) == 0:
            continue
        dur = (ts.t_ns[-1] - ts.t_ns[0]) / 1e9
        summary_lines.append(
            f"  {topic}: N={len(ts.t_ns)}, duration={dur:.1f}s, fields={ts.fields}"
        )
    summary = "\n".join(summary_lines)

    t0 = time.time()
    try:
        plot_img = plot_telemetry(focused, marks_ns=marks, size=(1400, 900))
        spec = post_mortem_prompt()
        client = ClaudeClient()
        report, cost = client.analyze(
            prompt_spec=spec,
            images=[plot_img],
            user_fields={
                "bag_summary": summary,
                "synced_frames_description": "(no cross-view frames available)",
                "code_snippets": "(not provided — derive hypothesis from telemetry alone)",
            },
            resolution="thumb",
            max_tokens=4000,
        )
        predicted = report.hypotheses[0].bug_class if report.hypotheses else "unknown"
        confidence = float(report.hypotheses[0].confidence) if report.hypotheses else 0.0
        usd = float(cost.usd_cost)
        status = "ok"
        notes = "ok"
    except Exception as e:
        predicted = "error"
        confidence = 0.0
        usd = 0.0
        status = "error"
        notes = repr(e)

    return CaseRow(
        case_key=case.name,
        ground_truth_bug=gt_bug,
        predicted_bug=predicted,
        bug_class_match=predicted in accepted,
        confidence=confidence,
        cost_usd=usd,
        wall_time_s=time.time() - t0,
        status=status,
        source="claude",
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Table rendering
# ---------------------------------------------------------------------------
TABLE_HEADERS = ["case", "wall-s", "$", "bug_class_match", "top-hyp confidence"]


def render_table(rows: list[CaseRow]) -> str:
    if not rows:
        return "(no cases)"
    data = [r.table_row() for r in rows]
    widths = {
        h: max(len(h), *(len(r[h]) for r in data))
        for h in TABLE_HEADERS
    }
    lines = [
        " | ".join(h.ljust(widths[h]) for h in TABLE_HEADERS),
        "-+-".join("-" * widths[h] for h in TABLE_HEADERS),
    ]
    for r in data:
        lines.append(" | ".join(r[h].ljust(widths[h]) for h in TABLE_HEADERS))
    return "\n".join(lines)


def render_markdown_table(rows: list[CaseRow]) -> str:
    if not rows:
        return "(no cases)"
    out = [
        "| case | wall-s | $ | bug_class_match | top-hyp confidence |",
        "|---|---:|---:|:---:|---:|",
    ]
    for r in rows:
        tr = r.table_row()
        out.append(
            f"| {tr['case']} | {tr['wall-s']} | {tr['$']} | "
            f"{tr['bug_class_match']} | {tr['top-hyp confidence']} |"
        )
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", "--offline", dest="dry_run", action="store_true",
                    help="Stub predictor, no API calls. Produces real-shape table/manifest.")
    ap.add_argument("--budget-usd", type=float, default=DEFAULT_BUDGET_USD,
                    help=f"Abort before a case if cumulative data/costs.jsonl + per-case "
                         f"ceiling would cross this. Default: ${DEFAULT_BUDGET_USD:.0f}.")
    ap.add_argument("--case-dir", type=Path, default=CASE_DIR,
                    help="Case directory. Default: black-box-bench/cases/.")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="Override output directory. Default: data/bench_runs/batch_<date>[_dryrun]/")
    ap.add_argument("--only", default=None, help="Run a single case by key.")
    ap.add_argument("--suffix", default=None,
                    help="Extra suffix on the batch directory (e.g. 'v2').")
    args = ap.parse_args(argv)

    cases = discover_cases(args.case_dir, only=args.only)
    if not cases:
        print(f"no cases found under {args.case_dir}", file=sys.stderr)
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    mode = "dry-run" if args.dry_run else "live"
    suffix_parts = []
    if args.dry_run:
        suffix_parts.append("dryrun")
    if args.suffix:
        suffix_parts.append(args.suffix)
    dir_name = f"batch_{stamp}"
    if suffix_parts:
        dir_name += "_" + "_".join(suffix_parts)
    out_dir = args.out_dir or (OUT_ROOT / dir_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Keep batch_id in sync with the actual output dir so an explicit
    # --out-dir override doesn't leave the manifest pointing at a
    # different name.
    batch_id = out_dir.name

    baseline = cumulative_cost_usd(COSTS_PATH)
    manifest = BatchManifest(
        batch_id=batch_id,
        mode=mode,
        model="claude-opus-4-7",
        started_utc=datetime.now(timezone.utc).isoformat(),
        budget_usd=args.budget_usd,
        baseline_cost_usd=baseline,
    )

    print(f"=== overnight batch ===")
    print(f"mode      : {mode}")
    print(f"cases     : {len(cases)} from {args.case_dir}")
    print(f"budget    : ${args.budget_usd:.2f} (cumulative data/costs.jsonl = ${baseline:.3f})")
    print(f"output    : {out_dir}")
    print(f"batch id  : {batch_id}")
    print()

    rows: list[CaseRow] = []
    spent = 0.0
    budget_exhausted = False

    for i, case in enumerate(cases, 1):
        gt = load_gt(case)

        # Budget gate — only bite in live mode. Dry-run is zero-cost.
        if not args.dry_run:
            projected = baseline + spent + PER_CASE_USD_CEILING
            if projected > args.budget_usd:
                budget_exhausted = True
                remaining = args.budget_usd - (baseline + spent)
                print(f"[{i}/{len(cases)}] {case.name} -- SKIPPED (budget): "
                      f"baseline ${baseline:.3f} + spent ${spent:.3f} + ceiling "
                      f"${PER_CASE_USD_CEILING:.2f} > ${args.budget_usd:.2f} "
                      f"(remaining ${remaining:.3f})",
                      flush=True)
                rows.append(CaseRow(
                    case_key=case.name,
                    ground_truth_bug=gt_bug_class(gt),
                    predicted_bug="skipped",
                    bug_class_match=False,
                    confidence=0.0,
                    cost_usd=0.0,
                    wall_time_s=0.0,
                    status="skipped_budget",
                    source="skipped",
                    notes=f"budget gate: ${args.budget_usd:.2f} cap",
                ))
                continue

        print(f"[{i}/{len(cases)}] {case.name} ...", flush=True)
        predict = stub_predict if args.dry_run else claude_predict
        row = predict(case, gt)
        rows.append(row)
        spent += row.cost_usd

        # Stream a one-liner per case.
        mark = {
            "ok": "OK  " if row.bug_class_match else "MISS",
            "skeleton": "SKEL",
            "error": "ERR ",
            "skipped_budget": "SKIP",
        }.get(row.status, "??  ")
        print(f"  -> {mark} predicted={row.predicted_bug} "
              f"truth={row.ground_truth_bug} conf={row.confidence:.2f} "
              f"cost=${row.cost_usd:.3f} wall={row.wall_time_s:.1f}s",
              flush=True)
        if row.notes and row.notes != "ok":
            print(f"     notes: {row.notes[:200]}", flush=True)

        # Persist per-case JSON immediately so a crash keeps partials.
        (out_dir / f"{case.name}.json").write_text(
            json.dumps(asdict(row), indent=2)
        )

    manifest.finished_utc = datetime.now(timezone.utc).isoformat()
    manifest.spent_usd = spent
    manifest.n_cases = len(rows)
    manifest.n_match = sum(1 for r in rows if r.bug_class_match)
    manifest.rows = [asdict(r) for r in rows]

    # Write manifest + table artifacts.
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(asdict(manifest), indent=2))

    table_txt = render_table(rows)
    (out_dir / "table.txt").write_text(table_txt + "\n")

    md_rows = render_markdown_table(rows)
    summary_md = (
        f"# Overnight batch: {batch_id}\n\n"
        f"- mode: `{mode}`\n"
        f"- model: `{manifest.model}`\n"
        f"- started: {manifest.started_utc}\n"
        f"- finished: {manifest.finished_utc}\n"
        f"- budget: ${args.budget_usd:.2f} (baseline cumulative ${baseline:.3f}, "
        f"spent this run ${spent:.3f})\n"
        f"- cases: {manifest.n_cases}, matches: {manifest.n_match}\n"
        + ("- status: BUDGET EXHAUSTED, some cases skipped\n" if budget_exhausted else "")
        + "\n## Table\n\n"
        + md_rows
        + "\n"
    )
    (out_dir / "table.md").write_text(summary_md)

    print()
    print(table_txt)
    print()
    print(f"cases       : {manifest.n_cases}")
    print(f"matches     : {manifest.n_match}")
    print(f"spent       : ${spent:.3f} / ${args.budget_usd:.2f}")
    print(f"manifest    : {manifest_path}")
    print(f"table (txt) : {out_dir / 'table.txt'}")
    print(f"table (md)  : {out_dir / 'table.md'}")

    if budget_exhausted:
        print()
        print("one or more cases were skipped by the budget gate — see manifest.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
