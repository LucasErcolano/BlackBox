# SPDX-License-Identifier: MIT
"""NAO6 walking gait controller.

Drives a simple alternating-step cycle via per-joint PID on the six sagittal
leg joints. Joint targets are radians (NAOqi convention, positive = flexion
forward for pitch joints). Commanded at 50 Hz from the main control loop.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class GaitState(Enum):
    IDLE = "idle"
    STEP_LEFT = "step_left"
    STEP_RIGHT = "step_right"


# Per-joint gains. HipPitch drives step initiation; Knee/Ankle handle lift + land.
# NOTE: kp on HipPitch was bumped during indoor tuning to hit step cadence.
_GAINS: dict[str, tuple[float, float, float]] = {
    "LHipPitch":    (18.0, 0.4, 0.9),
    "RHipPitch":    (18.0, 0.4, 0.9),
    "LKneePitch":   ( 9.5, 0.3, 0.6),
    "RKneePitch":   ( 9.5, 0.3, 0.6),
    "LAnklePitch":  ( 8.0, 0.2, 0.5),
    "RAnklePitch":  ( 8.0, 0.2, 0.5),
}

# Swing / stance targets in radians. Mirror across legs during alternation.
_SWING_HIP = 0.45
_SWING_KNEE = 0.70
_SWING_ANKLE = -0.25
_STANCE_HIP = 0.10
_STANCE_KNEE = 0.15
_STANCE_ANKLE = -0.05

_STEP_DURATION_S = 0.55


@dataclass
class _PID:
    kp: float
    ki: float
    kd: float
    integral: float = 0.0
    last_err: float = 0.0

    def step(self, err: float, dt: float) -> float:
        self.integral += err * dt
        deriv = (err - self.last_err) / max(dt, 1e-6)
        self.last_err = err
        return self.kp * err + self.ki * self.integral + self.kd * deriv


@dataclass
class WalkingGait:
    state: GaitState = GaitState.IDLE
    t_in_state: float = 0.0
    pids: dict[str, _PID] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.pids:
            self.pids = {name: _PID(*g) for name, g in _GAINS.items()}

    def targets_for_state(self) -> dict[str, float]:
        if self.state is GaitState.STEP_LEFT:
            return {
                "LHipPitch": _SWING_HIP,   "LKneePitch": _SWING_KNEE,  "LAnklePitch": _SWING_ANKLE,
                "RHipPitch": _STANCE_HIP,  "RKneePitch": _STANCE_KNEE, "RAnklePitch": _STANCE_ANKLE,
            }
        if self.state is GaitState.STEP_RIGHT:
            return {
                "LHipPitch": _STANCE_HIP,  "LKneePitch": _STANCE_KNEE, "LAnklePitch": _STANCE_ANKLE,
                "RHipPitch": _SWING_HIP,   "RKneePitch": _SWING_KNEE,  "RAnklePitch": _SWING_ANKLE,
            }
        return {name: 0.0 for name in _GAINS}

    def _advance_state(self, dt: float) -> None:
        self.t_in_state += dt
        if self.state is GaitState.IDLE:
            self.state = GaitState.STEP_LEFT
            self.t_in_state = 0.0
            return
        if self.t_in_state >= _STEP_DURATION_S:
            self.state = (
                GaitState.STEP_RIGHT if self.state is GaitState.STEP_LEFT else GaitState.STEP_LEFT
            )
            self.t_in_state = 0.0

    def step(self, measured: dict[str, float], dt: float) -> dict[str, float]:
        self._advance_state(dt)
        targets = self.targets_for_state()
        cmd: dict[str, float] = {}
        for joint, target in targets.items():
            err = target - measured.get(joint, 0.0)
            cmd[joint] = self.pids[joint].step(err, dt)
        return cmd

    def stop(self) -> dict[str, float]:
        self.state = GaitState.IDLE
        self.t_in_state = 0.0
        for pid in self.pids.values():
            pid.integral = 0.0
            pid.last_err = 0.0
        return {name: 0.0 for name in _GAINS}


def phase_angle(t_s: float) -> float:
    return (2.0 * math.pi * t_s) / (2.0 * _STEP_DURATION_S)
