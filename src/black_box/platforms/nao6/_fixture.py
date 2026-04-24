# SPDX-License-Identifier: MIT
"""Deterministic synthetic NAO6 fall fixtures.

Writes real MP4 + CSV + .py artifacts to disk so the adapter runs the same
code path it would on tomorrow's real recordings. No randomness — any math
uses fixed constants so tests are reproducible.

Scenarios:
  generate_fall_fixture              — forward faceplant from PID wind-up
  generate_lateral_tip_fixture       — sideways tip from weak roll gain
  generate_stumble_recovery_fail_fixture — teeter then topple from stuck recovery FSM
"""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np


# Scenario constants
_FPS = 10
_DURATION_S = 3
_TOTAL_FRAMES = _FPS * _DURATION_S  # 30
_WIDTH = 320
_HEIGHT = 240
_TELE_HZ = 100


def generate_fall_fixture(out_dir: Path) -> dict[str, Path]:
    """Emit a reproducible NAO6 forward-fall scenario on disk.

    Produces:
      top_video.mp4   — gradient scene that rotates with robot pitch
      bottom_video.mp4 — floor texture progressively occluded by collapse
      telemetry.csv   — IMU-style time series + one non-numeric state key
      controller.py   — toy balance controller with an intentional PID wind-up

    Returns paths keyed as: top_video, bottom_video, telemetry_csv, controller_source.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    top_path = out_dir / "top_video.mp4"
    bottom_path = out_dir / "bottom_video.mp4"
    tele_path = out_dir / "telemetry.csv"
    ctrl_path = out_dir / "controller.py"

    _write_top_video(top_path)
    _write_bottom_video(bottom_path)
    _write_telemetry(tele_path)
    _write_controller(ctrl_path)

    return {
        "top_video": top_path,
        "bottom_video": bottom_path,
        "telemetry_csv": tele_path,
        "controller_source": ctrl_path,
    }


# ---- video writers ---------------------------------------------------------


def _fourcc() -> int:
    # mp4v is the most portable cv2 MP4 fourcc; avoids external codecs.
    return cv2.VideoWriter_fourcc(*"mp4v")


def _write_top_video(path: Path) -> None:
    vw = cv2.VideoWriter(str(path), _fourcc(), _FPS, (_WIDTH, _HEIGHT))
    try:
        # Base horizon: upper sky band, lower ground band.
        sky = np.full((_HEIGHT, _WIDTH, 3), (200, 160, 90), dtype=np.uint8)  # BGR bluish
        ground = np.full((_HEIGHT, _WIDTH, 3), (60, 90, 40), dtype=np.uint8)  # dark green
        horizon = _HEIGHT // 2
        base = sky.copy()
        base[horizon:] = ground[horizon:]

        for i in range(_TOTAL_FRAMES):
            # Stable for first 2s, then rotate linearly to -60deg as robot pitches forward
            t_s = i / _FPS
            if t_s < 2.0:
                angle_deg = 0.0
            else:
                frac = (t_s - 2.0) / 1.0
                angle_deg = -60.0 * frac
            m = cv2.getRotationMatrix2D((_WIDTH / 2, _HEIGHT / 2), angle_deg, 1.0)
            rotated = cv2.warpAffine(base, m, (_WIDTH, _HEIGHT), borderValue=(0, 0, 0))
            vw.write(rotated)
    finally:
        vw.release()


def _write_bottom_video(path: Path) -> None:
    vw = cv2.VideoWriter(str(path), _fourcc(), _FPS, (_WIDTH, _HEIGHT))
    try:
        # Floor texture: checkerboard
        floor = np.zeros((_HEIGHT, _WIDTH, 3), dtype=np.uint8)
        tile = 40
        for y in range(0, _HEIGHT, tile):
            for x in range(0, _WIDTH, tile):
                if ((x // tile) + (y // tile)) % 2 == 0:
                    floor[y : y + tile, x : x + tile] = (180, 180, 180)
                else:
                    floor[y : y + tile, x : x + tile] = (110, 110, 110)

        for i in range(_TOTAL_FRAMES):
            t_s = i / _FPS
            frame = floor.copy()
            # Occlusion grows from top as the robot tips forward onto its face
            if t_s < 2.0:
                occl_px = 0
            else:
                frac = (t_s - 2.0) / 1.0
                occl_px = int(frac * _HEIGHT)
            if occl_px > 0:
                frame[:occl_px] = (20, 20, 20)
            vw.write(frame)
    finally:
        vw.release()


# ---- telemetry -------------------------------------------------------------


def _write_telemetry(path: Path) -> None:
    samples = _TELE_HZ * _DURATION_S  # 300
    dt_ns = int(1e9 / _TELE_HZ)

    rows: list[tuple[int, str, str]] = []
    for i in range(samples):
        t_ns = i * dt_ns
        t_s = i / _TELE_HZ

        # AngleY: 0.02 rad for 2s, then linear ramp to 0.8 rad over the final 1s
        if t_s < 2.0:
            angle_y = 0.02
        else:
            frac = (t_s - 2.0) / 1.0
            angle_y = 0.02 + (0.8 - 0.02) * frac
        rows.append((t_ns, "InertialSensor/AngleY/Sensor/Value", f"{angle_y:.6f}"))

        # GyrY: ~0 for 2s, -3.0 rad/s during fall
        gyr_y = 0.0 if t_s < 2.0 else -3.0
        rows.append((t_ns, "GyrY", f"{gyr_y:.6f}"))

        # AccZ: -9.81 nominal, -3.0 freefall mid-fall, hard negative spike at impact
        if t_s < 2.0:
            acc_z = -9.81
        elif t_s < 2.8:
            acc_z = -3.0
        elif t_s < 2.9:
            acc_z = -40.0  # impact spike
        else:
            acc_z = -9.81
        rows.append((t_ns, "AccZ", f"{acc_z:.6f}"))

        # Non-numeric state key — adapter must skip these without crashing.
        state = "standing" if t_s < 2.0 else "falling"
        rows.append((t_ns, "BalanceController/State", state))

    with path.open("w", newline="") as f:
        w = __import__("csv").writer(f)
        w.writerow(["t_ns", "key", "value"])
        for row in rows:
            w.writerow(row)


# ---- controller source -----------------------------------------------------


_CONTROLLER_SRC = '''"""Toy NAO6 balance controller.

