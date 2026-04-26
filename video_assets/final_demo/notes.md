# Final demo — production notes

## Runtime

3:00.000 exact. Hard cap met.

## Audio

All source clips have **no audio stream** (verified via ffprobe). Output muxed `-an`. Final mp4 has zero audio tracks. Safe for separate VO add later.

## Optional inserts used

- `final_ui_capture/intake_ui.mp4` — segment 02a
- `final_ui_capture/managed_agent_stream_ui.mp4` — segment 04
- `final_ui_capture/patch_human_review_ui.mp4` — segment 08b (HITL surface in real UI)
- `ui_feature_inserts/evidence_trace_insert.mp4` — segment 12b (final 2.5s)

## Optional inserts skipped

- `final_ui_capture/report_overview_ui.mp4` — Batch B already covers generalization/grounding more compactly.
- `ui_feature_inserts/memory_insert.mp4` — managed_agent_stream_ui already shows tools/events/memory; extra insert would push past 3:00.
- `ui_feature_inserts/steering_insert.mp4` — not in narrative.
- `ui_feature_inserts/hitl_patch_insert.mp4` — `final_ui_capture/patch_human_review_ui.mp4` is the higher-fidelity real UI capture, preferred.
- `ui_feature_inserts/rollback_insert.mp4` — not in narrative.

## Visual issues to fix before adding voice-over

- Lower-third scrim covers bottom 180 px on every non-hook segment — confirm it does not occlude critical chart axes in `block_sanfer_evidence` clip 40–60s root-cause panels. Spot-checked: stat card and plots sit above 900 px, so axes remain visible. Re-verify on 1080p monitor.
- 10 fps UI clips upscaled to 30 fps via plain `fps` filter — playback shows mild judder on cursor moves. Acceptable for demo, but if VO timing requires smooth scrubs, re-render UI clips at 30 fps source.
- Hook cards (0:00–0:12) are pure black with centered white text. If VO opens cold on a louder beat, consider adding 1–2 frames of preview.png Ken-Burns instead.

## Claims that depend on external artifacts

These visual claims are pulled from real artifacts and remain correct only if the source files do:

- "RTK heading failure started 43 minutes earlier" — depends on `data/runs/sanfer_sanisidro__no_prompt/windows.json` + bench `rtk_heading_break_01` evidence.
- All Opus 4.6 vs 4.7 numbers in segment 09 — depend on `black-box-bench/runs/sample/opus46_vs_opus47_*.json` (per `block_credibility_opus47/notes.md`).
- "cents per case" close — depends on `data/costs.jsonl` (currently $53.13 / 283 calls per Batch B notes).
- Patch / RTCM / UART text on screen in segment 08a — rendered by `scripts/render_block_sanfer_evidence.py` from real bag-derived diff.

If any of those upstream artifacts get regenerated with different numbers, segments 06–09 will need a re-cut.

## Build command

```bash
ffmpeg -f concat -safe 0 -i /tmp/fd/concat.txt \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -an \
  video_assets/final_demo/final_demo_3min_visual_only.mp4
```

Per-segment commands trim+overlay each source via `drawbox` (lower-third scrim) + two `drawtext` (textfile=, expansion=none for the % line) at 30 fps 1920x1080 yuv420p. See `shot_list.md` for src in/out per segment.
