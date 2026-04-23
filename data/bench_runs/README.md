# Opus 4.7 bench results

Live runs of `scripts/run_opus_bench.py` against the non-skeleton cases
in `black-box-bench/cases/`. Each file in this directory is a single
run — tagged by UTC timestamp, keyed by `case_key`, and scored against
the `bug_class` ground truth (plus any `scoring.bug_class_match`
alternatives declared in the case).

## Latest: `opus47_20260423T140758Z`

| case | truth | predicted | confidence | match | cost | wall |
|---|---|---|---:|:---:|---:|---:|
| bad_gain_01 | `bad_gain_tuning` | `bad_gain_tuning` | 0.88 | OK | $0.190 | 27.8s |
| pid_saturation_01 | `pid_saturation` | `pid_saturation` | 0.78 | OK | $0.129 | 22.5s |
| sensor_timeout_01 | `sensor_timeout` | `bad_gain_tuning` | 0.78 | MISS | $0.137 | 22.1s |

**Accuracy: 2 / 3 (66.7%)** at **$0.457 total** on `claude-opus-4-7`,
telemetry-only (no cross-view frames, no code snippets — the hardest
setting we have). Budget cap for the run was $20.

### Honest read

- Bad-gain and PID-saturation are cleanly separated by the velocity /
  PWM shape; the model nails both at high confidence.
- sensor_timeout_01 is the hard one: the model sees scan-range
  discontinuities and attributes them to a gain misconfiguration.
  This is the useful signal to feed back into L2 priors — telemetry
  alone is insufficient for that case; cross-view frame densification
  would help.

### Coverage gap

- 3 of 7 bench cases are `status: skeleton_awaiting_bag` and were
  skipped (boat_lidar_01, reflect_public_01, sensor_drop_cameras_01).
- `rtk_heading_break_01` uses a different `.npz` field-naming convention
  than the three cases above and is skipped by the current loader.
  Not a platform limitation — a loader TODO.

## Re-run

```
.venv/bin/python scripts/run_opus_bench.py --budget-usd 20
.venv/bin/python scripts/run_opus_bench.py --dry-run       # list cases only
.venv/bin/python scripts/run_opus_bench.py --only pid_saturation_01
```

Results go to `data/bench_runs/opus47_<utc_stamp>.json`; update the table
above by hand when promoting a run to "latest."
