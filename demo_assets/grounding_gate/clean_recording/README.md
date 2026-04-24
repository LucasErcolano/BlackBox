# Grounding gate: "nothing anomalous detected" demo

A clean recording went in. The model under pressure produced four 
plausible-but-under-evidenced hypotheses. The gate killed all four 
and the report that ships says so explicitly.

## Why this asset exists

Lucas asked for the grounding gate to be visible in the demo, 
including the no-anomaly branch. Previous assets only showed the 
*refutation* side (operator narrative contradicted by telemetry). 
This one shows the *silence* side — the agent would rather ship 
nothing than ship a fabrication.

## Before (raw) vs after (gated)

| # | bug_class | conf | evidence | status |
|--:|-----------|-----:|---------:|--------|
| 0 | `pid_saturation` | 0.72 | 1 | dropped — only 1 evidence row(s) (need >= 2) |
| 1 | `calibration_drift` | 0.60 | 2 | dropped — only 1 source (camera) — need >= 2 |
| 2 | `bad_gain_tuning` | 0.55 | 2 | dropped — only 1 source (telemetry) — need >= 2 |
| 3 | `latency_spike` | 0.22 | 2 | dropped — confidence 0.22 < 0.4 |

**Gated output** — `patch_proposal`: _No anomaly detected with sufficient evidence to support a scoped fix._
**Hypotheses shipped**: 0

## Gate rules applied

- min confidence: `0.4`
- min evidence rows / hypothesis: `2`
- min distinct evidence sources: `min(2, available_sources)`
- info-severity moments dropped by default

Rules live in `src/black_box/analysis/grounding.py :: GroundingThresholds`. 

## Regenerate

```
python scripts/build_grounding_gate_demo.py
```

Outputs:
- `raw_hypotheses.json` — pre-gate report
- `gated_report.json` — what ships to the PDF renderer
- `drop_reasons.json` — per-hypothesis rejection reason

## Companion asset

`../README.md` covers the *refutation* side on sanfer_tunnel. This 
file covers the *silence* side. Together they cover both exits from 
the gate.
