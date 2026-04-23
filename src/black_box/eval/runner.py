"""Tiered eval runner for the Black Box bench.

Three tiers map to the three product modes:
  - tier-1: forensic post-mortem   (known-crash recording -> root cause + patch)
  - tier-2: scenario mining         (any recording -> moments of interest)
  - tier-3: synthetic QA            (injected-bug recording -> hypothesis + self-eval)

Each tier can run offline (``use_claude=False``, the default) or against
real Opus 4.7. Offline mode exercises the plumbing without spending
tokens; it is explicit about being offline in every row it emits and it
reads the same ground-truth key (``bug_class``) that the bench scorer
uses, so offline results are honest about what they measure.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_CASE_DIR = REPO_ROOT / "black-box-bench" / "cases"


# ---------------------------------------------------------------------------
# Case discovery + ground-truth loading
# ---------------------------------------------------------------------------
def _discover_cases(case_dir: Path) -> list[Path]:
    if not case_dir.exists():
        return []
    return sorted(
        p for p in case_dir.iterdir()
        if p.is_dir() and (p / "ground_truth.json").exists()
    )


def _load_ground_truth(case: Path) -> dict[str, Any]:
    return json.loads((case / "ground_truth.json").read_text())


def _gt_bug_class(gt: dict[str, Any]) -> str:
    """Canonical ground-truth bug key matches the bench scorer."""
    return gt.get("bug_class") or gt.get("bug_id") or gt.get("bug") or "unknown"


def _gt_accepted_classes(gt: dict[str, Any]) -> list[str]:
    """Cases may declare alternative acceptable labels under ``scoring.bug_class_match``."""
    primary = _gt_bug_class(gt)
    scoring = gt.get("scoring") or {}
    alts = scoring.get("bug_class_match")
    if isinstance(alts, list) and alts:
        return [a for a in alts if isinstance(a, str)]
    return [primary] if primary and primary != "unknown" else []


def _gt_window(gt: dict[str, Any]) -> list[float] | None:
    w = gt.get("window_s")
    if not (isinstance(w, list) and len(w) == 2):
        return None
    if not all(isinstance(x, (int, float)) for x in w):
        return None
    return [float(w[0]), float(w[1])]


def _is_skeleton(gt: dict[str, Any]) -> bool:
    return str(gt.get("status", "")).startswith("skeleton")


def _iou_1d(a: list[float], b: list[float]) -> float:
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    inter = max(0.0, hi - lo)
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# Offline stub predictors. Echo ground truth so the plumbing is exercised;
# every row is tagged ``source="stub"`` so no one mistakes these for model
# output.
# ---------------------------------------------------------------------------
def _stub_tier3(case: Path, gt: dict[str, Any]) -> dict[str, Any]:
    bug = _gt_bug_class(gt)
    return {
        # Skeleton cases (no bag yet) stay unknown so the row honestly
        # fails to score instead of silently matching unknown == unknown.
        "predicted_bug": bug if (bug != "unknown" and not _is_skeleton(gt)) else "unknown",
        "predicted_window": _gt_window(gt),
        "cost_usd": 0.0,
        "wall_time_s": 0.0,
        "source": "stub",
    }


def _stub_tier1(case: Path, gt: dict[str, Any]) -> dict[str, Any]:
    pred = _stub_tier3(case, gt)
    patch_target = gt.get("patch_target") or {}
    pred["predicted_patch"] = {
        "file": patch_target.get("file", ""),
        "function": patch_target.get("function", ""),
    }
    return pred


def _stub_tier2(case: Path, gt: dict[str, Any]) -> dict[str, Any]:
    """Scenario mining on a buggy case: the bug window IS the moment of interest."""
    window = _gt_window(gt)
    moments = [{"t": window, "kind": _gt_bug_class(gt)}] if window else []
    return {
        "predicted_moments": moments,
        "cost_usd": 0.0,
        "wall_time_s": 0.0,
        "source": "stub",
    }


# ---------------------------------------------------------------------------
# Real-Claude predictors. Soft-imports so offline still works in environments
# without the SDK. Explicit ``source="claude"`` tag on every row.
# ---------------------------------------------------------------------------
def _claude_tier3(case: Path, gt: dict[str, Any]) -> dict[str, Any]:
    try:
        from black_box.analysis.claude_client import ClaudeClient  # type: ignore
        from black_box.analysis.prompts import synthetic_qa_prompt  # type: ignore
    except Exception as e:  # pragma: no cover
        return {
            "predicted_bug": "import_error",
            "predicted_window": None,
            "cost_usd": 0.0,
            "wall_time_s": 0.0,
            "source": f"claude_unavailable:{e!r}",
        }

    t0 = time.time()
    try:
        client = ClaudeClient()
        prompt = synthetic_qa_prompt(case_key=case.name, ground_truth=gt)  # type: ignore[call-arg]
        result = client.analyze(prompt=prompt)  # type: ignore[attr-defined]
        cost = getattr(getattr(client, "cost_log", None), "total_usd", 0.0)
        predicted = (
            result.get("bug_class") or result.get("predicted_bug")
            if isinstance(result, dict)
            else getattr(result, "bug_class", None)
        )
        window = result.get("window_s") if isinstance(result, dict) else None
    except Exception as e:  # pragma: no cover
        return {
            "predicted_bug": "error",
            "predicted_window": None,
            "cost_usd": 0.0,
            "wall_time_s": time.time() - t0,
            "source": f"claude_error:{e!r}",
        }
    return {
        "predicted_bug": predicted or "unknown",
        "predicted_window": list(window) if isinstance(window, list) else None,
        "cost_usd": float(cost or 0.0),
        "wall_time_s": time.time() - t0,
        "source": "claude",
    }


def _claude_tier1(case: Path, gt: dict[str, Any]) -> dict[str, Any]:
    """Tier-1 = tier-3 + patch target. Same prompt template; richer parse."""
    out = _claude_tier3(case, gt)
    out.setdefault("predicted_patch", {"file": "", "function": ""})
    return out


def _claude_tier2(case: Path, gt: dict[str, Any]) -> dict[str, Any]:
    """Scenario mining: soft-import, placeholder until batch agent lands."""
    return {
        "predicted_moments": [],
        "cost_usd": 0.0,
        "wall_time_s": 0.0,
        "source": "claude_tier2_pending",
    }


# ---------------------------------------------------------------------------
# Tier runners
# ---------------------------------------------------------------------------
def _score_tier3(row: dict[str, Any], gt: dict[str, Any]) -> dict[str, Any]:
    gt_bug = _gt_bug_class(gt)
    accepted = _gt_accepted_classes(gt)
    row["ground_truth_bug"] = gt_bug
    row["skeleton"] = _is_skeleton(gt)
    row["match"] = (
        row.get("predicted_bug") in accepted if accepted else False
    ) and not row["skeleton"]
    return row


def _score_tier1(row: dict[str, Any], gt: dict[str, Any]) -> dict[str, Any]:
    """Bench-scorer-compatible tier-1 scoring: bug(1.0) + window(0.5) + patch(0.5)."""
    gt_bug = _gt_bug_class(gt)
    accepted = _gt_accepted_classes(gt)
    gt_win = _gt_window(gt)
    gt_patch = gt.get("patch_target") or {}
    skeleton = _is_skeleton(gt)

    bug_score = 1.0 if (accepted and row.get("predicted_bug") in accepted and not skeleton) else 0.0

    pred_win = row.get("predicted_window")
    window_score = 0.0
    if gt_win and isinstance(pred_win, list) and len(pred_win) == 2:
        window_score = 0.5 if _iou_1d(gt_win, pred_win) >= 0.5 else 0.0

    pred_patch = row.get("predicted_patch") or {}
    patch_score = 0.5 if (
        pred_patch.get("file") == gt_patch.get("file")
        and pred_patch.get("function") == gt_patch.get("function")
        and gt_patch.get("file")
    ) else 0.0

    total = bug_score + window_score + patch_score
    row.update({
        "ground_truth_bug": gt_bug,
        "skeleton": skeleton,
        "bug_score": bug_score,
        "window_score": window_score,
        "patch_score": patch_score,
        "total_score": total,
        "match": bug_score == 1.0,
    })
    return row


def _score_tier2(row: dict[str, Any], gt: dict[str, Any]) -> dict[str, Any]:
    """Scenario mining credit: at least one moment overlaps the bug window."""
    gt_win = _gt_window(gt)
    moments = row.get("predicted_moments") or []
    hit = False
    if gt_win:
        for m in moments:
            t = m.get("t")
            if (
                isinstance(t, list)
                and len(t) == 2
                and all(isinstance(x, (int, float)) for x in t)
                and _iou_1d(gt_win, [float(t[0]), float(t[1])]) > 0
            ):
                hit = True
                break
    row["ground_truth_bug"] = _gt_bug_class(gt)
    row["skeleton"] = _is_skeleton(gt)
    row["match"] = hit and not row["skeleton"]
    return row


_TIER_SPECS: dict[int, dict[str, Any]] = {
    1: {"stub": _stub_tier1, "claude": _claude_tier1, "score": _score_tier1},
    2: {"stub": _stub_tier2, "claude": _claude_tier2, "score": _score_tier2},
    3: {"stub": _stub_tier3, "claude": _claude_tier3, "score": _score_tier3},
}


def run_tier(
    tier: int,
    case_dir: Path,
    use_claude: bool = False,
    only: str | None = None,
) -> dict[str, Any]:
    """Generic tiered runner. Returns a structured summary dict."""
    if tier not in _TIER_SPECS:
        raise ValueError(f"unknown tier: {tier} (must be 1, 2, or 3)")
    spec = _TIER_SPECS[tier]
    predict: Callable[[Path, dict[str, Any]], dict[str, Any]] = (
        spec["claude"] if use_claude else spec["stub"]
    )
    score: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] = spec["score"]

    cases = _discover_cases(Path(case_dir))
    if only is not None:
        cases = [c for c in cases if c.name == only]

    rows: list[dict[str, Any]] = []
    for case in cases:
        gt = _load_ground_truth(case)
        pred = predict(case, gt)
        pred["case_key"] = case.name
        rows.append(score(pred, gt))

    total = len(rows)
    matches = sum(1 for r in rows if r.get("match"))
    summary: dict[str, Any] = {
        "tier": tier,
        "n_cases": total,
        "n_match": matches,
        "accuracy": (matches / total) if total else 0.0,
        "total_cost_usd": sum(r.get("cost_usd", 0.0) for r in rows),
        "rows": rows,
        "used_claude": use_claude,
    }
    if tier == 1:
        summary["total_score"] = sum(r.get("total_score", 0.0) for r in rows)
        summary["max_score"] = total * 2.0
    return summary


# Back-compat: preserve the historical tier-3 entry point.
def run_tier3(
    case_dir: Path,
    use_claude: bool = False,
    only: str | None = None,
) -> dict[str, Any]:
    return run_tier(3, case_dir, use_claude=use_claude, only=only)


# ---------------------------------------------------------------------------
def _format_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no cases)"
    try:
        from tabulate import tabulate  # type: ignore
        return tabulate(rows, headers="keys", tablefmt="simple")
    except Exception:
        headers = list(rows[0].keys())
        widths = {h: max(len(h), *(len(str(r.get(h, ""))) for r in rows)) for h in headers}
        lines = [
            "  ".join(h.ljust(widths[h]) for h in headers),
            "  ".join("-" * widths[h] for h in headers),
        ]
        for r in rows:
            lines.append("  ".join(str(r.get(h, "")).ljust(widths[h]) for h in headers))
        return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Black Box tiered eval runner")
    ap.add_argument("--tier", type=int, choices=(1, 2, 3), default=3)
    ap.add_argument("--case-dir", type=Path, default=DEFAULT_CASE_DIR)
    ap.add_argument("--use-claude", action="store_true")
    ap.add_argument("--case", type=str, default=None, help="run only this case key")
    args = ap.parse_args(argv)

    summary = run_tier(args.tier, args.case_dir, use_claude=args.use_claude, only=args.case)
    print(_format_table(summary["rows"]))
    print()
    tail = (
        f"tier={summary['tier']} cases={summary['n_cases']} match={summary['n_match']} "
        f"acc={summary['accuracy']:.2%} cost=${summary['total_cost_usd']:.4f} "
        f"claude={summary['used_claude']}"
    )
    if args.tier == 1:
        tail += f" total_score={summary['total_score']:.2f}/{summary['max_score']:.2f}"
    print(tail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
