# SPDX-License-Identifier: MIT
"""Visual-mining orchestrator (#87) — cross-modal hero mode.

Glue layer that takes the existing pieces — `from_timeline` for window
selection, `sample_frames` for windowed densification, `visual_mining_v2`
for the prompt — and obeys CLAUDE.md frame discipline:

- 800×600 thumbnails by default; 3.75 MP only when the analysis step
  explicitly escalates.
- 5 cameras in ONE prompt (cross-view reasoning), never 5 separate calls.
- Windowed densification anchored on suspicious telemetry windows
  produced upstream — never uniform-stride sampling.

This module is intentionally side-effect-free at import time. The
orchestrator function returns a structured plan dict; the live agent
loop is the consumer that pays for tokens. The cost-delta tracker
reads ``data/costs.jsonl`` after the fact.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Optional


DEFAULT_THUMBNAIL = (800, 600)
HIRES_ESCALATION = (2500, 1500)  # ~3.75 MP
PROMPT_KIND_VISUAL = "visual_mining_v2"
PROMPT_KIND_TELEMETRY_ONLY = "telemetry_drop_v1"


@dataclass
class VisualMiningPlan:
    """Structured plan emitted before any model call. Audit-friendly."""

    case_key: str
    windows_anchored_from: Literal["from_timeline", "operator", "stub"]
    windows_s: list[tuple[float, float]]
    cameras: list[str]
    resolution: tuple[int, int]
    cross_view_single_call: bool = True
    notes: list[str] = field(default_factory=list)


class FrameDisciplineError(ValueError):
    """Raised when a plan violates CLAUDE.md frame discipline."""


def validate_plan(plan: VisualMiningPlan) -> None:
    if plan.resolution != DEFAULT_THUMBNAIL and plan.resolution != HIRES_ESCALATION:
        raise FrameDisciplineError(
            f"resolution {plan.resolution} is not 800x600 (default) or 2500x1500 (escalation)"
        )
    if len(plan.cameras) < 2:
        raise FrameDisciplineError(
            "visual_mining_v2 requires multiple cameras for cross-view reasoning"
        )
    if not plan.cross_view_single_call:
        raise FrameDisciplineError(
            "5 cameras must land in ONE prompt; per-camera calls are forbidden"
        )
    if not plan.windows_s:
        raise FrameDisciplineError(
            "no windows anchored from telemetry — uniform-stride sampling is a bug"
        )
    if plan.windows_anchored_from == "stub":
        raise FrameDisciplineError("plan windows came from a stub; refusing to spend on uniform stride")


def plan_visual_mining(
    *,
    case_key: str,
    timeline_json_path: Optional[Path],
    cameras: Iterable[str],
    resolution: tuple[int, int] = DEFAULT_THUMBNAIL,
    operator_windows: Optional[list[tuple[float, float]]] = None,
) -> VisualMiningPlan:
    """Build a ``VisualMiningPlan`` from existing telemetry analysis.

    Window source priority:
      1. ``operator_windows`` if provided (live steering — see #85).
      2. ``from_timeline(timeline_json_path)`` parsed off the prior turn's
         analysis.json.
      3. None — raises ``FrameDisciplineError`` from validate_plan.
    """
    cams = list(dict.fromkeys(cameras))
    if operator_windows:
        plan = VisualMiningPlan(
            case_key=case_key,
            windows_anchored_from="operator",
            windows_s=list(operator_windows),
            cameras=cams,
            resolution=resolution,
        )
    elif timeline_json_path and timeline_json_path.exists():
        from .windows import from_timeline
        windows = from_timeline(json.loads(timeline_json_path.read_text(encoding="utf-8")))
        windows_s = []
        for w in windows:
            half_ns = (w.span_s * 1e9) / 2
            t0 = (w.center_ns - half_ns) / 1e9
            t1 = (w.center_ns + half_ns) / 1e9
            windows_s.append((float(t0), float(t1)))
        plan = VisualMiningPlan(
            case_key=case_key,
            windows_anchored_from="from_timeline",
            windows_s=windows_s,
            cameras=cams,
            resolution=resolution,
        )
    else:
        plan = VisualMiningPlan(
            case_key=case_key,
            windows_anchored_from="stub",
            windows_s=[],
            cameras=cams,
            resolution=resolution,
        )
    validate_plan(plan)
    return plan


# ---------------------------------------------------------------------------
# Cost-delta reporter — visual vs telemetry-only on the same case_key
# ---------------------------------------------------------------------------
def cost_delta(costs_path: Path, case_key: str) -> dict[str, Any]:
    """Compare USD spend between visual and telemetry-only prompts on a case."""
    visual_usd = 0.0
    tele_usd = 0.0
    visual_n = tele_n = 0
    if not costs_path.exists():
        return {"visual_usd": 0.0, "telemetry_usd": 0.0, "delta_usd": 0.0, "visual_n": 0, "telemetry_n": 0}
    for line in costs_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(row.get("case_key") or row.get("job_id") or "") != case_key:
            continue
        kind = str(row.get("prompt_kind") or "")
        usd = float(row.get("usd_cost") or 0.0)
        if kind == PROMPT_KIND_VISUAL:
            visual_usd += usd
            visual_n += 1
        elif kind == PROMPT_KIND_TELEMETRY_ONLY:
            tele_usd += usd
            tele_n += 1
    return {
        "case_key": case_key,
        "visual_usd": round(visual_usd, 4),
        "telemetry_usd": round(tele_usd, 4),
        "delta_usd": round(visual_usd - tele_usd, 4),
        "visual_n": visual_n,
        "telemetry_n": tele_n,
    }
