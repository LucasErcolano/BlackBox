# Overnight Batch Runner

One-page operator doc for `scripts/overnight_batch.py`. Iterates every
case in `black-box-bench/cases/` (synthetic + public-dataset skeletons),
streams per-case progress, writes a per-run directory under
`data/bench_runs/batch_<date>[_suffix]/`.

## Invoke

```bash
# Dry-run: stub predictor, zero API calls, real-shape table + manifest.
PYTHONPATH=src python scripts/overnight_batch.py --dry-run

# Unattended live run against Opus 4.7. Budget-gated.
PYTHONPATH=src python scripts/overnight_batch.py --budget-usd 50

# One case only (live):
PYTHONPATH=src python scripts/overnight_batch.py --only pid_saturation_01

# Custom output directory (e.g. pin a batch id):
PYTHONPATH=src python scripts/overnight_batch.py --dry-run \
  --out-dir data/bench_runs/batch_2026-04-23_dryrun
```

The script is self-contained: no Docker, no supervisor required. Run it
in a plain terminal and walk away.

## Cost budget guardrails

- Every run reads `data/costs.jsonl` at the start and uses the summed
  `usd_cost` as the **baseline** — this captures every previous Claude
  call the project has made.
- Before each case the script computes
  `baseline + spent_this_run + PER_CASE_USD_CEILING ($2.00)`. If that
  crosses `--budget-usd` (default **$50**), the case is marked
  `status=skipped_budget` and the run ends cleanly.
- Per-case JSON is flushed as each case completes, so a crash or a SIGINT
  keeps the partial manifest and the completed rows.
- The hackathon hard cap is $500. The default `--budget-usd=50` leaves
  an order of magnitude of headroom; a full synthetic pass costs ~$0.50
  in practice (see `data/bench_runs/opus47_20260423T140758Z.json`).

## Expected wall time

| Mode | Per case | 7-case run |
|---|---:|---:|
| dry-run | <0.05s | <1s |
| live (synthetic, telemetry-only) | ~25s | 3 mins of API wall + plotting |

Skeleton cases (`reflect_public_01`, `boat_lidar_01`,
`sensor_drop_cameras_01`) return immediately in both modes — no bag to
load.

## Table schema

End-of-run table (matches issue #25 exactly):

| column | meaning |
|---|---|
| `case` | case key from `black-box-bench/cases/<key>/` |
| `wall-s` | seconds for that case (includes plotting + API round-trip) |
| `$` | per-case USD cost from the Anthropic SDK usage object |
| `bug_class_match` | `OK` / `MISS` / `SKIP` — `SKIP` covers skeleton cases, errors, and budget-skipped cases |
| `top-hyp confidence` | confidence of the top hypothesis from the post-mortem report (0.00–1.00) |

A case is **OK** only when `predicted_bug ∈ scoring.bug_class_match`
(falling back to `bug_class` if the case does not declare alternatives).
Skeleton cases never count as matches, even though the stub may print
`unknown == unknown`.

## Output directory layout

```
data/bench_runs/batch_<date>[_dryrun][_<suffix>]/
  manifest.json            run-level summary (mode, budget, rows)
  table.txt                plain-text end-of-run table
  table.md                 markdown table + summary paragraph
  <case_key>.json          per-case row, flushed eagerly
  README.md                (optional) human note on this batch
```

`manifest.json` shape:

```json
{
  "batch_id": "batch_2026-04-23_dryrun",
  "mode": "dry-run",
  "model": "claude-opus-4-7",
  "budget_usd": 50.0,
  "baseline_cost_usd": 30.56,
  "spent_usd": 0.0,
  "n_cases": 7,
  "n_match": 4,
  "rows": [...]
}
```

## How to read results

1. Open `table.md` for the at-a-glance view.
2. For every `MISS`, open the per-case JSON to see `predicted_bug`
   vs `ground_truth_bug` and the `notes` field.
3. For every `SKIP`, the `status` field disambiguates:
   - `skeleton` — case intentionally has no bag yet.
   - `skipped_budget` — run hit the budget cap before this case.
   - `error` — telemetry load failed, SDK import failed, or the model
     call raised. `notes` carries the repr.
4. Cross-check `manifest.spent_usd` against `data/costs.jsonl`
   (the runner does not itself append to `costs.jsonl`; the
   `ClaudeClient.analyze` call inside the runner does).

## Known limitations (hackathon honesty)

- `rtk_heading_break_01` uses a different npz field-naming convention
  than the three synthetic cases and is skipped by the live loader
  with `status=error`. Loader TODO, not a platform limitation.
- The live runner uses `post_mortem_prompt` with telemetry only (no
  cross-view frames, no code snippets). That is the hardest setting we
  ship — sensor_timeout misclassifies against bad_gain_tuning on
  telemetry alone. Enable `visual_mining_v2` for the hero cases when
  you have the token budget.
- The batch runner never records an asciinema cast on its own; record
  one with `asciinema rec docs/assets/overnight_batch_live.cast -c
  'PYTHONPATH=src python scripts/overnight_batch.py --budget-usd 50'`
  after the first unattended live run.

## Canonical dry-run artifact

The committed `data/bench_runs/batch_2026-04-23_dryrun/` directory is
the expected dry-run output. Regenerate it with:

```bash
rm -rf data/bench_runs/batch_2026-04-23_dryrun && \
  PYTHONPATH=src python scripts/overnight_batch.py --dry-run \
    --out-dir data/bench_runs/batch_2026-04-23_dryrun
```

A terminal-log equivalent of that run is at
`docs/assets/overnight_batch_dryrun.txt` — use it as a substitute for
the live asciinema cast until the unattended run lands.
