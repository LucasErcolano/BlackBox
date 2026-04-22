"""Proportional heading controller (BUGGY — gain too aggressive)."""

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
