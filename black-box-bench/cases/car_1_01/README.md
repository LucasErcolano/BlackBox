# car_1_01

**Bug class:** `other` (scenario-mining reference - not a forensic bug case)
**Platform:** ground vehicle
**Tier:** 2 (scenario mining)
**Status:** skeleton - awaiting bag re-share; curated fixtures only

## Story

Urban clip, roughly 420 s. Operator framed it as "nothing broken, mine for scenarios of interest." The finding worth surfacing: the ego sat stationary for ~90 s at a parking-lot egress with a pedestrian and cart in the lane under a raised barrier, with no escalation or progress during the dwell. Not a bug - a scenario a human operator would want flagged in a 7-minute clip.

Tier-2 scoring credit is awarded when the agent surfaces a moment overlapping the dwell window.

## Fixtures

- `fixtures/stream_events.jsonl` - recorded Opus 4.7 stream events.
- `fixtures/analysis.json` - final scenario-mining report (schema: `black_box.analysis.schemas.PostMortemReport`).

## Scoring

Tier-2 (`run_tier(2, ...)` in `src/black_box/eval/runner.py`): at least one `predicted_moments[*].t` must overlap the ground-truth window_s once it's pinned from the re-ingested bag.

## Provenance

Ported 2026-04-23 from the deprecated `bench/cases.yaml` during the P5-E benchmark-directory consolidation.