BUG (intentional, for synthetic QA — bug_class: pid_saturation):
The PID integral term is never reset when the state transitions from
"standing" to "falling". Under a sustained forward pitch error the
integral winds up without bound and the commanded ankle torque saturates
the actuator, so the recovery step never fires.
"""

from __future__ import annotations


class BalancePID:
    def __init__(self, kp: float = 4.0, ki: float = 1.5, kd: float = 0.2) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral = 0.0
        self.last_err = 0.0
        self.state = "standing"

    def step(self, angle_y: float, dt: float) -> float:
        err = 0.0 - angle_y  # setpoint = upright
        self.integral += err * dt  # BUG: never clamped, never reset on state switch
        deriv = (err - self.last_err) / max(dt, 1e-6)
        self.last_err = err
        if abs(angle_y) > 0.25:
            self.state = "falling"
        torque = self.kp * err + self.ki * self.integral + self.kd * deriv
        return torque
'''


def _write_controller(path: Path) -> None:
    path.write_text(_CONTROLLER_SRC, encoding="utf-8")


# ---- shared helpers for variant scenarios ----------------------------------


def _build_horizon_base() -> np.ndarray:
    """Sky over ground base image (same look as the forward-fall top video)."""
    sky = np.full((_HEIGHT, _WIDTH, 3), (200, 160, 90), dtype=np.uint8)
    ground = np.full((_HEIGHT, _WIDTH, 3), (60, 90, 40), dtype=np.uint8)
    base = sky.copy()
    base[_HEIGHT // 2 :] = ground[_HEIGHT // 2 :]
    return base


def _build_checkerboard_floor() -> np.ndarray:
    floor = np.zeros((_HEIGHT, _WIDTH, 3), dtype=np.uint8)
    tile = 40
    for y in range(0, _HEIGHT, tile):
        for x in range(0, _WIDTH, tile):
            if ((x // tile) + (y // tile)) % 2 == 0:
                floor[y : y + tile, x : x + tile] = (180, 180, 180)
            else:
                floor[y : y + tile, x : x + tile] = (110, 110, 110)
    return floor


def _write_csv(path: Path, rows: list[tuple[int, str, str]]) -> None:
    import csv as _csv

    with path.open("w", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["t_ns", "key", "value"])
        for row in rows:
            w.writerow(row)


# ---- Scenario A: lateral tip-over ------------------------------------------


def generate_lateral_tip_fixture(out_dir: Path) -> dict[str, Path]:
    """Emit a reproducible NAO6 lateral (sideways) tip-over scenario.

    Roll (AngleX) ramps while pitch stays flat. Top camera rolls about its
    optical axis; bottom camera gets occluded from the LEFT as the robot
    tips onto its side. Controller bug: weak Kp_roll — bad_gain_tuning.

    Returns paths keyed as: top_video, bottom_video, telemetry_csv, controller_source.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    top_path = out_dir / "top_video.mp4"
    bottom_path = out_dir / "bottom_video.mp4"
    tele_path = out_dir / "telemetry.csv"
    ctrl_path = out_dir / "controller.py"

    _write_top_video_lateral(top_path)
    _write_bottom_video_lateral(bottom_path)
    _write_telemetry_lateral(tele_path)
    ctrl_path.write_text(_CONTROLLER_LATERAL_SRC, encoding="utf-8")

    return {
        "top_video": top_path,
        "bottom_video": bottom_path,
        "telemetry_csv": tele_path,
        "controller_source": ctrl_path,
    }


