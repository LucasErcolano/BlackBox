"""Proportional heading controller (CLEAN — conservative gain)."""

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
