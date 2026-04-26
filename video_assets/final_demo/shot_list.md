# Final demo — shot list

Output: `video_assets/final_demo/final_demo_3min_visual_only.mp4`
Runtime: 3:00.000 (exact). 1920x1080, h264, 30 fps, no audio track.

| #  | t (out)       | dur  | source clip                                                   | src in–out | overlay text                                                                          | reason |
|----|---------------|------|---------------------------------------------------------------|------------|---------------------------------------------------------------------------------------|--------|
| 01a| 0:00–0:06     | 6.0  | lavfi black                                                   | —          | "The operator blamed the tunnel."                                                     | hook card 1 — operator framing |
| 01b| 0:06–0:12     | 6.0  | lavfi black                                                   | —          | "Black Box checked the recording."                                                    | hook card 2 — product framing |
| 02a| 0:12–0:22     | 10.0 | final_ui_capture/intake_ui.mp4                                | 0–10       | "Robot failures leave evidence everywhere." / "Video · lidar · telemetry · controller logs" | product problem — full intake clip |
| 02b| 0:22–0:25     | 3.0  | final_ui_capture/clip.mp4                                     | 0–3        | (same as 02a)                                                                          | bridge into setup |
| 03 | 0:25–0:38     | 13.0 | final_ui_capture/clip.mp4                                     | 3–16       | "One real driving session" / "Operator note — check the tunnel. No labels."           | setup — Sanfer session in product UI |
| 04 | 0:38–0:55     | 17.0 | final_ui_capture/managed_agent_stream_ui.mp4                  | 0–17       | "Opus 4.7 managed forensic agent" / "Tools · events · memory · evidence"              | live product surface |
| 05 | 0:55–1:08     | 13.0 | block_sanfer_evidence/clip.mp4                                | 0–13       | "Telemetry selects the windows" / "Vision checks the evidence"                        | visual mining beat A + start of operator quote |
| 06 | 1:08–1:35     | 27.0 | block_sanfer_evidence/clip.mp4                                | 13–40      | "Operator hypothesis: tunnel caused GPS failure" / "Finding — RTK heading failure started 43 minutes earlier" | refutation (must-keep) — operator quote → REFUTED → first root-cause cards |
| 07 | 1:35–1:55     | 20.0 | block_sanfer_evidence/clip.mp4                                | 40–60      | "Actual failure — RTK correction path" / "Rover never gets valid heading"             | root cause (must-keep) — carrier-phase + REL_POS_VALID + stat card |
| 08a| 1:55–2:05     | 10.0 | block_sanfer_evidence/clip.mp4                                | 60–70      | "Scoped patch, not redesign" / "Proposed for human review"                            | scoped patch — 3-file diff w/ vertical pan |
| 08b| 2:05–2:12     | 7.0  | final_ui_capture/patch_human_review_ui.mp4                    | 0–7        | (same as 08a)                                                                          | HITL surface — approve/reject in real UI |
| 09 | 2:12–2:32     | 20.0 | block_credibility_opus47/clip.mp4                             | 0–20       | "Same accuracy. Better judgment. More eyes." / "Simple post-mortems — 4.6 = 67%, 4.7 = 67%" | Opus 4.7 delta — title + delta_panel readable |
| 10 | 2:32–2:43     | 11.0 | block_credibility_opus47/clip.mp4                             | 20–31      | "4.7 preserves fine visual evidence" / "4.7 runs faster on telemetry / text"          | breadth montage tail = vision/speed proof |
| 11 | 2:43–2:52     | 9.0  | block_credibility_opus47/clip.mp4                             | 31–40      | "Not a single-car demo" / "Cars · robotic boat · clean cases · injected failures"     | grounding + bench beats = generalization |
| 12a| 2:52–2:57.5   | 5.5  | block_credibility_opus47/clip.mp4                             | 40–45.5    | "No evidence → no claim" / "Open benchmark · reproducible runs · cents per case"      | outro — costs.jsonl panel |
| 12b| 2:57.5–3:00   | 2.5  | ui_feature_inserts/evidence_trace_insert.mp4                  | 0–2.5      | (same as 12a)                                                                          | close — evidence trace as final visual |

Notes:
- All overlays are bottom lower-third, black @55% scrim, white DejaVuSans-Bold, 44pt primary / 34pt secondary.
- Source 30 fps clips passed through; 10 fps UI clips upsampled to 30 fps via `fps=30` filter (visual judder unchanged).
- Hard cuts only — no crossfades — to keep tone forensic.