def _write_top_video_lateral(path: Path) -> None:
    vw = cv2.VideoWriter(str(path), _fourcc(), _FPS, (_WIDTH, _HEIGHT))
    try:
        base = _build_horizon_base()
        for i in range(_TOTAL_FRAMES):
            t_s = i / _FPS
            # Stable 1.5s, then roll to +70deg over remaining 1.5s (horizon tilts left)
            if t_s < 1.5:
                angle_deg = 0.0
            else:
                frac = (t_s - 1.5) / 1.5
                angle_deg = 70.0 * frac
            m = cv2.getRotationMatrix2D((_WIDTH / 2, _HEIGHT / 2), angle_deg, 1.0)
            rotated = cv2.warpAffine(base, m, (_WIDTH, _HEIGHT), borderValue=(0, 0, 0))
            vw.write(rotated)
    finally:
        vw.release()


def _write_bottom_video_lateral(path: Path) -> None:
    vw = cv2.VideoWriter(str(path), _fourcc(), _FPS, (_WIDTH, _HEIGHT))
    try:
        floor = _build_checkerboard_floor()
        for i in range(_TOTAL_FRAMES):
            t_s = i / _FPS
            frame = floor.copy()
            # Occlusion sweeps in from the LEFT as the robot lies on its side
            if t_s < 1.5:
                occl_px = 0
            else:
                frac = (t_s - 1.5) / 1.5
                occl_px = int(frac * _WIDTH)
            if occl_px > 0:
                frame[:, :occl_px] = (20, 20, 20)
            vw.write(frame)
    finally:
        vw.release()


def _write_telemetry_lateral(path: Path) -> None:
    samples = _TELE_HZ * _DURATION_S
    dt_ns = int(1e9 / _TELE_HZ)
    rows: list[tuple[int, str, str]] = []
    for i in range(samples):
        t_ns = i * dt_ns
        t_s = i / _TELE_HZ

        # AngleX (roll): 0.01 rad for 1.5s, then ramp to 0.9 rad
        if t_s < 1.5:
            angle_x = 0.01
        else:
            frac = (t_s - 1.5) / 1.5
            angle_x = 0.01 + (0.9 - 0.01) * frac
        rows.append((t_ns, "InertialSensor/AngleX/Sensor/Value", f"{angle_x:.6f}"))

        # GyrX: ~0 for 1.5s, then +2.7 rad/s as robot rolls sideways
        gyr_x = 0.0 if t_s < 1.5 else 2.7
        rows.append((t_ns, "GyrX", f"{gyr_x:.6f}"))

        # AccZ: nominal, freefall dip, impact spike, rest
        if t_s < 1.5:
            acc_z = -9.81
        elif t_s < 2.7:
            acc_z = -4.0
        elif t_s < 2.8:
            acc_z = -38.0
        else:
            acc_z = -9.81
        rows.append((t_ns, "AccZ", f"{acc_z:.6f}"))

        state = "standing" if t_s < 1.5 else "tipping"
        rows.append((t_ns, "BalanceController/State", state))

    _write_csv(path, rows)


