# block_07_grounding — notes

## What is real
- All four candidate hypotheses come from `demo_assets/grounding_gate/clean_recording/raw_hypotheses.json`:
  - `pid_saturation` conf 0.72, 1 evidence
  - `calibration_drift` conf 0.60, 2 evidence (same camera source)
  - `other` conf 0.55, 2 evidence
  - `latency_spike` conf 0.22
- Every on-screen "drop reason" string is the exact `reason_dropped` value from `demo_assets/grounding_gate/clean_recording/drop_reasons.json`.
- The gated JSON card shows the real shape of `gated_report.json`: `"hypotheses": []`, and the `patch_proposal` line is the exact string emitted by `src/black_box/analysis/grounding.py` (`NO_ANOMALY_PATCH`).
- The thresholds subtitle ("min 2 evidence · min 2 sources · conf ≥ 0.40") reflects the real `GroundingThresholds` defaults in `src/black_box/analysis/grounding.py`.

## What is composited
- Candidate rows, REJECTED tags, strike-throughs, drop-reason callout, JSON-card chrome, principle lockup, 4-dot beat indicator, grid backdrop, drop shadows, crossfades. All PIL/ffmpeg.

## What is placeholder
- Nothing. Every text element on screen either quotes a real file byte-for-byte or summarizes a field from one.

## Why this block supports the VO
- "Black Box does not force an answer" → beat A shows four candidates queued, no verdict yet.
- "reject low-support explanations" → beat B strikes each one through with its real threshold-failure reason.
- "return empty moments, keep the report narrow" → beat C is the literal `hypotheses: []` report.
- "no evidence, no claim" → beat D says it as the principle, held long enough to land.

## Why this block is UI-independent
No product UI is rendered or implied. Every frame is either JSON fragments, typography, or the grid backdrop. The render script reads only from `demo_assets/grounding_gate/clean_recording/` — no running service, no FastAPI, no HTMX.

## Visual continuity with blocks 01 and 02
Same palette tokens, same fonts, same 80px grid, same drop-shadow recipe, same 4-dot progress indicator. What changed, on purpose:
- Amber is desaturated (#ffb840 → #c49648) and reserved for the hairline accent, the empty-array line, and the conclusion word "claim."
- Only 1–2 primary elements on screen at any moment (never five stagger-in tiles like block_02).
- Crossfades slowed to 450–600ms; long holds on beats C and D.
- Rejection is communicated by strike-throughs and muted-red REJECTED tags — not motion. No flourish, no sweep.

Effect: same film, stricter phase. Verification cadence, not discovery cadence.

## Final-ready?
Yes. Drops directly into the final edit as the credibility beat before the diff reveal.

## What should be regenerated later
- If the default `GroundingThresholds` values change, update the subtitle string in beat D.
- If more cases get added under `demo_assets/grounding_gate/`, the script can be pointed at a different case by changing the three JSON paths at the top.
- If VO timing requires 17–18s, extend beat D hold (the cheapest edit).

## Reproduce
```
python3 scripts/render_block_07_grounding.py
```
Outputs `video_assets/block_07_grounding/{clip.mp4,preview.png}`.
