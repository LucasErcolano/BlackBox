"""Source-code artifacts: buggy vs clean controller templates.

These files are not executed. They exist so the post-mortem agent can emit a
scoped unified diff as a patch proposal.
"""

from __future__ import annotations

from typing import Dict

# -----------------------------------------------------------------------------
# PID saturation (integral windup)
# -----------------------------------------------------------------------------

PID_BUGGY = '''"""Toy PID controller for a differential-drive robot (BUGGY)."""

import time


PWM_MAX = 255
PWM_MIN = 0


class PIDController:
    def __init__(self, kp: float = 1.2, ki: float = 0.4, kd: float = 0.05):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral = 0.0
        self.prev_err = 0.0
        self.prev_t = None

    def reset(self) -> None:
        self.integral = 0.0
        self.prev_err = 0.0
        self.prev_t = None

    def step(self, setpoint: float, measured: float) -> float:
        now = time.time()
        dt = 0.02 if self.prev_t is None else max(1e-3, now - self.prev_t)
        err = setpoint - measured

        # BUG: integral accumulates even when output saturates -> windup.
        self.integral += err * dt
        derivative = (err - self.prev_err) / dt
        u = self.kp * err + self.ki * self.integral + self.kd * derivative

        # clamp actuator output only
        u_cmd = max(PWM_MIN, min(PWM_MAX, u))

        self.prev_err = err
        self.prev_t = now
        return u_cmd
'''


PID_CLEAN = '''"""Toy PID controller for a differential-drive robot (CLEAN)."""

import time


PWM_MAX = 255
PWM_MIN = 0


class PIDController:
    def __init__(self, kp: float = 1.2, ki: float = 0.4, kd: float = 0.05):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.integral = 0.0
        self.prev_err = 0.0
        self.prev_t = None

    def reset(self) -> None:
        self.integral = 0.0
        self.prev_err = 0.0
        self.prev_t = None

    def step(self, setpoint: float, measured: float) -> float:
        now = time.time()
        dt = 0.02 if self.prev_t is None else max(1e-3, now - self.prev_t)
        err = setpoint - measured

        # Tentative integral and output
        tentative_integral = self.integral + err * dt
        derivative = (err - self.prev_err) / dt
        u = self.kp * err + self.ki * tentative_integral + self.kd * derivative
        u_cmd = max(PWM_MIN, min(PWM_MAX, u))

        # Anti-windup: only accumulate when not saturated (or when err pushes away from rail)
        saturated_high = u >= PWM_MAX and err > 0
        saturated_low = u <= PWM_MIN and err < 0
        if not (saturated_high or saturated_low):
            self.integral = tentative_integral

        self.prev_err = err
        self.prev_t = now
        return u_cmd
'''


# -----------------------------------------------------------------------------
# Sensor timeout (missing freshness check)
# -----------------------------------------------------------------------------

OBSTACLE_BUGGY = '''"""Obstacle avoider consuming cached laser scans (BUGGY)."""

import time


SAFE_RANGE_M = 0.6
CRUISE_LINEAR = 0.4
REACT_ANGULAR = 2.5


class ObstacleAvoider:
    def __init__(self) -> None:
        self.last_scan = None          # scalar range in meters
        self.last_scan_t = 0.0

    def on_scan(self, range_m: float) -> None:
        self.last_scan = float(range_m)
        self.last_scan_t = time.time()

    def step(self) -> tuple[float, float]:
        # BUG: uses self.last_scan without checking its age.
        # Stale scan => phantom obstacle => ballistic avoidance.
        scan = self.last_scan
        if scan is None:
            return 0.0, 0.0
        if scan < SAFE_RANGE_M:
            return 0.0, REACT_ANGULAR
        return CRUISE_LINEAR, 0.0
'''


OBSTACLE_CLEAN = '''"""Obstacle avoider consuming cached laser scans (CLEAN)."""

import time


SAFE_RANGE_M = 0.6
CRUISE_LINEAR = 0.4
REACT_ANGULAR = 2.5
SCAN_TIMEOUT_S = 0.3


class ObstacleAvoider:
    def __init__(self) -> None:
        self.last_scan = None          # scalar range in meters
        self.last_scan_t = 0.0

    def on_scan(self, range_m: float) -> None:
        self.last_scan = float(range_m)
        self.last_scan_t = time.time()

    def step(self) -> tuple[float, float]:
        scan = self.last_scan
        age = time.time() - self.last_scan_t
        if scan is None or age > SCAN_TIMEOUT_S:
            # Conservative fallback: slow crawl, no turn.
            return 0.05, 0.0
        if scan < SAFE_RANGE_M:
            return 0.0, REACT_ANGULAR
        return CRUISE_LINEAR, 0.0
'''


# -----------------------------------------------------------------------------
# Bad gain (Kp too high)
# -----------------------------------------------------------------------------

HEADING_BUGGY = '''"""Proportional heading controller (BUGGY — gain too aggressive)."""

import math


MAX_ANG_RATE = 3.0


class HeadingController:
    def __init__(self) -> None:
        # BUG: Kp is way too high for this platform; closed loop oscillates.
        self.Kp = 4.5

    def _wrap(self, a: float) -> float:
        return math.atan2(math.sin(a), math.cos(a))

    def step(self, yaw_meas: float, yaw_ref: float) -> float:
        err = self._wrap(yaw_ref - yaw_meas)
        cmd = self.Kp * err
        if cmd > MAX_ANG_RATE:
            cmd = MAX_ANG_RATE
        elif cmd < -MAX_ANG_RATE:
            cmd = -MAX_ANG_RATE
        return cmd
'''


HEADING_CLEAN = '''"""Proportional heading controller (CLEAN — conservative gain)."""

import math


MAX_ANG_RATE = 3.0


class HeadingController:
    def __init__(self) -> None:
        # Empirically tuned: 0.8 gives critical-ish response on this platform.
        self.Kp = 0.8

    def _wrap(self, a: float) -> float:
        return math.atan2(math.sin(a), math.cos(a))

    def step(self, yaw_meas: float, yaw_ref: float) -> float:
        err = self._wrap(yaw_ref - yaw_meas)
        # Guard: if error is tiny, stop commanding (prevents limit-cycling on noise)
        if abs(err) < 1e-3:
            return 0.0
        cmd = self.Kp * err
        if cmd > MAX_ANG_RATE:
            cmd = MAX_ANG_RATE
        elif cmd < -MAX_ANG_RATE:
            cmd = -MAX_ANG_RATE
        return cmd
'''


def buggy_sources() -> Dict[str, Dict[str, str]]:
    """Return {bug_class: {filename: code}} for buggy controllers."""
    return {
        "pid_saturation": {"pid_controller.py": PID_BUGGY},
        "sensor_timeout": {"obstacle_avoider.py": OBSTACLE_BUGGY},
        "bad_gain_tuning": {"heading_controller.py": HEADING_BUGGY},
    }


def clean_sources() -> Dict[str, Dict[str, str]]:
    """Return {bug_class: {filename: code}} for clean controllers."""
    return {
        "pid_saturation": {"pid_controller.py": PID_CLEAN},
        "sensor_timeout": {"obstacle_avoider.py": OBSTACLE_CLEAN},
        "bad_gain_tuning": {"heading_controller.py": HEADING_CLEAN},
    }