_CONTROLLER_LATERAL_SRC = '''"""Toy NAO6 lateral balance controller.

BUG (intentional, for synthetic QA — bug_class: bad_gain_tuning):
The roll-axis proportional gain (kp_roll) was copy-pasted from an early
prototype at 0.8 when the tuned value should be ~4.0. Under a real
lateral disturbance the commanded hip-roll correction is ~5x too small,
so the robot tips sideways faster than the controller can restore it.
"""

from __future__ import annotations


class LateralBalancePID:
    def __init__(self, kp_roll: float = 0.8, ki_roll: float = 0.2, kd_roll: float = 0.1) -> None:
        # BUG: kp_roll=0.8 is the un-tuned prototype value; sane value ~= 4.0
        self.kp_roll = kp_roll
        self.ki_roll = ki_roll
        self.kd_roll = kd_roll
        self.integral = 0.0
        self.last_err = 0.0
        self.state = "standing"

    def step(self, angle_x: float, dt: float) -> float:
        err = 0.0 - angle_x  # setpoint = upright about the roll axis
        self.integral += err * dt
        deriv = (err - self.last_err) / max(dt, 1e-6)
        self.last_err = err
        if abs(angle_x) > 0.2:
            self.state = "tipping"
        # Under-gained response — will not arrest the tip in time.
        hip_roll_torque = self.kp_roll * err + self.ki_roll * self.integral + self.kd_roll * deriv
        return hip_roll_torque
'''


# ---- Scenario B: stumble + recovery-deadlock -------------------------------


