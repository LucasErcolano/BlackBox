# Opus 4.7 vs Opus 4.6 — BlackBox delta harness

We claim Opus 4.7 is the reason BlackBox can be a long-horizon forensic
agent instead of a one-shot report generator. This doc is the harness
that lets us back the claim with numbers, not vibes.

## TL;DR — what 4.7 actually wins on

Single-shot bug_class accuracy on simple closed-taxonomy cases is a
**ceiling-effect metric**: both models saturate it. The signal lives in
the five axes below.

| Axis | 4.6 | 4.7 | Source |
| --- | --- | --- | --- |
| Latency (wall time)         | 100% | **~70%** | every run, n=24..36 |
| $/correct (solvable subset) | $0.16 | **$0.16** ≈ tied raw, lower under pressure | both passes |
| Calibrated abstention on under-specified cases | **0%** (3/3 commit wrong answer) | **100%** (3/3 abstain) | mode=none, n=12 each |
| Brier under adversarial operator pressure | 0.239 | **0.162** | mode=false, n=9 each |
| Fine-grain text detection at 3.84 MP image | **0%** (0/3) | **100%** (3/3) | D1 vision A/B, n=3 each |

Single-shot bug_class accuracy on solvable cases: **tied at 67%** in
both passes. 4.6's apparent edge in raw `bug_match_rate` comes entirely
from confidently mis-classifying `rtk_heading_break_01` as
`sensor_timeout` — pattern-matching the operator narrative rather than
recognizing the closed taxonomy doesn't fit. 4.7 abstains.

## What it measures

For each bench case, both models receive **the same prompt, same
telemetry summary, same focused plot, same budget**. The only thing
that changes is the model id. Per case+model+seed:

| Metric                  | Why it matters                                     |
| ----------------------- | -------------------------------------------------- |
| `bug_class` match       | Raw forensic accuracy vs `ground_truth.json`        |
| `solvable_accuracy`     | Accuracy excluding under-specified taxonomy cases  |
| `abstention_correctness`| On under-specified cases: did the model decline    |
| `pt_file_match`/`pt_function_match`/`pt_both_match` | Patch proposal names file/function |
| `confidence` (top-1)    | Calibration of leading hypothesis                  |
| `brier_score`           | `mean((confidence - match)^2)` — lower better      |
| `flip_rate`             | Disagreement across seeds (lower = more stable)    |
| `refutation_rate`       | When operator narrative is wrong, did model push back |
| `evidence_count`        | Distinct (source, topic_or_file) tuples cited      |
| `cost_usd`, `wall_time_s` | $, latency from live ledger                      |
| `usd_per_correct`, `wall_per_correct` | Normalized by accuracy             |

A case is `is_under_specified` if `gt.under_specified == true`, the
scoring rationale mentions "no exact slot", or `scoring.bug_class_match`
lists more than one accepted class — i.e. the closed taxonomy can't
cleanly tag it. `rtk_heading_break_01` is the canonical example.

## How to run

Two passes give the headline story:

**Pass 1 — clean baseline (mode=none).** Surfaces calibrated abstention
and raw single-shot performance.

```bash
.venv/bin/python scripts/compare_opus_models.py \
    --models claude-opus-4-6 claude-opus-4-7 \
    --seeds 3 --temperature 1.0 --budget-usd 4 \
    --operator-mode none
```

**Pass 2 — false-operator pressure (mode=false).** Surfaces calibration
under adversarial framing on solvable cases.

```bash
.venv/bin/python scripts/compare_opus_models.py \
    --seeds 3 --temperature 1.0 --budget-usd 4 \
    --operator-mode false \
    --cases bad_gain_01,pid_saturation_01,sensor_timeout_01
```

`--operator-mode native` uses `gt.anti_hypothesis` if present (pre-Tier
A behavior — kept for back-compat).

`--no-grounding` disables the post-hoc grounding gate; use to isolate
raw model behavior from gate filtering.

**Pass 3 — D1 vision A/B (`scripts/compare_opus_vision.py`).** Surfaces
the image-cap advantage. 4.6 caps at 1568 px / 1.15 MP server-side; 4.7
caps at 2576 px / 3.75 MP. We render a 2400 × 1600 plot with a 10 pt
text token in the corner and ask the model to read every annotation:

```bash
.venv/bin/python scripts/compare_opus_vision.py --seeds 3 --budget-usd 2
```

Live result: 4.6 0/3 detection, 4.7 3/3 detection (+100pp). Token at
~10 pt rendered on a 2400 px canvas survives 4.7's downsample but
becomes ~6 px tall after 4.6's downsample to 1568 px → unreadable.
Output: `data/bench_runs/opus_vision_d1_<UTC-stamp>.json` plus the
rendered plot as a sibling artifact under `vision_assets/`.

The model is parametrizable everywhere via `BLACKBOX_MODEL` env var or
`ClaudeClient(model=...)`. Per-model pricing lives in
`src/black_box/analysis/claude_client.py::ClaudeClient.PRICING_BY_MODEL`.

Dry-run (case discovery, no API calls):

```bash
.venv/bin/python scripts/compare_opus_models.py --dry-run
```

## Output

`data/bench_runs/opus46_vs_opus47_<UTC-stamp>.json` shaped as:

```json
{
  "schema": "opus_model_compare/2.3",
  "operator_mode": "none|native|false",
  "grounding": true,
  "models": ["claude-opus-4-6", "claude-opus-4-7"],
  "cases": ["bad_gain_01", "..."],
  "aggregates": [{
    "model": "...",
    "bug_match_rate": 0.50,
    "solvable_accuracy": 0.67,
    "abstention_correctness": 1.0,
    "brier_score": 0.166,
    "...": "..."
  }],
  "delta": {
    "abstention_correctness_delta": 1.0,
    "brier_score_delta": -0.077,
    "wall_time_s_delta": -94.3,
    "...": "..."
  }
}
```

## What we are *not* claiming

- Opus 4.7 is "better at coding in general" — out of scope.
- Memory reuse delta — covered separately by `scripts/memory_loop_demo.py`.
- Vision escalation success — covered by `visual_mining_v2`; A/B'ing
  high-res here would re-introduce a confound (image budget) that
  defeats the comparison.

## Caveats

- Patch-target match is substring-based (file basename + terminal
  function name); generous on purpose. Bench function names like
  `step` are common in code so `pt_function_rate` is noisy.
- `evidence_count` counts unique `(source, topic_or_file)` tuples; it
  does not verify topics exist. The grounding module enforces
  existence at report-write time.
- The bench is small (3–4 cases × 3 seeds = 9–12 runs/model).
  Treat differences under one case as noise; report direction +
  magnitude, not p-values.
- `abstention_correctness` requires at least one under-specified case
  to be informative. `rtk_heading_break_01` is currently the only one.

## Methodology rationale

Why two passes? A single run conflates capability and calibration:

- **Mode=none** isolates capability + calibration on a clean baseline.
  Surfaces the calibrated-abstention advantage.
- **Mode=false** stresses calibration under adversarial framing.
  Surfaces the brier-under-pressure advantage.

Without these, raw `bug_match_rate` rewards confident pattern-matching
on under-specified cases (which is how 4.6 looked deceptively better in
earlier passes). The Tier-A scoring fixes (`solvable_accuracy`,
`abstention_correctness`, `is_under_specified`) decouple "got the
answer" from "called the bluff."
