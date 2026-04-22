# black-box-bench

Benchmark suite for robot forensic-analysis agents. MIT.

## Structure
- `cases/` — one dir per case. Each contains:
  - `bag/` — ROS1 or ROS2 bag (or symlink).
  - `ground_truth.json` — `{ "bug": "<taxonomy_key>", "window_s": [start, end], "evidence": [...], "patch_hint": "..." }`.
  - `source/` — controller source with the injected bug.
  - `README.md` — human-readable case summary.
- `scripts/` — loaders, scoring harness.

## Scoring
- Root cause match (exact bug key) — 1.0.
- Window overlap IoU ≥ 0.5 — 0.5.
- Patch touches the correct file+function — 0.5.

Max 2.0 per case.

## Cases (planned)
- `pid_saturation_01` — PID wind-up → pose divergence.
- `sensor_timeout_01` — stale lidar frames → phantom obstacle.
- `bad_gain_01` — P too high → oscillation.
