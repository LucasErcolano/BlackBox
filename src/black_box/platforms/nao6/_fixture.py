"""Deterministic synthetic NAO6 forward-fall fixture.

Writes real MP4 + CSV + .py artifacts to disk so the adapter runs the same
code path it would on tomorrow's real recordings. No randomness — any math
uses fixed constants so tests are reproducible.
"""

from __future__ import annotations

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
