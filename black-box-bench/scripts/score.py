"""Scoring harness for black-box-bench.

Usage:
    python scripts/score.py --case cases/pid_saturation_01 --prediction out.json
    python scripts/score.py --all --predictions-dir runs/2026-04-22/

Prediction JSON shape (produced by the Black Box agent):
{
  "bug_class": "pid_saturation",
  "window_s": [12.3, 17.8],
  "patch": {"file": "source/buggy/pid.py", "function": "PIDController.step"}
}

Scoring (max 2.0 per case):
  - root cause match (exact bug_class)   -> 1.0
  - window overlap IoU >= 0.5            -> 0.5
  - patch file + function match          -> 0.5
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class CaseScore:
    case: str
    bug_match: float
    window_iou: float
    window_score: float
    patch_score: float
    total: float
    bug_class_gt: str
    bug_class_pred: str
    window_gt: list[float]
    window_pred: list[float] | None
    notes: str = ""


def iou_1d(a: list[float], b: list[float]) -> float:
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    inter = max(0.0, hi - lo)
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0


def score_case(gt_path: Path, pred_path: Path) -> CaseScore:
    gt = json.loads(gt_path.read_text())
    pred = json.loads(pred_path.read_text()) if pred_path.exists() else {}

    skeleton = gt.get("status", "").startswith("skeleton")

    bug_gt = gt["bug_class"]
    bug_pred = pred.get("bug_class", "")
    bug_match = 1.0 if (bug_gt == bug_pred and not skeleton) else 0.0

    window_gt = gt["window_s"]
    window_pred = pred.get("window_s")
    window_gt_valid = (
        isinstance(window_gt, list)
        and len(window_gt) == 2
        and all(isinstance(v, (int, float)) for v in window_gt)
    )
    if window_pred and len(window_pred) == 2 and window_gt_valid:
        iou = iou_1d(window_gt, window_pred)
        window_score = 0.5 if iou >= 0.5 else 0.0
    else:
        iou = 0.0
        window_score = 0.0

    target = gt.get("patch_target") or {}
    patch_pred = pred.get("patch", {})
    if target:
        file_ok = bool(patch_pred.get("file")) and patch_pred["file"].endswith(
            target["file"].split("/")[-1]
        )
        fn_ok = patch_pred.get("function", "") == target.get("function", "__missing__")
        patch_score = 0.5 if (file_ok and fn_ok) else 0.0
    else:
        patch_score = 0.0

    return CaseScore(
        case=gt_path.parent.name,
        bug_match=bug_match,
        window_iou=iou,
        window_score=window_score,
        patch_score=patch_score,
        total=bug_match + window_score + patch_score,
        bug_class_gt=bug_gt,
        bug_class_pred=bug_pred,
        window_gt=window_gt if window_gt_valid else [],
        window_pred=window_pred,
        notes="skeleton (awaiting bag)" if skeleton else "",
    )


def print_table(scores: list[CaseScore]) -> None:
    header = f"{'case':30s} {'bug':5s} {'iou':>5s} {'win':>5s} {'patch':>5s} {'total':>5s}"
    print(header)
    print("-" * len(header))
    scoreable = [s for s in scores if not s.notes.startswith("skeleton")]
    for s in scores:
        suffix = f"  [{s.notes}]" if s.notes else ""
        print(
            f"{s.case:30s} {s.bug_match:5.1f} {s.window_iou:5.2f} "
            f"{s.window_score:5.1f} {s.patch_score:5.1f} {s.total:5.2f}{suffix}"
        )
    if scoreable:
        total = sum(s.total for s in scoreable)
        max_total = 2.0 * len(scoreable)
        print("-" * len(header))
        print(f"{'TOTAL (scoreable only)':30s} {'':5s} {'':>5s} {'':>5s} {'':>5s} "
              f"{total:5.2f} / {max_total:.1f}")
        if len(scoreable) < len(scores):
            skipped = len(scores) - len(scoreable)
            print(f"({skipped} skeleton case(s) excluded from total)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--case", type=Path, help="Path to one case dir")
    p.add_argument("--prediction", type=Path, help="Prediction JSON for --case")
    p.add_argument("--all", action="store_true", help="Score every case under cases/")
    p.add_argument("--predictions-dir", type=Path,
                   help="Dir containing <case_name>.json for --all mode")
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = p.parse_args()

    root = Path(__file__).resolve().parent.parent
    scores: list[CaseScore] = []

    if args.all:
        pred_dir = args.predictions_dir or root / "runs" / "latest"
        for case_dir in sorted((root / "cases").iterdir()):
            gt = case_dir / "ground_truth.json"
            pred = pred_dir / f"{case_dir.name}.json"
            if gt.exists():
                scores.append(score_case(gt, pred))
    else:
        if not args.case or not args.prediction:
            p.error("--case and --prediction required without --all")
        scores.append(score_case(args.case / "ground_truth.json", args.prediction))

    if args.json:
        print(json.dumps([asdict(s) for s in scores], indent=2))
    else:
        print_table(scores)


if __name__ == "__main__":
    main()
