# sensor_timeout_01

**Bug class:** `sensor_timeout`
**Ground-truth window:** 10.0s – 14.0s

## Telemetry topics
  - `/scan_range` fields=['range']
  - `/imu/accel` fields=['ax', 'ay', 'az']
  - `/cmd_vel` fields=['linear', 'angular']
  - `/reference` fields=['x', 'y', 'yaw']

## Files

- `ground_truth.json` — machine-readable labels for eval.
- `telemetry.npz` — numpy arrays (use `np.load(..., allow_pickle=True)`).
- `source/buggy/` — the controller as shipped; reproduces the bug.
- `source/clean/` — intended fix; compare for patch diff demo.
- `video_prompts.md` — prompts for Nano Banana Pro (stills) and Wan 2.2 (clips).

## Evidence hints
- /scan_range is bit-exactly constant between 10.0s and 13.0s
- /imu/accel continues normally (sensor subsystem alive)
- /cmd_vel angular spikes to +/- 2.5 rad/s with no visible obstacle

## Patch hint
In ObstacleAvoider.step, compare (time.time() - self.last_scan_t) against a SCAN_TIMEOUT_S constant and fall back to a conservative crawl (low linear, zero angular) when the scan is stale.
