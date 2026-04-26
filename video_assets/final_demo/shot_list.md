# Final demo — shot list

Output: `video_assets/final_demo/final_demo_3min_visual_only.mp4`
Runtime: 3:00.000 (exact). 1920x1080, h264, 30 fps, no audio track.
Build: `bash scripts/build_final_demo.sh`.

| #  | t (out)       | dur  | source clip                                                   | src in–out | reason |
|----|---------------|------|---------------------------------------------------------------|------------|--------|
| 01a| 0:00–0:04     | 4.0  | dark slate (#0e0f0a), DejaVuSans-Bold 64pt                    | —          | hook 1 — "The operator blamed the tunnel." |
| 01b| 0:04–0:08     | 4.0  | dark slate                                                    | —          | hook 2 — "Black Box checked the recording." |
| 02a| 0:08–0:18     | 10.0 | final_ui_capture/intake_ui.mp4                                | 0–10       | product problem — full intake clip (dark UI) |
| 02b| 0:18–0:21     | 3.0  | final_ui_capture/clip.mp4                                     | 0–3        | bridge into setup |
| 03 | 0:21–0:34     | 13.0 | final_ui_capture/clip.mp4                                     | 3–16       | setup — Sanfer session in product UI |
| 04 | 0:34–0:51     | 17.0 | final_ui_capture/managed_agent_stream_ui.mp4                  | 0–17       | live agent surface — tools/events/memory |
| 05 | 0:51–1:04     | 13.0 | block_sanfer_evidence/clip.mp4                                | 0–13       | visual mining beat A + start of operator quote |
| 06 | 1:04–1:31     | 27.0 | block_sanfer_evidence/clip.mp4                                | 13–40      | refutation (must-keep) — operator quote → REFUTED |
| 07 | 1:31–1:51     | 20.0 | block_sanfer_evidence/clip.mp4                                | 40–60      | root cause (must-keep) — carrier-phase + REL_POS_VALID |
| 08a| 1:51–2:01     | 10.0 | block_sanfer_evidence/clip.mp4                                | 60–70      | scoped patch — 3-file diff |
| 08b| 2:01–2:11     | 10.0 | final_ui_capture/patch_human_review_ui.mp4                    | 0–10       | HITL surface — approve/reject in real UI (widened from 7s) |
| 09 | 2:11–2:31     | 20.0 | block_credibility_opus47/clip.mp4                             | 0–20       | Opus 4.7 delta — title + delta_panel readable |
| 10 | 2:31–2:42     | 11.0 | block_credibility_opus47/clip.mp4                             | 20–31      | breadth montage tail = vision/speed proof |
| 11 | 2:42–2:51     | 9.0  | block_credibility_opus47/clip.mp4                             | 31–40      | grounding + bench beats = generalization |
| 12a| 2:51–2:56.5   | 5.5  | block_credibility_opus47/clip.mp4                             | 40–45.5    | outro — costs.jsonl panel |
| 12b| 2:56.5–3:00   | 3.5  | ui_feature_inserts/evidence_trace_insert.mp4                  | 0–3.5      | close — evidence trace as final visual (extended from 2.5s) |

Notes:
- Lower-third caption overlays REMOVED. Hook slates carry the only added text.
- UI clips re-recorded at 30 fps source (`scripts/record_*_ui.py FPS=30`) — no upsample judder.
- 0.2s fade in / 0.2s fade out per segment → ~12-frame black dip between cuts. Softens hard boundaries while preserving 3:00 runtime.
- All sources dark-themed: UI capture via Playwright dark CSS injection (`scripts/_ui_dark.py`); Batch A/B rendered against dark BG.
- Hook compressed 12s → 8s (4+4) vs first cut; recovered 4s went to widening 08b patch UI (7s → 10s) and 12b close (2.5s → 3.5s).
- mp4 has `creation_time` + git short sha embedded in metadata.