def generate_stumble_recovery_fail_fixture(out_dir: Path) -> dict[str, Path]:
    """Emit a reproducible NAO6 stumble -> failed recovery scenario.

    Pitch oscillates for 1.5s (teeter), then ramps forward as the robot
    slowly topples. The controller enters RECOVERING and deadlocks.
    Bug_class: state_machine_deadlock.

    Returns paths keyed as: top_video, bottom_video, telemetry_csv, controller_source.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    top_path = out_dir / "top_video.mp4"
    bottom_path = out_dir / "bottom_video.mp4"
    tele_path = out_dir / "telemetry.csv"
    ctrl_path = out_dir / "controller.py"

    _write_top_video_stumble(top_path)
    _write_bottom_video_stumble(bottom_path)
    _write_telemetry_stumble(tele_path)
    ctrl_path.write_text(_CONTROLLER_STUMBLE_SRC, encoding="utf-8")

    return {
        "top_video": top_path,
        "bottom_video": bottom_path,
        "telemetry_csv": tele_path,
        "controller_source": ctrl_path,
    }


def _write_top_video_stumble(path: Path) -> None:
    vw = cv2.VideoWriter(str(path), _fourcc(), _FPS, (_WIDTH, _HEIGHT))
    try:
        base = _build_horizon_base()
        for i in range(_TOTAL_FRAMES):
            t_s = i / _FPS
            if t_s < 1.5:
                # Small pitch oscillation — ~+/-8 deg at 2 Hz
                angle_deg = -8.0 * math.sin(2.0 * math.pi * 2.0 * t_s)
            else:
                # Monotonic forward pitch: 0 -> -55 deg over last 1.5s
                frac = (t_s - 1.5) / 1.5
                angle_deg = -55.0 * frac
            m = cv2.getRotationMatrix2D((_WIDTH / 2, _HEIGHT / 2), angle_deg, 1.0)
            rotated = cv2.warpAffine(base, m, (_WIDTH, _HEIGHT), borderValue=(0, 0, 0))
            vw.write(rotated)
    finally:
        vw.release()


def _write_bottom_video_stumble(path: Path) -> None:
    vw = cv2.VideoWriter(str(path), _fourcc(), _FPS, (_WIDTH, _HEIGHT))
    try:
        floor = _build_checkerboard_floor()
        for i in range(_TOTAL_FRAMES):
            t_s = i / _FPS
            frame = floor.copy()
            # Stable for the teeter phase, then gradual top-down occlusion
            if t_s < 1.5:
                occl_px = 0
            else:
                frac = (t_s - 1.5) / 1.5
                occl_px = int(frac * _HEIGHT)
            if occl_px > 0:
                frame[:occl_px] = (20, 20, 20)
            vw.write(frame)
    finally:
        vw.release()


def _write_telemetry_stumble(path: Path) -> None:
    samples = _TELE_HZ * _DURATION_S
    dt_ns = int(1e9 / _TELE_HZ)
    rows: list[tuple[int, str, str]] = []
    for i in range(samples):
        t_ns = i * dt_ns
        t_s = i / _TELE_HZ

        # AngleY: sine oscillation (amplitude 0.15 rad) for 1.5s, then ramp to 0.75 rad
        if t_s < 1.5:
            angle_y = 0.15 * math.sin(2.0 * math.pi * 2.0 * t_s)
        else:
            frac = (t_s - 1.5) / 1.5
            angle_y = 0.0 + (0.75 - 0.0) * frac
        rows.append((t_ns, "InertialSensor/AngleY/Sensor/Value", f"{angle_y:.6f}"))

        # GyrY tracks the derivative roughly: oscillating, then steady negative
        if t_s < 1.5:
            gyr_y = 0.15 * 2.0 * math.pi * 2.0 * math.cos(2.0 * math.pi * 2.0 * t_s)
        else:
            gyr_y = -2.2
        rows.append((t_ns, "GyrY", f"{gyr_y:.6f}"))

        # AccZ: nominal with brief freefall when toppling begins, impact near end
        if t_s < 1.5:
            acc_z = -9.81
        elif t_s < 2.7:
            acc_z = -5.0
        elif t_s < 2.8:
            acc_z = -36.0
        else:
            acc_z = -9.81
        rows.append((t_ns, "AccZ", f"{acc_z:.6f}"))

        # State machine: standing -> teetering -> recovering -> fell.
        # Notice: once "recovering" appears, it never returns to "standing".
        if t_s < 0.8:
            state = "standing"
        elif t_s < 1.5:
            state = "teetering"
        elif t_s < 2.7:
            state = "recovering"
        else:
            state = "fell"
        rows.append((t_ns, "BalanceController/State", state))

    _write_csv(path, rows)


_CONTROLLER_STUMBLE_SRC = '''"""Toy NAO6 stumble-recovery FSM.

BUG (intentional, for synthetic QA — bug_class: state_machine_deadlock):
The controller transitions STANDING -> TEETERING -> RECOVERING on a
stumble, and is supposed to return to STANDING when |angle_y| drops
back below a small threshold. There is no timeout and no fall-back
branch, so if the recovery condition never fires the controller stays
in RECOVERING forever while the robot slowly topples.
"""

from __future__ import annotations


STANDING = "standing"
TEETERING = "teetering"
RECOVERING = "recovering"


class StumbleFSM:
    def __init__(self) -> None:
        self.state = STANDING
        self.teeter_thresh = 0.10
        self.recover_thresh = 0.02  # never reached once the robot begins to topple

    def step(self, angle_y: float, dt: float) -> float:
        if self.state == STANDING:
            if abs(angle_y) > self.teeter_thresh:
                self.state = TEETERING
        elif self.state == TEETERING:
            if abs(angle_y) > self.teeter_thresh * 1.2:
                self.state = RECOVERING
        elif self.state == RECOVERING:
            # BUG: only way out is recover_thresh; no timeout, no "give up and brace"
            # branch. Once angle_y drifts past teeter_thresh monotonically, we are stuck.
            if abs(angle_y) < self.recover_thresh:
                self.state = STANDING

        # Simple proportional response regardless of state — fine on paper,
        # but since we never leave RECOVERING the higher-level planner waits
        # on a state it will never see.
        return -3.0 * angle_y
'''
