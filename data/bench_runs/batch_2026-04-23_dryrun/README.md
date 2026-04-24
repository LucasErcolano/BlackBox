# batch_2026-04-23_dryrun — DRY-RUN (NOT LIVE)

**Mode:** `dry-run` (stub predictor, zero API calls).
**Model line:** `claude-opus-4-7` (carried in manifest for schema
completeness — no model was actually invoked).
**Purpose:** prove the overnight-batch plumbing end to end without
burning budget. This is **not** a real eval.

## How to read this directory

| File | Meaning |
|---|---|
| `manifest.json` | Run-level summary: mode, budget, cumulative baseline from `data/costs.jsonl`, row list. |
| `table.txt` / `table.md` | End-of-run table (columns: `case`, `wall-s`, `$`, `bug_class_match`, `top-hyp confidence`). |
| `<case>.json` | Per-case row, flushed as each case completes so partial runs survive a crash. |

## Why every non-skeleton row says OK

The stub predictor echoes ground truth with a fixed 0.77 confidence —
that is its job: exercise the row shape, I/O, budget gate, and streaming
without spending a cent. Skeleton cases (no bag yet) stay
`predicted_bug=unknown` / `SKIP` so the table is honest about what a
real run would be unable to score.

## What a live run will look like

`scripts/run_opus_bench.py` already ran a similar live pass on three of
these cases; see `data/bench_runs/opus47_20260423T140758Z.json`:
2/3 synthetic cases matched at ~$0.46 total. The live overnight_batch
run will cover the same three synthetic cases plus `rtk_heading_break_01`
once its npz loader lands, and will cost-gate against `--budget-usd`
(default $50).

## Re-run

```
PYTHONPATH=src python scripts/overnight_batch.py --dry-run --out-dir data/bench_runs/batch_2026-04-23_dryrun
```

For the real thing (unattended, budget-gated):

```
PYTHONPATH=src python scripts/overnight_batch.py --budget-usd 50
```

See `OVERNIGHT_BATCH.md` at repo root for the full one-pager.
