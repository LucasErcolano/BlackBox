"""Obstacle avoider consuming cached laser scans (CLEAN)."""

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
