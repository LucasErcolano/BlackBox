"""Obstacle avoider consuming cached laser scans (BUGGY)."""

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
