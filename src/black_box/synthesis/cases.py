"""Synthetic case registry + materialization to disk."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

from .controllers import buggy_sources, clean_sources
from .telemetry_gen import (
    gen_bad_gain,
    gen_pid_saturation,
    gen_sensor_timeout,
    save_npz,
)
from .video_prompts import video_prompt_for


@dataclass
class SyntheticCase:
    key: str
    bug_class: str
    window_s: Tuple[float, float]
    telemetry: Dict[str, dict] = field(repr=False)
    buggy_source: Dict[str, str] = field(repr=False)
    clean_source: Dict[str, str] = field(repr=False)
    ground_truth: Dict = field(repr=False)
    video_prompts: Dict[str, str] = field(repr=False)


def _pid_saturation_case() -> SyntheticCase:
    duration, sat_start, diverge = 20.0, 12.0, 15.0
    telemetry = gen_pid_saturation(
        duration_s=duration, hz=50.0, sat_start_s=sat_start, diverge_s=diverge
    )
    window = (sat_start, min(duration, diverge + 3.0))
    bug_class = "pid_saturation"
    gt = {
        "bug_class": bug_class,
        "window_s": list(window),
        "evidence_hints": [
            "PWM on /pwm pegs at 255 for all 4 motors starting at ~12.0s",
            "/odom/pose yaw and y drift from /reference after ~15.0s",
            "/cmd_vel linear command keeps rising while pose stops tracking",
        ],
        "patch_hint": (
            "Add anti-windup to PIDController.step: only accumulate the "
            "integral when the unclamped output is inside [PWM_MIN, PWM_MAX] "
            "or when the error would reduce saturation."
        ),
    }
    vp = video_prompt_for(
        bug_class,
        window_description=(
            f"from t={window[0]:.1f}s to t={window[1]:.1f}s: motors pinned at "
            "max, path drifting off-lane despite full throttle."
        ),
    )
    return SyntheticCase(
        key="pid_saturation_01",
        bug_class=bug_class,
        window_s=window,
        telemetry=telemetry,
        buggy_source=buggy_sources()[bug_class],
        clean_source=clean_sources()[bug_class],
        ground_truth=gt,
        video_prompts=vp,
    )


def _sensor_timeout_case() -> SyntheticCase:
    stall_start, stall_dur = 10.0, 3.0
    telemetry = gen_sensor_timeout(
        duration_s=20.0, hz=50.0, stall_start_s=stall_start, stall_dur_s=stall_dur
    )
    window = (stall_start, stall_start + stall_dur + 1.0)
    bug_class = "sensor_timeout"
    gt = {
        "bug_class": bug_class,
        "window_s": list(window),
        "evidence_hints": [
            "/scan_range is bit-exactly constant between 10.0s and 13.0s",
            "/imu/accel continues normally (sensor subsystem alive)",
            "/cmd_vel angular spikes to +/- 2.5 rad/s with no visible obstacle",
        ],
        "patch_hint": (
            "In ObstacleAvoider.step, compare (time.time() - self.last_scan_t) "
            "against a SCAN_TIMEOUT_S constant and fall back to a conservative "
            "crawl (low linear, zero angular) when the scan is stale."
        ),
    }
    vp = video_prompt_for(
        bug_class,
        window_description=(
            f"from t={window[0]:.1f}s to t={window[1]:.1f}s: robot violently "
            "turns in place despite an empty corridor ahead."
        ),
    )
    return SyntheticCase(
        key="sensor_timeout_01",
        bug_class=bug_class,
        window_s=window,
        telemetry=telemetry,
        buggy_source=buggy_sources()[bug_class],
        clean_source=clean_sources()[bug_class],
        ground_truth=gt,
        video_prompts=vp,
    )


def _bad_gain_case() -> SyntheticCase:
    duration = 20.0
    telemetry = gen_bad_gain(duration_s=duration, hz=50.0, kp_too_high=True)
    window = (5.0, duration)
    bug_class = "bad_gain_tuning"
    gt = {
        "bug_class": bug_class,
        "window_s": list(window),
        "evidence_hints": [
            "/cmd_vel angular oscillates at ~2.5 rad/s with growing amplitude",
            "/odom/pose yaw overshoots /reference yaw on every swing",
            "/pwm alternates left/right wheel pairs in square-wave fashion",
        ],
        "patch_hint": (
            "Reduce HeadingController.Kp from 4.5 to ~0.8 and add a dead-band "
            "guard: if |err| < 1e-3 rad, command 0 angular rate to avoid "
            "limit-cycling on sensor noise."
        ),
    }
    vp = video_prompt_for(
        bug_class,
        window_description=(
            f"from t={window[0]:.1f}s to t={window[1]:.1f}s: robot weaves "
            "left-right across a painted reference line with growing amplitude."
        ),
    )
    return SyntheticCase(
        key="bad_gain_01",
        bug_class=bug_class,
        window_s=window,
        telemetry=telemetry,
        buggy_source=buggy_sources()[bug_class],
        clean_source=clean_sources()[bug_class],
        ground_truth=gt,
        video_prompts=vp,
    )


def build_all_cases() -> List[SyntheticCase]:
    return [_pid_saturation_case(), _sensor_timeout_case(), _bad_gain_case()]


def _render_readme(case: SyntheticCase) -> str:
    topics = "\n".join(f"  - `{t}` fields={ts['fields']}" for t, ts in case.telemetry.items())
    return f"""# {case.key}

