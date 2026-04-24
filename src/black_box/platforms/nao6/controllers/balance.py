# SPDX-License-Identifier: MIT
"""NAO6 balance / fall-prevention controller.

Reads body-frame attitude from the onboard IMU (InertialSensor) and blends a
reactive ankle-strategy torque with a hip nudge when the robot starts to tip.
Runs at 100 Hz from the behavior manager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BalanceState(Enum):
    UPRIGHT = "UPRIGHT"
    TEETERING = "TEETERING"
    FALL_IMMINENT = "FALL_IMMINENT"
    RECOVERING = "RECOVERING"


# Thresholds in radians (body-frame) and rad/s (gyro).
_TEETER_ANGLE = 0.12
_IMMINENT_ANGLE = 0.28
_TEETER_GYRO = 0.9
_IMMINENT_GYRO = 2.0

# Recovery torque limits (NAOqi ankle stiffness is clamped to [0, 1] on the API
# side; these are internal torque-equivalent scalars that map to that range).
_ANKLE_TORQUE_MAX = 1.0
_HIP_NUDGE_MAX = 0.6


@dataclass
class BalanceController:
    state: BalanceState = BalanceState.UPRIGHT
    t_in_state: float = 0.0
    last_ankle_cmd: float = 0.0
    last_hip_cmd: float = 0.0
    _prev_state: BalanceState = field(default=BalanceState.UPRIGHT)

    def _classify(self, angle_x: float, angle_y: float, gyr_x: float, gyr_y: float) -> BalanceState:
        tilt = max(abs(angle_x), abs(angle_y))
        rate = max(abs(gyr_x), abs(gyr_y))
        if tilt >= _IMMINENT_ANGLE or rate >= _IMMINENT_GYRO:
            return BalanceState.FALL_IMMINENT
        if tilt >= _TEETER_ANGLE or rate >= _TEETER_GYRO:
            return BalanceState.TEETERING
        return BalanceState.UPRIGHT

    def _ankle_strategy(self, angle_y: float, gyr_y: float) -> float:
        # Simple PD on pitch: push ankles in the opposite direction of tilt.
        cmd = -(4.5 * angle_y + 0.6 * gyr_y)
        if cmd > _ANKLE_TORQUE_MAX:
            cmd = _ANKLE_TORQUE_MAX
        elif cmd < -_ANKLE_TORQUE_MAX:
            cmd = -_ANKLE_TORQUE_MAX
        return cmd

    def _hip_nudge(self, angle_x: float) -> float:
        cmd = -(3.0 * angle_x)
        if cmd > _HIP_NUDGE_MAX:
            cmd = _HIP_NUDGE_MAX
        elif cmd < -_HIP_NUDGE_MAX:
            cmd = -_HIP_NUDGE_MAX
        return cmd

    def step(
        self,
        angle_x: float,
        angle_y: float,
        gyr_x: float,
        gyr_y: float,
        dt: float,
    ) -> dict[str, float]:
        observed = self._classify(angle_x, angle_y, gyr_x, gyr_y)

        # Transition table. UPRIGHT is re-entered only when fully settled.
        if self.state is BalanceState.UPRIGHT:
            if observed is not BalanceState.UPRIGHT:
                self.state = observed
                self.t_in_state = 0.0
        elif self.state is BalanceState.TEETERING:
            if observed is BalanceState.FALL_IMMINENT:
                self.state = BalanceState.FALL_IMMINENT
                self.t_in_state = 0.0
            elif observed is BalanceState.UPRIGHT:
                self.state = BalanceState.UPRIGHT
                self.t_in_state = 0.0
        elif self.state is BalanceState.FALL_IMMINENT:
            # Engage active recovery; once engaged we drive RECOVERING until upright.
            self.state = BalanceState.RECOVERING
            self.t_in_state = 0.0
        elif self.state is BalanceState.RECOVERING:
            # Exit recovery only when the IMU reports upright again.
            if observed is BalanceState.UPRIGHT:
                self.state = BalanceState.UPRIGHT
                self.t_in_state = 0.0

        self.t_in_state += dt

        ankle = self._ankle_strategy(angle_y, gyr_y)
        hip = self._hip_nudge(angle_x) if self.state is not BalanceState.UPRIGHT else 0.0
        if self.state is BalanceState.UPRIGHT:
            ankle *= 0.25  # light trim only

        self.last_ankle_cmd = ankle
        self.last_hip_cmd = hip
        return {"ankle_pitch_torque": ankle, "hip_roll_nudge": hip}
