# black-box-bench

Benchmark suite for robot forensic-analysis agents. Feed an agent a ROS bag plus controller source; score its root-cause hypothesis, the temporal window it flags, and the patch it proposes. MIT.

Companion to [Black Box](../) — the forensic copilot this benchmark was built to stress-test.

## Structure

- `cases/` — one dir per case:
  - `bag/` — ROS1 or ROS2 bag (or symlink). Skeleton cases ship without a bag until the bundle lands.
  - `ground_truth.json` — `{ bug_class, window_s, evidence_hints, patch_target: {file, function}, patch_hint }`.
  - `source/` — controller source with the injected bug (synthetic cases only).
  - `telemetry.npz` — key topic time-series, already extracted (synthetic cases only, fast to load in CI).
  - `video_prompts.md` — text prompts to regenerate the visual side on Wan 2.2 / Nano Banana, no bundled MP4 (synthetic cases).
  - `README.md` — human-readable case summary.
- `scripts/score.py` — scoring harness.
- `runs/` — prediction JSON files per case. `runs/sample/` ships reference predictions.
- `results/` — committed eval tables. See `results/sample_eval_2026-04-22.md`.

## Scoring (max 2.0 per case)

| Axis | Weight | Rule |
|------|--------|------|
| Root cause match | 1.0 | Predicted `bug_class` equals ground-truth key exactly |
| Temporal window | 0.5 | IoU over `window_s` ≥ 0.5 |
| Patch target | 0.5 | Predicted `patch.file` (basename) + `patch.function` match ground truth |

Skeleton cases (`status: skeleton_awaiting_bag`) are excluded from totals.

## Cases

### Scoreable (synthetic, ground-truth authoritative)
- `pid_saturation_01` — PID wind-up → pose divergence.
- `sensor_timeout_01` — stale lidar frames → phantom obstacle maneuvers.
- `bad_gain_01` — `Kp` too high → heading limit cycle.

### Scoreable (real bag, ground-truth derived from sensor cross-check)
- `rtk_heading_break_01` — real ROS 1 car session (~1 h). Rover dual-antenna RTK heading never valid entire bag; moving base healthy. Operator-reported "GPS fails under tunnel" is the anti-hypothesis — pipeline must disagree. Tests grounding + cross-source reasoning on unlabelled real data.

### Skeletons (awaiting bag ingestion)
- `boat_lidar_01` — USV (ROS 2) with LiDAR; forensic or scenario-mining TBD on first real bag.
- `sensor_drop_cameras_01` — multi-camera simultaneous drop on autonomous car.
- `reflect_public_01` — [REFLECT](https://github.com/real-stanford/reflect) public-dataset case for Tier-2 coverage.

## Prediction JSON shape

```json
{
  "bug_class": "pid_saturation",
  "window_s": [12.3, 17.8],
  "patch": {"file": "source/buggy/pid_controller.py", "function": "PIDController.step"}
}
```

## Run the harness

```bash
# Score one case:
python scripts/score.py --case cases/pid_saturation_01 --prediction runs/sample/pid_saturation_01.json

# Score every case against a predictions dir:
python scripts/score.py --all --predictions-dir runs/sample
```

Sample run on 2026-04-22: 6.00 / 6.00 on the 3 scoreable cases. See `results/sample_eval_2026-04-22.md`.

## License

MIT — see `LICENSE`. Use this to benchmark your own robot-forensic agent.
