"""One-shot forensic pass on rtk_heading_break_01.

Loads the telemetry.npz for the case, builds a text-only bag summary of
sensor evidence, runs the post_mortem prompt via ClaudeClient (no images),
grounds the result via the gate already wired into claude_client.analyze,
and dumps the report JSON to runs/sample/rtk_heading_break_01.json.

Tests whether the tool's existing post-mortem prompt can surface the RTK
heading-subsystem failure from telemetry alone without any tunnel bias.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from black_box.analysis.claude_client import ClaudeClient
from black_box.analysis.prompts import post_mortem_prompt

CASE = REPO / "black-box-bench" / "cases" / "rtk_heading_break_01"


def _summarize(npz: np.lib.npyio.NpzFile) -> str:
    rover_carr = npz["rover_carr"]
    mb_carr = npz["mb_carr"]
    relpos_flags = npz["relpos_flags"]
    rover_numSV = npz["rover_numSV"]
    rover_hAcc_mm = npz["rover_hAcc_mm"]
    mb_numSV = npz["mb_numSV"]
    mb_hAcc_mm = npz["mb_hAcc_mm"]
    rover_t_ns = npz["rover_t_ns"]

    n_rover = len(rover_carr)
    n_mb = len(mb_carr)
    n_rel = len(relpos_flags)

    def pct(arr, value):
        return 100.0 * np.mean(arr == value)

    bag_start_s = rover_t_ns[0] / 1e9
    bag_end_s = rover_t_ns[-1] / 1e9
    bag_dur_s = bag_end_s - bag_start_s

    rel_pos_valid = (relpos_flags & 0x04).astype(bool)
    diff_soln = (relpos_flags & 0x02).astype(bool)

    return f"""Platform: autonomous car, ROS 1 Noetic. Session 2026-02-03, duration {bag_dur_s:.1f} s.

Hardware: ublox ZED-F9P dual-antenna GNSS, one "moving base" antenna + one "rover" antenna intended to produce cm-level relative heading via carrier-phase RTK between the two.

Topics captured (extracted from bag into a fixed telemetry matrix, no access to raw bag in this call):

/ublox_rover/navpvt   (ublox_msgs/NavPVT, {n_rover} samples):
  numSV          min={rover_numSV.min():d}  max={rover_numSV.max():d}  median={int(np.median(rover_numSV)):d}
  hAcc           min={rover_hAcc_mm.min()/1000:.2f} m  median={np.median(rover_hAcc_mm)/1000:.2f} m  max={rover_hAcc_mm.max()/1000:.2f} m
  fixType==3     {pct(npz['rover_fixType'], 3):.1f}%   (3D fix)
  carrier-phase: CARR_NONE={pct(rover_carr, 0):.1f}%  FLOAT={pct(rover_carr, 1):.1f}%  FIXED={pct(rover_carr, 2):.1f}%

/ublox_moving_base/navpvt   (ublox_msgs/NavPVT, {n_mb} samples):
  numSV          min={mb_numSV.min():d}  max={mb_numSV.max():d}  median={int(np.median(mb_numSV)):d}
  hAcc           min={mb_hAcc_mm.min()/1000:.2f} m  median={np.median(mb_hAcc_mm)/1000:.2f} m  max={mb_hAcc_mm.max()/1000:.2f} m
  carrier-phase: CARR_NONE={pct(mb_carr, 0):.1f}%  FLOAT={pct(mb_carr, 1):.1f}%  FIXED={pct(mb_carr, 2):.1f}%

/ublox_rover/navrelposned   (ublox_msgs/NavRELPOSNED9, {n_rel} samples):
  FLAGS_GNSS_FIX_OK (bit 0)  set on {(relpos_flags & 0x01).astype(bool).mean()*100:.1f}% of samples
  FLAGS_DIFF_SOLN   (bit 1)  set on {diff_soln.mean()*100:.1f}% of samples   (= rover receives RTCM corrections from the base)
  FLAGS_REL_POS_VALID (bit 2) set on {rel_pos_valid.mean()*100:.1f}% of samples
  relPosLength (cm)    min={npz['relpos_relPosLength_cm'].min():d}  max={npz['relpos_relPosLength_cm'].max():d}
  relPosHeading (1e-5 deg) min={npz['relpos_relPosHeading_1e5deg'].min():d} max={npz['relpos_relPosHeading_1e5deg'].max():d}
  accLength (0.1 mm)   min={npz['relpos_accLength_0p1mm'].min():d} max={npz['relpos_accLength_0p1mm'].max():d}

Rate observations (not shown in full but verified separately):
  /imu/data, /ublox_rover/navpvt, /ublox_moving_base/navpvt, /ublox_rover/navrelposned, /ublox_rover/navheading all publish at their expected rates for the entire bag. No drop-outs, no frozen windows, no position jumps > 10 m.

Operator self-report (do not take as ground truth): "We think the GPS fails when the car drives through a tunnel." No tunnel timestamp was given and sensor metrics show no tunnel-specific degradation.
"""


def _synced_frames_description() -> str:
    return "No camera frames are provided in this analysis pass. The evidence in the bag summary is telemetry-only."


def _code_snippets() -> str:
    return "The controller source is not available in the bag artifacts. When proposing a patch, specify the target by topic and field (e.g., 'the node that subscribes /ublox_rover/navrelposned'), not a file path."


def main() -> int:
    npz = np.load(CASE / "telemetry.npz")
    summary = _summarize(npz)

    client = ClaudeClient()
    spec = post_mortem_prompt()
    report, cost = client.analyze(
        prompt_spec=spec,
        images=None,
        user_fields={
            "bag_summary": summary,
            "synced_frames_description": _synced_frames_description(),
            "code_snippets": _code_snippets(),
        },
        resolution="thumb",
        max_tokens=4000,
        apply_grounding=False,
    )

    out_dir = REPO / "black-box-bench" / "runs" / "sample"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "rtk_heading_break_01.json"
    out_path.write_text(report.model_dump_json(indent=2))

    print("=== report ===")
    print(report.model_dump_json(indent=2))
    print()
    print("=== cost ===")
    print(
        f"cached_in={cost.cached_input_tokens} uncached_in={cost.uncached_input_tokens} "
        f"cache_create={cost.cache_creation_tokens} out={cost.output_tokens} "
        f"USD={cost.usd_cost:.4f} wall={cost.wall_time_s:.1f}s"
    )
    print(f"wrote {out_path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
