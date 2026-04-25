# Clean-Clone Smoke Test

End-to-end walkthrough a judge (or any fresh machine) runs after `git clone`.
Exercises the package install, analysis imports, and one public-dataset
benchmark case without spending a single API token.

## Prereqs

- Python **>= 3.10** (verified on 3.13).
- `pip` and `venv` from the standard library (no extras).
- ~600 MB disk for the transitive dependency set (numpy, opencv, matplotlib,
  rosbags, reportlab, fastapi, anthropic, pydantic, etc.).
- No ROS runtime required. No GPU required. No CUDA required.
- No `ANTHROPIC_API_KEY` required for the smoke path (the offline stub runner
  does not call the API). A key is only needed for `--use-claude` live runs.

## Expected runtime

| Step | Time (cold pip cache) | Time (warm pip cache) |
|---|---|---|
| `python -m venv` | ~3 s | ~3 s |
| `pip install -e .` | ~90 s | ~10 s |
| Offline benchmark run (7 cases) | < 1 s | < 1 s |

Total: roughly 2 min on a fresh machine, 15 s on a warm one.

## Expected output artifacts

- Editable install of the `black-box` wheel plus its dependency closure into
  the new venv.
- Stdout table with one row per benchmark case and a summary tail:
  `tier=3 cases=9 match=4 acc=44.44% cost=$0.0000 claude=False`.
- No files written outside the venv directory. The offline stub path does
  not touch `data/`.

## Exact commands

From the repo root after `git clone`:

```bash
python3 -m venv .smoke-venv
source .smoke-venv/bin/activate
pip install -e .
python -m black_box.eval.runner --tier 3 --case-dir black-box-bench/cases
```

Expected stdout (verified 2026-04-25, Python 3.10, Linux x86_64):

```
predicted_bug    predicted_window      cost_usd    wall_time_s  source    case_key                ground_truth_bug    skeleton    match
---------------  ------------------  ----------  -------------  --------  ----------------------  ------------------  ----------  -------
bad_gain_tuning  [5.0, 20.0]                  0              0  stub      bad_gain_01             bad_gain_tuning     False       True
unknown                                       0              0  stub      boat_lidar_01           unknown             True        False
unknown                                       0              0  stub      car_1_01                other               True        False
pid_saturation   [12.0, 18.0]                 0              0  stub      pid_saturation_01       pid_saturation      False       True
unknown                                       0              0  stub      reflect_public_01       unknown             True        False
sensor_timeout   [0.0, 3626.8]                0              0  stub      rtk_heading_break_01    sensor_timeout      False       True
unknown                                       0              0  stub      sanfer_tunnel_01        sensor_timeout      True        False
unknown                                       0              0  stub      sensor_drop_cameras_01  sensor_timeout      True        False
sensor_timeout   [10.0, 14.0]                 0              0  stub      sensor_timeout_01       sensor_timeout      False       True

tier=3 cases=9 match=4 acc=44.44% cost=$0.0000 claude=False
```

Four matches, five skeleton (no-bag) cases intentionally fail rather than
silently score `unknown == unknown`. Total session cost: $0.00. Nine
public-dataset cases exercised end-to-end. The acc% number is intentionally
honest: skeleton cases count against accuracy by design — silent
"unknown == unknown" matches would inflate the score.

## Tier 1 smoke (offline, also free)

The tier-1 runner adds a patch-target prediction on top of the tier-3 row:

```bash
python -m black_box.eval.runner --tier 1 --case-dir black-box-bench/cases
```

Tail row: `tier=1 cases=9 match=4 acc=44.44% cost=$0.0000 claude=False total_score=7.50/18.00`.

## Sanity: run_session help

Verifies the full pipeline entrypoint imports cleanly (no missing modules):

```bash
python scripts/run_session.py --help
```

Prints the argparse help text. If this fails with `ModuleNotFoundError`,
open an issue; every module in `src/black_box/analysis/` is required.

## Implicit directories

The code creates these under the repo root on first real call. The offline
smoke path does not touch them, so they only materialize when you move to
live runs.

| Path | Created by | When |
|---|---|---|
| `data/` | `ClaudeClient._ensure_costs_file` | on the first API call (auto-created) |
| `data/costs.jsonl` | same | on the first API call (auto-created) |
| `data/jobs/`, `data/reports/`, `data/uploads/`, `data/patches/` | `black_box.ui.app` module import | when the FastAPI app boots (auto-created) |
| `data/runs/<session_name>/` | `scripts/run_session.py :: run()` | when `run_session.py` processes a folder (auto-created) |

All are created with `Path.mkdir(parents=True, exist_ok=True)`; none need to
be pre-staged. Judges running only the offline eval stub will not create any
of them.

## Live-run cost (skip for submission smoke)

If you want to confirm the real Claude path works, flip the switch:

```bash
export ANTHROPIC_API_KEY=sk-...
python -m black_box.eval.runner --tier 3 --case-dir black-box-bench/cases --use-claude
```

Rough cost ceiling: 7 cases x ~$0.50 upper bound per case = < $4 at current
Opus 4.7 pricing. The offline smoke above is the canonical judge path;
live-run is optional and only validates the Anthropic transport.

## Cleanup

```bash
deactivate
rm -rf .smoke-venv
```

`.smoke-venv/` is in `.gitignore`.
