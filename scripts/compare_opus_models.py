# SPDX-License-Identifier: MIT
"""A/B harness: same cases, same prompts, two models, K seeds per case.

Captures, per (model, case, seed):
    - bug_class match vs ground_truth.json
    - patch_target match — file basename, terminal function name, AND of both
    - confidence (top-1)
    - evidence_count (unique (source, topic_or_file) tuples)
    - tool_error (notes != "ok")
    - cost_usd, wall_time_s

Per (model, case) across seeds:
    - flip_rate — fraction of seed pairs whose top-1 bug_class disagrees

Per model aggregate:
    - bug_match_rate (mean) + stderr
    - pt_file_rate, pt_function_rate, pt_both_rate
    - brier_score = mean((confidence - match)^2)
    - mean_evidence_count, tool_error_count
    - total_cost_usd, total_wall_time_s
    - usd_per_correct, wall_per_correct (Inf if zero correct)

Re-run::

    .venv/bin/python scripts/compare_opus_models.py \\
        --models claude-opus-4-6 claude-opus-4-7 \\
        --seeds 3 --temperature 1.0 --budget-usd 6 \\
        --cases bad_gain_01,pid_saturation_01,sensor_timeout_01

Dry-run::

    .venv/bin/python scripts/compare_opus_models.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, dataclass, field
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

DEFAULT_MODELS = ["claude-opus-4-6", "claude-opus-4-7"]
# Empty default = all supported non-skeleton cases under black-box-bench/cases/.
DEFAULT_CASES: list[str] = []

# Tier B: false-operator injection. Map case_key -> deliberately wrong operator
# claim. Used when --operator-mode=false to test how much each model resists
# a misleading prior. None entries: skip injection.
FALSE_OPERATOR_BY_CASE: dict[str, str] = {
    "bad_gain_01": "Operator believes the IMU is broken — the wheel oscillation must be a bad accelerometer.",
    "pid_saturation_01": "Operator believes a wheel-encoder cable is loose, not a controller issue.",
    "sensor_timeout_01": "Operator believes the controller gain was bumped too high yesterday.",
    "rtk_heading_break_01": "Operator believes a tunnel passage corrupted GPS for the whole drive.",
}

# Confidence threshold below which a hypothesis counts as effective abstention.
ABSTENTION_CONFIDENCE_THRESHOLD = 0.30

# Tokens that count as a refutation of the operator's hypothesis. Substring,
# case-insensitive. Generous on purpose — both models compete under the same
# rule.
REFUTATION_KEYWORDS = [
    # session-wide / time scope
    "session-wide", "session wide", "entire session", "whole session",
    "throughout the session", "throughout the bag", "entire bag",
    "across the entire", "for all samples", "every sample", "all samples",
    "from start", "from the start", "from the beginning",
    # pre-tunnel / temporal refutation
    "pre-existing", "preexisting", "predates", "predate",
    "before the tunnel", "before tunnel", "pre-tunnel", "prior to tunnel",
    "prior to the tunnel", "before entering", "before reaching",
    "independent of tunnel", "independent of the tunnel",
    "regardless of tunnel", "regardless of the tunnel",
    # explicit refutation phrasing
    "not the tunnel", "not caused by the tunnel", "not caused by tunnel",
    "tunnel did not", "tunnel is not", "tunnel does not",
    "rule out the tunnel", "rules out the tunnel", "ruled out the tunnel",
    "reject the tunnel", "rejects the tunnel", "rule out tunnel",
    "operator hypothesis is wrong", "operator's hypothesis is wrong",
    "operator narrative", "operator report is", "operator report does not",
    "contradicts the operator", "contradict the operator",
    "disagree with the operator", "disagrees with the operator",
    # RTK technical signals that imply refutation
    "carr_soln=none", "carr=none", "carr_none",
    "carrier-phase never", "never produced carrier-phase",
    "carrier phase never", "no carrier-phase", "no carrier phase",
    "moving-base", "moving base", "navrelposned", "rel_pos_valid",
    "flags_rel_pos_valid", "rxm-sfrbx", "rxm-rawx", "rtcm",
    "dual-antenna", "dual antenna", "heading subsystem",
    "rover never", "never set", "always 0", "always zero",
]


@dataclass
class CaseSeedResult:
    case_key: str
    model: str
    seed: int
    ground_truth_bug: str
    predicted_bug: str
    bug_match: bool
    patch_target_file: str
    patch_target_function: str
    pt_file_match: bool
    pt_function_match: bool
    pt_both_match: bool
    confidence: float
    evidence_count: int
    tool_error: bool
    cost_usd: float
    wall_time_s: float
    notes: str
    has_operator_hypothesis: bool = False
    refutes_operator: bool = False
    report_text_excerpt: str = ""
    operator_mode: str = "none"
    is_under_specified: bool = False
    abstained: bool = False


@dataclass
class ModelAggregate:
    model: str
    n_runs: int
    n_cases: int
    seeds: int
    bug_match_count: int
    bug_match_rate: float
    bug_match_stderr: float
    pt_file_rate: float
    pt_function_rate: float
    pt_both_rate: float
    mean_confidence: float
    brier_score: float
    mean_evidence_count: float
    tool_error_count: int
    mean_flip_rate: float
    n_refutation_runs: int
    refutation_rate: float
    n_under_specified_runs: int
    abstention_correctness: float
    n_solvable_runs: int
    solvable_accuracy: float
    operator_mode: str
    total_cost_usd: float
    total_wall_time_s: float
    usd_per_correct: float
    wall_per_correct: float
    rows: list[dict] = field(default_factory=list)


def _load_npz_telemetry(npz_path: Path) -> dict[str, TimeSeries]:
    """Dual-schema loader (prefixed double-underscore + flat single-underscore).

    Mirrors ``scripts/overnight_batch.load_telemetry_npz`` so cases like
    ``rtk_heading_break_01`` (flat schema) participate in the A/B harness.
    """
    z = np.load(npz_path, allow_pickle=True)
    keys = list(z.files)
    topics: dict[str, TimeSeries] = {}
    for key in keys:
        if key.endswith("__t_ns"):
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
        elif key.endswith("_t_ns"):
            base = key[: -len("_t_ns")]
            if not base:
                continue
            t_ns = z[key]
            siblings = [
                k for k in keys
                if k != key and k.startswith(base + "_") and not k.endswith("_t_ns")
            ]
            if not siblings:
                continue
            fields_list: list[str] = []
            cols: list[Any] = []
            for sk in sorted(siblings):
                arr = z[sk]
                if arr.ndim != 1 or arr.shape[0] != t_ns.shape[0]:
                    continue
                fields_list.append(sk[len(base) + 1 :])
                cols.append(arr)
            if not cols:
                continue
            values = np.column_stack(cols) if len(cols) > 1 else cols[0]
            topic = "/" + base.replace("_", "/")
            topics[topic] = TimeSeries(t_ns=t_ns, values=values, fields=fields_list)
    return topics


def _supported_case(case: Path) -> bool:
    gt = json.loads((case / "ground_truth.json").read_text())
    if str(gt.get("status") or "").startswith("skeleton_"):
        return False
    return len(_load_npz_telemetry(case / "telemetry.npz")) > 0


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
    top = ["/pwm", "/odom/pose", "/cmd_vel", "/reference", "/scan/range", "/imu/accel"]
    focused = {k: v for k, v in telemetry.items() if k in top}
    return plot_telemetry(focused or telemetry, marks_ns=marks, size=(1400, 900))


def _patch_target_breakdown(
    patch_proposal: str, gt_target: dict[str, Any]
) -> tuple[bool, bool, bool]:
    """Return (file_match, function_match, both_match) — substring rule per piece."""
    if not patch_proposal or not gt_target:
        return False, False, False
    text = patch_proposal.lower()
    file_ = str(gt_target.get("file") or "").lower()
    func = str(gt_target.get("function") or "").lower()
    file_basename = Path(file_).name if file_ else ""
    file_hit = bool(file_basename) and file_basename in text
    func_terminal = func.split(".")[-1] if func else ""
    func_hit = bool(func_terminal) and func_terminal in text
    return file_hit, func_hit, (file_hit and func_hit)


# Back-compat alias used by existing tests.
def _patch_target_match(patch_proposal: str, gt_target: dict[str, Any]) -> bool:
    f, fn, _ = _patch_target_breakdown(patch_proposal, gt_target)
    return f or fn


def _is_under_specified(gt: dict[str, Any]) -> bool:
    """A case is under-specified when the closed taxonomy can't cleanly tag it.

    Heuristics, in order:
      1. Explicit override: ``gt.under_specified == true``.
      2. Scoring rationale mentions "no exact slot" / "no exact match".
      3. ``scoring.bug_class_match`` lists more than one accepted class —
         taxonomy is ambiguous for this case.
    """
    if gt.get("under_specified") is True:
        return True
    rationale = str((gt.get("scoring") or {}).get("bug_class_rationale") or "").lower()
    if "no exact slot" in rationale or "no exact match" in rationale:
        return True
    accepted = (gt.get("scoring") or {}).get("bug_class_match") or []
    return len(accepted) > 1


def _operator_hypothesis(gt: dict[str, Any]) -> str | None:
    """Extract operator narrative if the case is set up for refutation testing."""
    anti = gt.get("anti_hypothesis") or {}
    op_text = anti.get("operator_report") or gt.get("operator_narrative")
    if not op_text:
        return None
    if not (gt.get("refutes_operator") or anti):
        return None
    return str(op_text)


def _scores_refutation(report_text: str, operator_hypothesis: str) -> bool:
    """Substring rule — text mentions any refutation keyword (case-insensitive)."""
    if not report_text or not operator_hypothesis:
        return False
    text = report_text.lower()
    return any(kw in text for kw in REFUTATION_KEYWORDS)


def _flip_rate(predictions: list[str]) -> float:
    """Fraction of unordered pairs whose top-1 bug_class disagrees."""
    n = len(predictions)
    if n < 2:
        return 0.0
    pairs = n * (n - 1) // 2
    disagree = 0
    for i in range(n):
        for j in range(i + 1, n):
            if predictions[i] != predictions[j]:
                disagree += 1
    return disagree / pairs


def _resolve_operator_text(case_key: str, gt: dict[str, Any], mode: str) -> str | None:
    """Return operator text to inject given mode. None = no injection."""
    if mode == "none":
        return None
    if mode == "native":
        return _operator_hypothesis(gt)
    if mode == "false":
        return FALSE_OPERATOR_BY_CASE.get(case_key)
    raise ValueError(f"unknown operator-mode: {mode}")


def _run_case_seed(
    case: Path, model: str, seed: int, temperature: float,
    apply_grounding: bool = True,
    operator_mode: str = "none",
) -> CaseSeedResult:
    gt = json.loads((case / "ground_truth.json").read_text())
    gt_bug = str(gt.get("bug_class") or "unknown")
    accepted = {gt_bug} | set((gt.get("scoring") or {}).get("bug_class_match") or [])
    gt_target = gt.get("patch_target") or {}

    telemetry = _load_npz_telemetry(case / "telemetry.npz")
    summary = _bag_summary(telemetry)
    plot_img = _focused_plot(telemetry, gt)

    operator_text = _resolve_operator_text(case.name, gt, operator_mode)
    if operator_text:
        summary = (
            f"Operator report (UNTRUSTED — verify against telemetry):\n"
            f"  {operator_text}\n"
            f"You must agree, refine, or refute this report based on evidence. "
            f"Do not confirm it without cross-source support.\n\n"
            + summary
        )
    under_specified = _is_under_specified(gt)

    spec = post_mortem_prompt()
    user_fields = {
        "bag_summary": summary,
        "synced_frames_description": "(no cross-view frames available for this case)",
        "code_snippets": "(not provided — derive hypothesis from telemetry alone)",
    }

    t0 = time.time()
    predicted = "error"
    confidence = 0.0
    evidence_count = 0
    pt_file = pt_func = pt_both = False
    refutes = False
    report_excerpt = ""
    usd = 0.0
    notes = "ok"
    try:
        client = ClaudeClient(model=model)
        report, cost = client.analyze(
            prompt_spec=spec,
            images=[plot_img],
            user_fields=user_fields,
            resolution="thumb",
            max_tokens=4000,
            temperature=temperature,
            apply_grounding=apply_grounding,
        )
        if report.hypotheses:
            predicted = report.hypotheses[0].bug_class
            confidence = float(report.hypotheses[0].confidence)
        sources: set[tuple[str, str]] = set()
        for h in report.hypotheses:
            for ev in h.evidence:
                sources.add((ev.source, ev.topic_or_file))
        evidence_count = len(sources)
        pt_file, pt_func, pt_both = _patch_target_breakdown(
            report.patch_proposal or "", gt_target
        )
        full_text = (report.patch_proposal or "") + "\n" + "\n".join(
            h.summary for h in report.hypotheses
        )
        # Also fold timeline labels — they often carry the refutation phrasing.
        full_text += "\n" + "\n".join(
            getattr(t, "label", "") for t in (report.timeline or [])
        )
        if operator_text:
            refutes = _scores_refutation(full_text, operator_text)
        report_excerpt = full_text[:1200]
        usd = float(cost.usd_cost)
    except Exception as e:
        notes = repr(e)[:400]

    abstained = (predicted == "error") or (
        evidence_count == 0 and confidence < ABSTENTION_CONFIDENCE_THRESHOLD
    ) or (confidence < ABSTENTION_CONFIDENCE_THRESHOLD and notes == "ok")

    return CaseSeedResult(
        case_key=case.name,
        model=model,
        seed=seed,
        ground_truth_bug=gt_bug,
        predicted_bug=predicted,
        bug_match=predicted in accepted,
        patch_target_file=str(gt_target.get("file") or ""),
        patch_target_function=str(gt_target.get("function") or ""),
        pt_file_match=pt_file,
        pt_function_match=pt_func,
        pt_both_match=pt_both,
        confidence=confidence,
        evidence_count=evidence_count,
        tool_error=notes != "ok",
        cost_usd=usd,
        wall_time_s=time.time() - t0,
        notes=notes,
        has_operator_hypothesis=bool(operator_text),
        refutes_operator=refutes,
        report_text_excerpt=report_excerpt,
        operator_mode=operator_mode,
        is_under_specified=under_specified,
        abstained=abstained,
    )


def _aggregate(
    model: str, results: list[CaseSeedResult], seeds: int,
    operator_mode: str = "none",
) -> ModelAggregate:
    n = len(results)
    if n == 0:
        return ModelAggregate(
            model=model, n_runs=0, n_cases=0, seeds=seeds,
            bug_match_count=0, bug_match_rate=0.0, bug_match_stderr=0.0,
            pt_file_rate=0.0, pt_function_rate=0.0, pt_both_rate=0.0,
            mean_confidence=0.0, brier_score=0.0, mean_evidence_count=0.0,
            tool_error_count=0, mean_flip_rate=0.0,
            n_refutation_runs=0, refutation_rate=0.0,
            n_under_specified_runs=0, abstention_correctness=0.0,
            n_solvable_runs=0, solvable_accuracy=0.0,
            operator_mode=operator_mode,
            total_cost_usd=0.0, total_wall_time_s=0.0,
            usd_per_correct=math.inf, wall_per_correct=math.inf,
        )
    matches = [int(r.bug_match) for r in results]
    bug_count = sum(matches)
    rate = bug_count / n
    var = (sum((m - rate) ** 2 for m in matches) / n) if n else 0.0
    stderr = math.sqrt(var / n)
    pt_file = sum(1 for r in results if r.pt_file_match) / n
    pt_func = sum(1 for r in results if r.pt_function_match) / n
    pt_both = sum(1 for r in results if r.pt_both_match) / n
    brier = sum((r.confidence - int(r.bug_match)) ** 2 for r in results) / n
    ev_mean = sum(r.evidence_count for r in results) / n
    err_count = sum(1 for r in results if r.tool_error)
    conf_mean = sum(r.confidence for r in results) / n
    total_cost = sum(r.cost_usd for r in results)
    total_wall = sum(r.wall_time_s for r in results)

    by_case: dict[str, list[str]] = {}
    for r in results:
        by_case.setdefault(r.case_key, []).append(r.predicted_bug)
    flip_rates = [_flip_rate(preds) for preds in by_case.values()]
    mean_flip = (sum(flip_rates) / len(flip_rates)) if flip_rates else 0.0

    usd_per_correct = (total_cost / bug_count) if bug_count else math.inf
    wall_per_correct = (total_wall / bug_count) if bug_count else math.inf

    refute_runs = [r for r in results if r.has_operator_hypothesis]
    n_refute = len(refute_runs)
    refute_rate = (sum(1 for r in refute_runs if r.refutes_operator) / n_refute) if n_refute else 0.0

    under_runs = [r for r in results if r.is_under_specified]
    n_under = len(under_runs)
    abstention_correct = (sum(1 for r in under_runs if r.abstained) / n_under) if n_under else 0.0

    solvable_runs = [r for r in results if not r.is_under_specified]
    n_solv = len(solvable_runs)
    solvable_acc = (sum(1 for r in solvable_runs if r.bug_match) / n_solv) if n_solv else 0.0

    return ModelAggregate(
        model=model,
        n_runs=n,
        n_cases=len(by_case),
        seeds=seeds,
        bug_match_count=bug_count,
        bug_match_rate=rate,
        bug_match_stderr=stderr,
        pt_file_rate=pt_file,
        pt_function_rate=pt_func,
        pt_both_rate=pt_both,
        mean_confidence=conf_mean,
        brier_score=brier,
        mean_evidence_count=ev_mean,
        tool_error_count=err_count,
        mean_flip_rate=mean_flip,
        n_refutation_runs=n_refute,
        refutation_rate=refute_rate,
        n_under_specified_runs=n_under,
        abstention_correctness=abstention_correct,
        n_solvable_runs=n_solv,
        solvable_accuracy=solvable_acc,
        operator_mode=operator_mode,
        total_cost_usd=total_cost,
        total_wall_time_s=total_wall,
        usd_per_correct=usd_per_correct,
        wall_per_correct=wall_per_correct,
        rows=[asdict(r) for r in results],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--cases", default=",".join(DEFAULT_CASES),
                    help="Comma-separated case keys. Empty = all supported non-skeleton.")
    ap.add_argument("--seeds", type=int, default=3,
                    help="Repeats per (model, case). >=2 enables variance + flip-rate.")
    ap.add_argument("--temperature", type=float, default=1.0,
                    help="Sampling temperature passed to Anthropic API.")
    ap.add_argument("--budget-usd", type=float, default=6.0,
                    help="Hard cap across all calls.")
    ap.add_argument("--no-grounding", action="store_true",
                    help="Disable post-hoc grounding gate to isolate raw model behavior.")
    ap.add_argument("--operator-mode", choices=["none", "native", "false"], default="none",
                    help="Operator hypothesis injection. "
                         "'none' = no injection (clean baseline). "
                         "'native' = use ground_truth.anti_hypothesis or operator_narrative. "
                         "'false' = inject deliberately wrong claim from FALSE_OPERATOR_BY_CASE.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    requested = [c for c in args.cases.split(",") if c.strip()] if args.cases else []
    all_supported = sorted(
        p for p in CASE_DIR.iterdir()
        if p.is_dir() and (p / "ground_truth.json").exists() and _supported_case(p)
    )
    if requested:
        cases = [c for c in all_supported if c.name in requested]
        missing = set(requested) - {c.name for c in cases}
        if missing:
            print(f"[warn] requested but unsupported/missing: {sorted(missing)}")
    else:
        cases = all_supported

    print(f"Models: {args.models}")
    print(f"Cases ({len(cases)}): {[c.name for c in cases]}")
    print(f"Seeds per case: {args.seeds}  temperature={args.temperature}")
    total_calls = len(args.models) * len(cases) * args.seeds
    print(f"Total calls: {total_calls}  budget=${args.budget_usd:.2f}")
    if args.dry_run:
        print("Dry-run — no API calls.")
        return 0

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = Path(args.out) if args.out else OUT_ROOT / f"opus46_vs_opus47_{stamp}.json"

    spent = 0.0
    aggregates: list[ModelAggregate] = []
    for model in args.models:
        print(f"\n=== {model} ===")
        rows: list[CaseSeedResult] = []
        stop = False
        for i, case in enumerate(cases, 1):
            for s in range(args.seeds):
                if (args.budget_usd - spent) < 1.0:
                    print(f"[budget] ${spent:.2f}/${args.budget_usd:.2f} — stop before {model}/{case.name}/seed{s}.")
                    stop = True
                    break
                tag = f"[{i}/{len(cases)} s{s}] {model} :: {case.name}"
                print(f"{tag} ...", flush=True)
                r = _run_case_seed(
                    case, model, s, args.temperature,
                    apply_grounding=not args.no_grounding,
                    operator_mode=args.operator_mode,
                )
                rows.append(r)
                spent += r.cost_usd
                mark = "OK " if r.bug_match else "MISS"
                pt_tag = f"f={int(r.pt_file_match)} fn={int(r.pt_function_match)} both={int(r.pt_both_match)}"
                print(f"  -> {mark} {pt_tag} pred={r.predicted_bug} truth={r.ground_truth_bug} "
                      f"conf={r.confidence:.2f} ev={r.evidence_count} "
                      f"cost=${r.cost_usd:.3f} wall={r.wall_time_s:.1f}s")
                if r.tool_error:
                    print(f"  notes: {r.notes[:200]}")
            if stop:
                break
        aggregates.append(_aggregate(model, rows, args.seeds, args.operator_mode))

    delta: dict[str, Any] = {}
    if len(aggregates) == 2 and aggregates[0].n_runs and aggregates[1].n_runs:
        a, b = aggregates[0], aggregates[1]
        delta = {
            "from_model": a.model,
            "to_model": b.model,
            "bug_match_rate_delta": b.bug_match_rate - a.bug_match_rate,
            "pt_file_rate_delta": b.pt_file_rate - a.pt_file_rate,
            "pt_function_rate_delta": b.pt_function_rate - a.pt_function_rate,
            "pt_both_rate_delta": b.pt_both_rate - a.pt_both_rate,
            "brier_score_delta": b.brier_score - a.brier_score,
            "mean_evidence_count_delta": b.mean_evidence_count - a.mean_evidence_count,
            "tool_error_count_delta": b.tool_error_count - a.tool_error_count,
            "mean_flip_rate_delta": b.mean_flip_rate - a.mean_flip_rate,
            "refutation_rate_delta": b.refutation_rate - a.refutation_rate,
            "abstention_correctness_delta": b.abstention_correctness - a.abstention_correctness,
            "solvable_accuracy_delta": b.solvable_accuracy - a.solvable_accuracy,
            "total_cost_usd_delta": b.total_cost_usd - a.total_cost_usd,
            "total_wall_time_s_delta": b.total_wall_time_s - a.total_wall_time_s,
            "usd_per_correct_delta": b.usd_per_correct - a.usd_per_correct,
            "wall_per_correct_delta": b.wall_per_correct - a.wall_per_correct,
        }

    payload = {
        "schema": "opus_model_compare/2.3",
        "timestamp_utc": stamp,
        "budget_usd": args.budget_usd,
        "seeds": args.seeds,
        "temperature": args.temperature,
        "grounding": not args.no_grounding,
        "operator_mode": args.operator_mode,
        "cases": [c.name for c in cases],
        "models": [a.model for a in aggregates],
        "aggregates": [asdict(a) for a in aggregates],
        "delta": delta,
        "total_spent_usd": spent,
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str))

    print(f"\n{'=' * 60}")
    for a in aggregates:
        print(f"{a.model}: bug={a.bug_match_count}/{a.n_runs} "
              f"({a.bug_match_rate:.0%} ±{a.bug_match_stderr:.0%})  "
              f"pt_file={a.pt_file_rate:.0%}  pt_func={a.pt_function_rate:.0%}  "
              f"pt_both={a.pt_both_rate:.0%}  brier={a.brier_score:.3f}  "
              f"flip={a.mean_flip_rate:.0%}  "
              f"refute={a.refutation_rate:.0%} (n={a.n_refutation_runs})  "
              f"abst_ok={a.abstention_correctness:.0%} (n={a.n_under_specified_runs})  "
              f"solv_acc={a.solvable_accuracy:.0%} (n={a.n_solvable_runs})  "
              f"ev={a.mean_evidence_count:.1f}  "
              f"errs={a.tool_error_count}  cost=${a.total_cost_usd:.3f}  "
              f"wall={a.total_wall_time_s:.1f}s  "
              f"$/correct={'∞' if math.isinf(a.usd_per_correct) else f'${a.usd_per_correct:.3f}'}  "
              f"s/correct={'∞' if math.isinf(a.wall_per_correct) else f'{a.wall_per_correct:.1f}'}")
    if delta:
        print(f"\nDelta {delta['from_model']} -> {delta['to_model']}:")
        print(f"  bug_match_rate     {delta['bug_match_rate_delta']:+.2%}")
        print(f"  pt_file_rate       {delta['pt_file_rate_delta']:+.2%}")
        print(f"  pt_function_rate   {delta['pt_function_rate_delta']:+.2%}")
        print(f"  pt_both_rate       {delta['pt_both_rate_delta']:+.2%}")
        print(f"  brier (lower=bttr) {delta['brier_score_delta']:+.3f}")
        print(f"  flip_rate (lower=bttr) {delta['mean_flip_rate_delta']:+.2%}")
        print(f"  refutation_rate    {delta['refutation_rate_delta']:+.2%}")
        print(f"  abstention_correct {delta['abstention_correctness_delta']:+.2%}")
        print(f"  solvable_accuracy  {delta['solvable_accuracy_delta']:+.2%}")
        print(f"  evidence_count     {delta['mean_evidence_count_delta']:+.2f}")
        print(f"  tool_errors        {delta['tool_error_count_delta']:+d}")
        print(f"  cost_usd           ${delta['total_cost_usd_delta']:+.3f}")
        print(f"  wall_time_s        {delta['total_wall_time_s_delta']:+.1f}")
        print(f"  $/correct          {delta['usd_per_correct_delta']:+.3f}")
        print(f"  s/correct          {delta['wall_per_correct_delta']:+.1f}")
    print(f"\nWritten: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
