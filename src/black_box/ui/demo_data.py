"""Sample case data for the redesigned UI surfaces.

Mirrors data.jsx from the design handoff. Used until the real pipeline
populates a live case store.
"""
from __future__ import annotations

SANFER = {
    "id": "case_2026_04_18_sanfer",
    "key": "sanfer-tunnel-04-18",
    "bag": "sanfer_tunnel_run_4.mcap",
    "bag_size": "2.4 GB",
    "duration": 4567,
    "duration_label": "1h 16m 07s",
    "mode": "Tier 1 — Forensic post-mortem",
    "cost": "$0.4612",
    "date": "2026-04-18  14:07 PDT",
    "runtime": "43s",
    "hypothesis_operator": "Tunnel ingress caused vision loss; robot lost localization at t=02:57:11.",
    "hypothesis_model": "RTK heading subsystem failed at t=02:14:32, 43 min before tunnel entry. Tunnel only revealed a pre-existing fault.",
    "verdict": "REFUTED",
    "verdict_body": "Operator hypothesis (tunnel) does not match telemetry.",
    "window_start": 1872,
    "window_end": 2120,
    "tunnel_start": 4391,
    "tunnel_end": 4520,
    "recco": (
        "Quarantine /gnss/rtk_status as a hard fault source. Promote dual-receiver disagreement >0.40m "
        "to a halting condition. Re-baseline heading covariance prior; current σ=0.02 rad is two orders "
        "of magnitude tighter than observed dispersion in the 90s preceding the failure."
    ),
    "exhibits": [
        {"n": "E1", "type": "telemetry", "type_label": "Telemetry",
         "title": "RTK fix quality collapses at t=02:14:32",
         "cap": "Fix-type drops from RTK_FIXED → FLOAT → SINGLE over 11s. No tunnel obstruction at this timestamp; robot is in open lot.",
         "t": 1872, "source": "/gnss/fix · 5 Hz", "kind": "plot-line"},
        {"n": "E2", "type": "telemetry", "type_label": "Telemetry",
         "title": "Heading covariance silently widens 90s prior",
         "cap": "σ_yaw climbs from 0.018 rad to 0.21 rad without triggering /diagnostics. Estimator continues reporting nominal.",
         "t": 1782, "source": "/odom/ekf · 50 Hz", "kind": "plot-area"},
        {"n": "E3", "type": "frame", "type_label": "Frame",
         "title": "Front camera shows clear sky, lot empty",
         "cap": "Frame at t=02:14:35. Refutes occlusion hypothesis: sky visibility >85%, no overhang, no foliage.",
         "t": 1875, "source": "/cam_front/image_raw", "kind": "frame"},
        {"n": "E4", "type": "telemetry", "type_label": "Telemetry",
         "title": "Tunnel entry is at t=02:57:11 — 42m38s later",
         "cap": "GPS dropout coincident with mapped tunnel polygon. Robot already operating on degraded estimator.",
         "t": 4391, "source": "/gnss/fix · /map/static", "kind": "plot-step"},
        {"n": "E5", "type": "log", "type_label": "Log line",
         "title": "rtk_driver: 'partial reset, retry 0/3' at 02:14:30",
         "cap": "Single warning, suppressed by rate-limiter. Should have escalated. No /diagnostics_agg entry produced.",
         "t": 1870, "source": "rosout · WARN", "kind": "log"},
        {"n": "E6", "type": "diff", "type_label": "Source",
         "title": "ekf_node.cpp:412 — heading prior never updated",
         "cap": "Initial covariance set at boot; no decay, no replan. Estimator self-confidence rises monotonically.",
         "t": None, "source": "perception/src/ekf_node.cpp", "kind": "diff"},
        {"n": "E7", "type": "frame", "type_label": "Frame",
         "title": "Tunnel-entry frame — for completeness",
         "cap": "Operator's claimed cause. Frame is dim but feature-rich; vision pipeline reports nominal.",
         "t": 4393, "source": "/cam_front/image_raw", "kind": "frame-dim"},
        {"n": "E8", "type": "telemetry", "type_label": "Telemetry",
         "title": "Dual-receiver disagreement spikes to 0.62m",
         "cap": "Secondary disagrees with primary by >40cm for 280s. No code path consumes this signal.",
         "t": 1592, "source": "/gnss/secondary", "kind": "plot-bars"},
        {"n": "E9", "type": "telemetry", "type_label": "Telemetry",
         "title": "IMU bias drift uncorrelated with vibration",
         "cap": "Gyro z-bias drifts +0.004 rad/s during the 90s window. No mechanical excitation present.",
         "t": 1820, "source": "/imu/raw", "kind": "plot-line"},
        {"n": "E10", "type": "frame", "type_label": "Frame",
         "title": "Rear cam corroborates open sky",
         "cap": "Frame at t=02:14:36. Confirms no overhang or foliage at fault timestamp.",
         "t": 1876, "source": "/cam_rear/image_raw", "kind": "frame"},
        {"n": "E11", "type": "log", "type_label": "Log line",
         "title": "rate_limiter suppressed 3 fault tokens",
         "cap": "Token bucket exhausted at t=02:14:30. Three subsequent rtk_driver warnings dropped silently.",
         "t": 1870, "source": "rosout · INFO", "kind": "log"},
        {"n": "E12", "type": "diff", "type_label": "Source",
         "title": "diagnostic_agg.cpp:88 — fault aggregator skips RTK",
         "cap": "Aggregator only consumes /diagnostics, not /gnss/*. RTK faults bypass the escalation path entirely.",
         "t": None, "source": "perception/src/diagnostic_agg.cpp", "kind": "diff"},
    ],
    "tool_calls": [
        {"t": "+0.4s",  "tool": "decode_bag",                                 "in_b": 38,        "out_b": 2_412_000_000, "usd": 0.0000},
        {"t": "+1.1s",  "tool": "list_topics",                                "in_b": 24,        "out_b": 2_140,         "usd": 0.0001},
        {"t": "+1.8s",  "tool": "scan_diagnostics",                           "in_b": 86,        "out_b": 41_200,        "usd": 0.0008},
        {"t": "+3.4s",  "tool": "find_anomaly_windows",                       "in_b": 142,       "out_b": 1_840,         "usd": 0.0024},
        {"t": "+5.0s",  "tool": "sample_frames",                              "in_b": 96,        "out_b": 8_412_000,     "usd": 0.0061},
        {"t": "+9.7s",  "tool": "vision.describe",                            "in_b": 8_412_000, "out_b": 4_240,         "usd": 0.0421},
        {"t": "+14.2s", "tool": "telemetry.plot",                             "in_b": 184,       "out_b": 612_000,       "usd": 0.0033},
        {"t": "+17.6s", "tool": "telemetry.plot",                             "in_b": 192,       "out_b": 484_000,       "usd": 0.0029},
        {"t": "+21.4s", "tool": "src.read",                                   "in_b": 64,        "out_b": 18_400,        "usd": 0.0011},
        {"t": "+24.9s", "tool": "memory.read('bb-platform-priors')",           "in_b": 38,        "out_b": 9_120,         "usd": 0.0006},
        {"t": "+28.3s", "tool": "hypothesis.score",                           "in_b": 4_120,     "out_b": 1_840,         "usd": 0.0188},
        {"t": "+33.7s", "tool": "patch.scope",                                "in_b": 412,       "out_b": 6_240,         "usd": 0.0094},
        {"t": "+38.2s", "tool": "report.compose",                             "in_b": 12_840,    "out_b": 24_120,        "usd": 0.1041},
        {"t": "+42.1s", "tool": "memory.write('bb-forensic-learnings-2026Q2')", "in_b": 1_240,    "out_b": 96,            "usd": 0.0095},
    ],
}

