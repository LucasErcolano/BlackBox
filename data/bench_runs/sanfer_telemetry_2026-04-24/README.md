# sanfer_telemetry 2026-04-24 — reference artifact

Closes #26. Proof artifact for the telemetry-only E2E repro documented at
`docs/REPRO_SANFER_TELEMETRY_ONLY.md`.

## What is in this folder

`rtk_heading_break_01.json` — reference `ForensicReport` JSON for the
sanfer_sanisidro RTK-heading hero finding, produced by
`scripts/run_rtk_heading_case.py` against the pre-extracted bench
fixture at `black-box-bench/cases/rtk_heading_break_01/telemetry.npz`.
This is telemetry-only (no camera frames, no cross-view pass). It is
committed here as the **reference output** the repro doc verifies
against.

The three raw telemetry bags (`2_dataspeed.bag`, `2_diagnostics.bag`,
`2_sensors.bag`) are not in the repo — only the operator has them. The
bench case is the committed-in-repo replay fixture that reproduces the
same finding without needing the bags on disk.

## Hero signatures (grep-able)

- `CARR_NONE=100.0%` — rover never achieves carrier-phase lock.
- `FLAGS_REL_POS_VALID set on 0.0% of 18133 samples` — RTK heading
  invalid for the entire 3626.8 s run.
- `DIFF_SOLN set on only 15.0%` — base→rover RTCM link mostly absent.
- Moving-base contrast: `FLOAT 63.6% / FIXED 30.7%` — sky + antenna
  fine, only the inter-receiver link is broken.
- Operator tunnel hypothesis refuted: top ranked hypothesis is
  moving-base RTK misconfiguration, not a tunnel event.

## Fresh-run reproduction

From a clean checkout:

```
.venv/bin/python scripts/run_rtk_heading_case.py
```

Writes to `black-box-bench/runs/sample/rtk_heading_break_01.json`. Diff
that output against this committed reference — the bug_class, ranked
evidence, and refutation verdict should match. Cost and wall time will
differ run-to-run (deterministic schema, nondeterministic phrasing).

## Cost / runtime reference

- Option A (telemetry-only one-shot): ~45 s, $0.04–$0.10 per run.
- Option B (full `run_session.py` over three bags, stage 4 no-op):
  3–7 min, $0.10–$0.40 per run.

See `data/costs.jsonl` at repo root for appended cost rows.
