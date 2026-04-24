# black-box-bench

Benchmark suite for robot forensic-analysis agents. Feed an agent a ROS bag plus controller source; score its root-cause hypothesis, the temporal window it flags, and the patch it proposes. MIT.

Companion to [Black Box](../) — the forensic copilot this benchmark was built to stress-test.

## Dataset layout

```
black-box-bench/
  cases/
    <case_name>/
      bag/                 # ROS1 or ROS2 bag (or symlink). Skeleton cases ship without one.
      source/              # Controller source with the injected bug (synthetic cases only).
      telemetry.npz        # Pre-extracted key-topic time-series (synthetic cases, fast in CI).
      video_prompts.md     # Text prompts for Wan 2.2 / Nano Banana. No bundled MP4.
      ground_truth.json    # See schema below.
      README.md            # Human-readable case summary.
  scripts/
    score.py               # Scoring harness.
  runs/
    sample/                # Reference predictions, one JSON per case.
  results/
    sample_eval_2026-04-22.md   # Committed eval tables.
  LICENSE                  # MIT.
  README.md                # This file.
```

`ground_truth.json` keys:

```json
{
  "bug_class": "<taxonomy key>",
  "window_s": [start_s, end_s],
  "evidence_hints": ["..."],
  "patch_target": {"file": "source/buggy/pid.py", "function": "PIDController.step"},
  "patch_hint": "..."
}
```

## Cases

### Scoreable (synthetic, ground-truth authoritative)
- `pid_saturation_01` — PID wind-up causes pose divergence.
- `sensor_timeout_01` — stale lidar frames trigger phantom obstacle maneuvers.
- `bad_gain_01` — excessive `Kp` drives a heading limit cycle.

### Scoreable (real bag, ground-truth derived from sensor cross-check)
- `rtk_heading_break_01` — real ROS 1 car session (~1 h). Rover dual-antenna RTK heading never valid across the entire bag; moving base healthy. Operator-reported "GPS fails under tunnel" is the anti-hypothesis the pipeline must reject. Tests grounding plus cross-source reasoning on unlabelled real data.

### Skeletons (awaiting bag ingestion, excluded from totals)
- `boat_lidar_01` — USV (ROS 2) with LiDAR; forensic or scenario-mining TBD on first real bag. Curated stream-replay fixtures under `fixtures/`.
- `sensor_drop_cameras_01` — multi-camera simultaneous drop on an autonomous car.
- `reflect_public_01` — [REFLECT](https://github.com/real-stanford/reflect) public-dataset case for Tier-2 coverage.
- `sanfer_tunnel_01` — ground-vehicle rover, ~1 h. Operator-reported "tunnel caused RTK anomaly" is the anti-hypothesis; ground truth is `sensor_timeout` 43 min pre-tunnel. Curated stream-replay fixtures under `fixtures/` (Tier-1 grounding-gate showcase; ported 2026-04-23 from the deprecated `bench/` tree).
- `car_1_01` — ground-vehicle urban clip, ~420 s. Tier-2 scenario-mining reference (90 s dwell at parking-lot egress). Curated stream-replay fixtures under `fixtures/`.

## Run a case

```bash
# Score one case:
python scripts/score.py --case cases/pid_saturation_01 \
    --prediction runs/sample/pid_saturation_01.json

# Score every case in cases/ against a predictions dir:
python scripts/score.py --all --predictions-dir runs/sample

# Machine-readable output:
python scripts/score.py --all --predictions-dir runs/sample --json
```

Sample run on 2026-04-22: 6.00 / 6.00 on the 3 scoreable synthetic cases. See `results/sample_eval_2026-04-22.md`.

## Prediction JSON shape

Produced by the Black Box agent (or any agent under test):

```json
{
  "bug_class": "pid_saturation",
  "window_s": [12.3, 17.8],
  "patch": {"file": "source/buggy/pid_controller.py", "function": "PIDController.step"}
}
```

Black Box's own pydantic schemas for the full forensic output live at [`src/black_box/analysis/schemas.py`](../src/black_box/analysis/schemas.py) — `PostMortemReport`, `ScenarioMiningReport`, `SyntheticQAReport`. The bench prediction format is the scoreable projection of those reports.

## Scoring (max 2.0 per case)

| Axis | Weight | Rule |
|------|--------|------|
| Root cause match | 1.0 | Predicted `bug_class` equals ground-truth key exactly |
| Temporal window | 0.5 | IoU over `window_s` >= 0.5 |
| Patch target | 0.5 | Predicted `patch.file` (basename) + `patch.function` match ground truth |

Skeleton cases (`status: skeleton_awaiting_bag`) are excluded from totals.

## License

MIT. See [`LICENSE`](LICENSE). Use this to benchmark your own robot-forensic agent.