PATCH = {
    "before": [
        "void EKFNode::propagate(double dt) {",
        "    state_ = F_ * state_;",
        "    P_ = F_ * P_ * F_.transpose() + Q_;",
        "    P_(yaw,yaw) = 0.02;",
        "    if (rtk_age_ > rtk_timeout_) {",
        "        rtk_quality_ = FLOAT;",
        "    }",
        "    publish(state_);",
        "    return;",
        "}",
    ],
    "after": [
        "void EKFNode::propagate(double dt) {",
        "    state_ = F_ * state_;",
        "    P_ = F_ * P_ * F_.transpose() + Q_;",
        "    P_(yaw,yaw) = adapt(rtk_quality_, dual_rcv_disagree_);",
        "    if (P_(yaw,yaw) > 0.15) escalate(DIAG_FAULT);",
        "    if (rtk_age_ > rtk_timeout_ || rtk_quality_ != FIXED) {",
        "        rtk_quality_ = FLOAT;",
        "        diag_->report(rtk_quality_, dual_rcv_disagree_);",
        "    }",
        "    publish(state_);",
        "    return;",
        "}",
    ],
    "del_lines": [3],
    "add_lines": [3, 4, 7],
}


CASES_INDEX = [
    {"id": "case_2026_04_22_palette", "key": "palette-thermal-04-22", "date": "2026-04-22", "mode": "T1", "verdict": "CONFIRMED",   "cost": "$0.3814", "duration": "38s", "tags": ["battery", "drive", "thermal"],   "summary": "Cell-7 internal resistance, not payload"},
    {"id": "case_2026_04_18_sanfer",  "key": "sanfer-tunnel-04-18",   "date": "2026-04-18", "mode": "T1", "verdict": "REFUTED",     "cost": "$0.4612", "duration": "43s", "tags": ["gnss", "rtk", "estimator"],      "summary": "RTK fault preceded tunnel by 43 min"},
    {"id": "case_2026_04_15_pier",    "key": "pier-handover-04-15",   "date": "2026-04-15", "mode": "T2", "verdict": "REFUTED",     "cost": "$0.2107", "duration": "29s", "tags": ["handover", "manipulation"],      "summary": "Gripper pose drift, not network latency"},
    {"id": "case_2026_04_12_yard9",   "key": "yard9-stall-04-12",     "date": "2026-04-12", "mode": "T1", "verdict": "INCONCLUSIVE","cost": "$0.5240", "duration": "61s", "tags": ["planner", "lidar"],              "summary": "Two viable hypotheses, requesting longer bag"},
    {"id": "case_2026_04_09_dock",    "key": "dock-mis-04-09",        "date": "2026-04-09", "mode": "T1", "verdict": "CONFIRMED",   "cost": "$0.1834", "duration": "22s", "tags": ["docking", "fiducial"],           "summary": "April-tag occlusion (operator correct)"},
    {"id": "case_2026_04_05_loop",    "key": "loop-overrun-04-05",    "date": "2026-04-05", "mode": "T3", "verdict": "REFUTED",     "cost": "$0.6022", "duration": "71s", "tags": ["control", "loop-rate"],          "summary": "Scheduler jitter, not motor saturation"},
    {"id": "case_2026_03_30_aisle",   "key": "aisle-bump-03-30",      "date": "2026-03-30", "mode": "T1", "verdict": "REFUTED",     "cost": "$0.2904", "duration": "34s", "tags": ["perception", "lidar"],           "summary": "Lidar shadow on dark pallet, not nav fault"},
    {"id": "case_2026_03_24_lift",    "key": "lift-stop-03-24",       "date": "2026-03-24", "mode": "T2", "verdict": "CONFIRMED",   "cost": "$0.3401", "duration": "41s", "tags": ["safety", "estop"],               "summary": "Light-curtain false trigger, root cause confirmed"},
]


