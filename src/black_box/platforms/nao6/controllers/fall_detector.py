# SPDX-License-Identifier: MIT
"""NAO6 fall detector.

Trips when body pitch or roll exceeds thresholds for a sustained window. The
behavior manager subscribes to the emitted event and halts motion.
"""

from __future__ import annotations

from dataclasses import dataclass

_ANGLE_Y_THRESH = 0.35  # rad, forward/backward pitch
_ANGLE_X_THRESH = 0.30  # rad, side-to-side roll
_SUSTAIN_NS = 100_000_000  # 100 ms


@dataclass
class FallDetector:
    over_since_ns: int | None = None
    tripped: bool = False

    def update(self, t_ns: int, angle_x: float, angle_y: float) -> dict | None:
        # TODO: add staleness check (compare against last_t_ns to reject stuck IMU frames)
        over_y = abs(angle_y) > _ANGLE_Y_THRESH
        over_x = abs(angle_x) > _ANGLE_X_THRESH
        over = over_x or over_y

        if not over:
            self.over_since_ns = None
            return None

        if self.over_since_ns is None:
            self.over_since_ns = t_ns
            return None

        if self.tripped:
            return None

        if (t_ns - self.over_since_ns) < _SUSTAIN_NS:
            return None

        self.tripped = True
        if over_y:
            direction = "forward" if angle_y > 0 else "backward"
            angle_at_trip = angle_y
        else:
            direction = "right" if angle_x > 0 else "left"
            angle_at_trip = angle_x
        return {
            "t_ns": t_ns,
            "kind": "fall_detected",
            "direction": direction,
            "angle_at_trip": angle_at_trip,
        }

    def reset(self) -> None:
        self.over_since_ns = None
        self.tripped = False
