# Sample eval run — 2026-04-22

Reproducer:

```bash
python scripts/score.py --all --predictions-dir runs/sample
```

## Table

```
case                           bug     iou   win patch total
------------------------------------------------------------
bad_gain_01                      1.0  0.91   0.5   0.5  2.00
boat_lidar_01                    0.0  0.00   0.0   0.0  0.00  [skeleton (awaiting bag)]
pid_saturation_01                1.0  0.95   0.5   0.5  2.00
reflect_public_01                0.0  0.00   0.0   0.0  0.00  [skeleton (awaiting bag)]
sensor_drop_cameras_01           0.0  0.00   0.0   0.0  0.00  [skeleton (awaiting bag)]
sensor_timeout_01                1.0  0.67   0.5   0.5  2.00
------------------------------------------------------------
TOTAL (scoreable only)                                  6.00 / 6.0
```

3 scoreable synthetic cases, full score. 3 skeletons excluded from total (awaiting bag ingestion).

## Notes

- `runs/sample/` holds hand-written predictions that mirror what `scripts/end_to_end_smoke.py` returns on `pid_saturation_01` (real pipeline output, predicted=`pid_saturation`, match=True, cost $0.12 wall 11.5 s — see repo `data/costs.jsonl`).
- `sensor_timeout_01` window IoU is 0.67: predicted window `[10.5, 13.2]` overlaps ground truth `[10.0, 14.0]` — partial but above 0.5 threshold, full window-score awarded.
- Skeleton cases hit `scripts/score.py:55` status guard and are excluded from the denominator.
- Public-dataset case (`reflect_public_01`) is wired but awaits REFLECT bundle download (see `src/black_box/eval/public_data.py`).
