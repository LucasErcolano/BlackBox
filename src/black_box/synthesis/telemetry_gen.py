# SPDX-License-Identifier: MIT
"""Synthetic telemetry generators for forensic-bench cases.

Each generator returns a dict of ``topic -> TimeSeries-like dict`` with keys
``t_ns`` (np.ndarray[int64] nanoseconds), ``values`` (np.ndarray[float64]
shape ``(N, K)``), and ``fields`` (list[str] of length K). This duck-types
``black_box.ingestion.rosbag_reader.TimeSeries``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np

TimeSeriesDict = Dict[str, object]


def _time_axis(duration_s: float, hz: float) -> np.ndarray:
    n = int(duration_s * hz)
    t_s = np.arange(n) / hz
    t_ns = (t_s * 1e9).astype(np.int64)
    return t_ns


def _ts(t_ns: np.ndarray, values: np.ndarray, fields: list[str]) -> TimeSeriesDict:
    return {"t_ns": t_ns, "values": values.astype(np.float64), "fields": list(fields)}


def gen_pid_saturation(
    duration_s: float = 20.0,
    hz: float = 50.0,
    sat_start_s: float = 12.0,
    diverge_s: float = 15.0,
    seed: int = 7,
) -> Dict[str, TimeSeriesDict]:
    """PID actuator-saturation + integral windup scenario.

    Nominal tracking until ``sat_start_s``; PWM clamps to 255 in
    ``[sat_start_s, diverge_s]``; after ``diverge_s`` pose diverges from
    the reference with a growing ramp error.
    """
    rng = np.random.default_rng(seed)
    t_ns = _time_axis(duration_s, hz)
    t = t_ns.astype(np.float64) * 1e-9
    n = t.size

    # reference: straight line at 0.5 m/s along x with slow yaw
    ref_x = 0.5 * t
    ref_y = np.zeros(n)
    ref_yaw = 0.05 * np.sin(0.2 * t)
    reference = np.stack([ref_x, ref_y, ref_yaw], axis=1)

    # pose: nominal tracking + noise
    noise = rng.normal(0.0, 0.01, size=(n, 3))
    pose = reference + noise

    # post-divergence ramp
    post = t > diverge_s
    dt_post = np.clip(t - diverge_s, 0.0, None)
    pose[:, 0] += 0.0  # x stays roughly on
    pose[:, 1] += 0.15 * dt_post ** 1.3  # y drifts
    pose[:, 2] += 0.35 * dt_post  # yaw diverges

    # cmd_vel: nominal forward, slight angular
    lin = np.full(n, 0.5) + rng.normal(0.0, 0.005, size=n)
    ang = 0.05 * np.cos(0.2 * t) + rng.normal(0.0, 0.005, size=n)
    # After sat window, controller asks for more, more
    mask_after_sat = t >= sat_start_s
    lin[mask_after_sat] += 0.3  # commanded speed rises
    cmd_vel = np.stack([lin, ang], axis=1)

    # PWM: 4 motors. Compute from cmd and clamp.
    base = 120 + 40 * (lin - 0.5) / 0.5
    pwm = np.stack([base, base, base, base], axis=1)
    pwm += rng.normal(0.0, 1.0, size=pwm.shape)

    # Saturation window: clamp at 255
    sat_mask = (t >= sat_start_s) & (t <= diverge_s)
    pwm[sat_mask] = 255.0
    # Post-divergence: stay pinned at 255 (actuator rail)
    post_mask = t > diverge_s
    pwm[post_mask] = 255.0

    # Pre-sat must be below 255
    pwm = np.clip(pwm, 0.0, 255.0)

    return {
        "/odom/pose": _ts(t_ns, pose, ["x", "y", "yaw"]),
        "/cmd_vel": _ts(t_ns, cmd_vel, ["linear", "angular"]),
        "/pwm": _ts(t_ns, pwm, ["m0", "m1", "m2", "m3"]),
        "/reference": _ts(t_ns, reference, ["x", "y", "yaw"]),
    }


def gen_sensor_timeout(
    duration_s: float = 20.0,
    hz: float = 50.0,
    stall_start_s: float = 10.0,
    stall_dur_s: float = 3.0,
    seed: int = 11,
) -> Dict[str, TimeSeriesDict]:
    """Lidar scalar freezes while IMU keeps streaming; controller panics.

    ``/scan_range`` holds its last value for ``stall_dur_s``. ``/imu/accel``
    continues normally. ``/cmd_vel`` shows a big angular spike as the
    obstacle avoider reacts to stale range data.
    """
    rng = np.random.default_rng(seed)
    t_ns = _time_axis(duration_s, hz)
    t = t_ns.astype(np.float64) * 1e-9
    n = t.size

    # scan_range: nominal ~3.0m with low noise, slowly drifting
    scan = 3.0 + 0.3 * np.sin(0.4 * t) + rng.normal(0.0, 0.02, size=n)

    stall_mask = (t >= stall_start_s) & (t < stall_start_s + stall_dur_s)
    if stall_mask.any():
        first_idx = int(np.argmax(stall_mask))
        frozen = scan[first_idx]
        scan[stall_mask] = frozen

    # imu accel x,y,z: keeps moving normally
    ax = 0.05 * np.sin(2.0 * t) + rng.normal(0.0, 0.02, size=n)
    ay = 0.05 * np.cos(2.0 * t) + rng.normal(0.0, 0.02, size=n)
    az = 9.81 + rng.normal(0.0, 0.02, size=n)
    imu = np.stack([ax, ay, az], axis=1)

    # cmd_vel: nominal cruising, then angular spike during stall
    lin = np.full(n, 0.4) + rng.normal(0.0, 0.005, size=n)
    ang = rng.normal(0.0, 0.01, size=n)

    # Phantom obstacle avoidance: slam brakes + hard turn
    react_start = stall_start_s + 0.2  # small reaction delay
    react_mask = (t >= react_start) & (t < stall_start_s + stall_dur_s + 1.0)
    lin[react_mask] = 0.0
    # Ballistic angular: big oscillating turn
    local_t = t[react_mask] - react_start
    ang[react_mask] = 2.5 * np.sign(np.sin(6.0 * local_t))

    cmd_vel = np.stack([lin, ang], axis=1)

    # reference: straight cruise
    ref = np.stack([0.4 * t, np.zeros(n), np.zeros(n)], axis=1)

    return {
        "/scan_range": _ts(t_ns, scan.reshape(-1, 1), ["range"]),
        "/imu/accel": _ts(t_ns, imu, ["ax", "ay", "az"]),
        "/cmd_vel": _ts(t_ns, cmd_vel, ["linear", "angular"]),
        "/reference": _ts(t_ns, ref, ["x", "y", "yaw"]),
    }


def gen_bad_gain(
    duration_s: float = 20.0,
    hz: float = 50.0,
    kp_too_high: bool = True,
    seed: int = 13,
) -> Dict[str, TimeSeriesDict]:
    """Heading controller with too-high Kp: oscillates with growing amplitude."""
    rng = np.random.default_rng(seed)
    t_ns = _time_axis(duration_s, hz)
    t = t_ns.astype(np.float64) * 1e-9
    n = t.size

    # reference sinusoidal yaw
    ref_yaw = 0.5 * np.sin(0.3 * t)
    ref_x = 0.3 * t
    ref_y = 0.0 * t
    reference = np.stack([ref_x, ref_y, ref_yaw], axis=1)

    # Simulate oscillation: tracked yaw with growing amplitude if kp too high
    if kp_too_high:
        growth = 1.0 + 0.08 * t  # amplitude grows over time
        overshoot = 0.6 * growth * np.sin(2.5 * t + 0.4)
        tracked_yaw = ref_yaw + overshoot * 0.5
    else:
        tracked_yaw = ref_yaw + rng.normal(0.0, 0.01, size=n)

    pose_x = ref_x + rng.normal(0.0, 0.01, size=n)
    pose_y = ref_y + 0.05 * np.cumsum(np.sin(2.5 * t)) / hz  # lateral drift from oscillation
    pose = np.stack([pose_x, pose_y, tracked_yaw], axis=1)

    # cmd_vel: strongly oscillating angular
    lin = np.full(n, 0.3)
    if kp_too_high:
        ang = 3.0 * (1.0 + 0.05 * t) * np.cos(2.5 * t)
    else:
        ang = 0.8 * np.cos(0.3 * t)
    cmd_vel = np.stack([lin, ang], axis=1)

    # PWM alternates left/right
    base = 150.0
    diff = 80.0 * np.sign(np.sin(2.5 * t)) if kp_too_high else 10.0 * np.sin(0.3 * t)
    pwm_l = base + diff
    pwm_r = base - diff
    pwm = np.stack([pwm_l, pwm_l, pwm_r, pwm_r], axis=1)
    pwm = np.clip(pwm + rng.normal(0.0, 1.0, size=pwm.shape), 0.0, 255.0)

    return {
        "/odom/pose": _ts(t_ns, pose, ["x", "y", "yaw"]),
        "/cmd_vel": _ts(t_ns, cmd_vel, ["linear", "angular"]),
        "/pwm": _ts(t_ns, pwm, ["m0", "m1", "m2", "m3"]),
        "/reference": _ts(t_ns, reference, ["x", "y", "yaw"]),
    }


def save_npz(telemetry: Dict[str, TimeSeriesDict], path: Path) -> None:
    """Save a telemetry dict to a single .npz file.

    Each topic is flattened to ``<topic>__t_ns``, ``<topic>__values``,
    ``<topic>__fields`` keys (with '/' replaced by '.').
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flat: Dict[str, np.ndarray] = {}
    for topic, ts in telemetry.items():
        safe = topic.strip("/").replace("/", ".")
        flat[f"{safe}__t_ns"] = np.asarray(ts["t_ns"])
        flat[f"{safe}__values"] = np.asarray(ts["values"])
        flat[f"{safe}__fields"] = np.asarray(ts["fields"], dtype=object)
    np.savez_compressed(path, **flat)