**Bug class:** `{case.bug_class}`
**Ground-truth window:** {case.window_s[0]:.1f}s – {case.window_s[1]:.1f}s

## Telemetry topics
{topics}

## Files

- `ground_truth.json` — machine-readable labels for eval.
- `telemetry.npz` — numpy arrays (use `np.load(..., allow_pickle=True)`).
- `source/buggy/` — the controller as shipped; reproduces the bug.
- `source/clean/` — intended fix; compare for patch diff demo.
- `video_prompts.md` — prompts for Nano Banana Pro (stills) and Wan 2.2 (clips).

## Evidence hints
""" + "\n".join(f"- {h}" for h in case.ground_truth["evidence_hints"]) + f"""

## Patch hint
{case.ground_truth["patch_hint"]}
"""


def _render_video_prompts_md(case: SyntheticCase) -> str:
    vp = case.video_prompts
    return f"""# Video / image prompts — {case.key}

> Feed these to Nano Banana Pro (stills) and Wan 2.2 (short clips). The output
> MP4s should be placed under `video/cam{{0..4}}.mp4` for ingestion.

## Nano Banana Pro (key frames)

{vp["nano_banana_pro_prompt"]}

## Wan 2.2 (video clip, 3-6s)

{vp["wan22_prompt"]}

## Camera layout (replicate x5)

{vp["camera_layout"]}

## Notes

{vp["notes"]}
"""


def materialize_case(case: SyntheticCase, out_dir: Path) -> None:
    """Write a single case to ``<out_dir>/<key>/`` with all artifacts."""
    out_dir = Path(out_dir)
    root = out_dir / case.key
    root.mkdir(parents=True, exist_ok=True)

    # ground truth
    (root / "ground_truth.json").write_text(
        json.dumps(case.ground_truth, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # sources
    buggy_dir = root / "source" / "buggy"
    clean_dir = root / "source" / "clean"
    buggy_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)
    for fname, code in case.buggy_source.items():
        (buggy_dir / fname).write_text(code, encoding="utf-8")
    for fname, code in case.clean_source.items():
        (clean_dir / fname).write_text(code, encoding="utf-8")

    # telemetry
    save_npz(case.telemetry, root / "telemetry.npz")

    # prompts + README
    (root / "video_prompts.md").write_text(_render_video_prompts_md(case), encoding="utf-8")
    (root / "README.md").write_text(_render_readme(case), encoding="utf-8")
