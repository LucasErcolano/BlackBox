"""Tier-3 eval runner for the Black Box bench.

Runs each case in ``black-box-bench/cases/`` through the synthetic-QA
pipeline, compares the predicted bug to ground truth, and emits a
metrics table.

Offline mode (``use_claude=False``, the default) short-circuits the
model call so the test suite and CI can exercise the plumbing without
spending tokens.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_CASE_DIR = REPO_ROOT / "black-box-bench" / "cases"


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


def _stub_predict(case: Path, gt: dict[str, Any]) -> dict[str, Any]:
    """Offline prediction: echoes ground truth so tests pass deterministically."""
    return {
        "predicted_bug": gt.get("bug_id") or gt.get("bug") or "unknown",
        "cost_usd": 0.0,
        "wall_time_s": 0.0,
        "notes": "stub (offline)",
    }


def _claude_predict(case: Path, gt: dict[str, Any]) -> dict[str, Any]:
    """Real prediction path. Soft-imports ClaudeClient so offline still works."""
    try:
        from black_box.analysis.claude_client import ClaudeClient  # type: ignore
        from black_box.analysis.prompts import synthetic_qa_prompt  # type: ignore
    except Exception as e:  # pragma: no cover
        return {
            "predicted_bug": "import_error",
            "cost_usd": 0.0,
            "wall_time_s": 0.0,
            "notes": f"ClaudeClient unavailable: {e!r}",
        }

    t0 = time.time()
    try:
        client = ClaudeClient()
        prompt = synthetic_qa_prompt(case_key=case.name, ground_truth=gt)  # type: ignore[call-arg]
        result = client.analyze(prompt=prompt)  # type: ignore[attr-defined]
        cost = getattr(getattr(client, "cost_log", None), "total_usd", 0.0)
        predicted = (
            result.get("predicted_bug")
            if isinstance(result, dict)
            else getattr(result, "predicted_bug", "unknown")
        )
    except Exception as e:  # pragma: no cover
        return {
            "predicted_bug": "error",
            "cost_usd": 0.0,
            "wall_time_s": time.time() - t0,
            "notes": repr(e),
        }
    return {
        "predicted_bug": predicted or "unknown",
        "cost_usd": float(cost or 0.0),
        "wall_time_s": time.time() - t0,
        "notes": "claude",
    }


# ---------------------------------------------------------------------------
def run_tier3(
    case_dir: Path,
    use_claude: bool = False,
    only: str | None = None,
) -> dict[str, Any]:
    """Execute the tier-3 eval and return a structured summary dict."""
    cases = _discover_cases(Path(case_dir))
    if only is not None:
        cases = [c for c in cases if c.name == only]

    rows: list[dict[str, Any]] = []
    for case in cases:
        gt = _load_ground_truth(case)
        pred = _claude_predict(case, gt) if use_claude else _stub_predict(case, gt)
        gt_bug = gt.get("bug_id") or gt.get("bug") or "unknown"
        rows.append(
            {
                "case_key": case.name,
                "predicted_bug": pred["predicted_bug"],
                "ground_truth_bug": gt_bug,
                "match": pred["predicted_bug"] == gt_bug,
                "cost_usd": pred["cost_usd"],
                "wall_time_s": pred["wall_time_s"],
            }
        )

    total = len(rows)
    matches = sum(1 for r in rows if r["match"])
    return {
        "n_cases": total,
        "n_match": matches,
        "accuracy": (matches / total) if total else 0.0,
        "total_cost_usd": sum(r["cost_usd"] for r in rows),
        "rows": rows,
        "used_claude": use_claude,
    }


# ---------------------------------------------------------------------------
def _format_table(rows: list[dict[str, Any]]) -> str:
    try:
        from tabulate import tabulate  # type: ignore
        return tabulate(rows, headers="keys", tablefmt="simple")
    except Exception:
        if not rows:
            return "(no cases)"
        headers = list(rows[0].keys())
        widths = {h: max(len(h), *(len(str(r[h])) for r in rows)) for h in headers}
        lines = [
            "  ".join(h.ljust(widths[h]) for h in headers),
            "  ".join("-" * widths[h] for h in headers),
        ]
        for r in rows:
            lines.append("  ".join(str(r[h]).ljust(widths[h]) for h in headers))
        return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Black Box tier-3 eval runner")
    ap.add_argument("--case-dir", type=Path, default=DEFAULT_CASE_DIR)
    ap.add_argument("--use-claude", action="store_true")
    ap.add_argument("--case", type=str, default=None, help="run only this case key")
    args = ap.parse_args(argv)

    summary = run_tier3(args.case_dir, use_claude=args.use_claude, only=args.case)
    print(_format_table(summary["rows"]))
    print()
    print(
        f"cases={summary['n_cases']} match={summary['n_match']} "
        f"acc={summary['accuracy']:.2%} cost=${summary['total_cost_usd']:.4f} "
        f"claude={summary['used_claude']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
