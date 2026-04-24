# sanfer_tunnel_01

**Bug class:** `sensor_timeout` (ground-truth: MB -> rover observation stream never wired)
**Platform:** ground vehicle (rover), ROS 1
**Tier:** 1 (forensic post-mortem)
**Status:** skeleton - awaiting bag re-share; curated fixtures only

## Story

A real rover session. The operator filed a ticket claiming *"tunnel entry caused an RTK anomaly."* The ground truth is that dual-antenna moving-base RTK was broken **43 minutes before the tunnel** and DBW was never engaged for the entire 3626.8 s session. A model that uncritically agrees with the operator fails. A grounded model produces the refutation as its own ranked hypothesis.

This is the canonical Tier-1 refutation showcase - the case that proves the grounding gate isn't cosmetic.

## Fixtures

- `fixtures/stream_events.jsonl` - 138 recorded Opus 4.7 stream events over a 711.98 s real-time span.
- `fixtures/analysis.json` - final `PostMortemReport` (schema: `black_box.analysis.schemas.PostMortemReport`).

Diff your runner's output against these to verify plumbing without spending inference budget.

## Scoring

Standard Tier-1 rubric (2.0 max):
- Bug class match on `sensor_timeout` - 1.0
- Window IoU >= 0.5 - 0.5 (pending real window from bag re-ingestion)
- Patch target match - 0.5 (pending bag re-ingestion to pin file/function)

Additionally, at least one hypothesis must refute the operator narrative with non-empty evidence (Tier-1 `refutes_operator: true` contract).

## Provenance

Ported 2026-04-23 from the deprecated `bench/cases.yaml` during the P5-E benchmark-directory consolidation. Historical reference:
- operator narrative verbatim: *"Tunnel entry caused GNSS/RTK anomaly and behavior degradation."*
- curated `analysis.json` is the concise editorial cut used in the demo; the raw analyst cut lives under `demo_assets/analyses/sanfer_tunnel.json`.