def _verdict_class(v: str) -> str:
    v = v.upper()
    if v == "CONFIRMED":
        return "confirmed"
    if v == "REFUTED":
        return "refuted"
    return "inconclusive"


def recent_cases(n: int = 4) -> list[dict]:
    out = []
    for c in CASES_INDEX[:n]:
        out.append({**c, "verdict_class": _verdict_class(c["verdict"])})
    return out


def case_by_id(case_id: str | None) -> dict:
    return SANFER  # only one fully populated case for the demo


STAGE_NAMES = [
    "Decoding bag",
    "Sampling frames",
    "Running cross-camera analysis",
    "Grounding hypothesis",
    "Writing report",
]


def stage_idx_from_status(status: dict) -> int:
    progress = status.get("progress") or 0.0
    if progress >= 1.0:
        return len(STAGE_NAMES)
    # Walk roughly through 5 stages.
    return min(int(progress * len(STAGE_NAMES)), len(STAGE_NAMES) - 1)


def synth_status_for_done() -> dict:
    """Synthetic done-state status for /report preview without a real run."""
    return {
        "stage": "done",
        "progress": 1.0,
        "label": "Complete",
        "stage_label": "Complete",
        "upload": SANFER["bag"],
        "bag_size": SANFER["bag_size"],
        "adapter": "mcap_v1",
        "mode": "post_mortem",
        "mode_label": "Post-mortem",
        "cost_usd": 0.4612,
        "cached_tokens": 1842,
        "uncached_tokens": 412,
        "memory_rw": "1 / 1",
        "frames": 24,
        "duration_label": "43s",
        "stage_idx": len(STAGE_NAMES),
        "reasoning_buffer": [],
    }
