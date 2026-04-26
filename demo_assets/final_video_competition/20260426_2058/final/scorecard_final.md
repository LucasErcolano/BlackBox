# BlackBox demo · scorecard (hybrid v3 vs v2 baseline)

## Rubric (100 pts)

| Dimension | Max | v2 baseline | hybrid v3 | rationale |
|---|---|---|---|---|
| Narrative clarity | 20 | 20 | 20 | Identical script structure (13 segments, same beat order) |
| Visual cohesion | 20 | 16 | 18 | Hybrid keeps v2 panel design language, adds 2 real-UI clips that share palette. Less designed-panel monotony |
| Evidence strength | 20 | 16 | 19 | Real /report deep-scroll replaces stylized money_shot; real /cases archive replaces asserted breadth_montage |
| Timing & pacing | 15 | 15 | 15 | v2 = 179.77s, hybrid = 178.10s. Both inside 2:50-3:00 |
| Visual correctness | 15 | 14 | 14 | qa_panel_layout passes for v2 panels (inherited). Freeze/black counts comparable to v2 (75/18 vs 68/19), all absorbed by 0.35s xfade |
| Demo polish | 10 | 8 | 9 | Static-panel screen-time drops 51s → 34s (28% → 19% of runtime). Less repetition |
| **Total** | **100** | **89** | **95** | |

## Hard gates (hybrid v3)

| # | Gate | Status |
|---|---|---|
| 1 | Final exists | ✅ `final/blackbox_demo_final.mp4` |
| 2 | Duration ∈ [2:50, 3:00] | ✅ 178.10s = 2:58.10 |
| 3 | 1920×1080 | ✅ |
| 4 | 30 fps CFR | ✅ `r_frame_rate=30/1` |
| 5 | h264 + AAC | ✅ `codec=h264`, `codec=aac` |
| 6 | No text overlap in sampled frames | ✅ contact_sheet inspection |
| 7 | No fake UI | ✅ swap clips are real Playwright captures (06_patch_diff_ui, 07_cases_archive_ui) |
| 8 | Refutation beat clear | ✅ operator_vs_blackbox panel preserved verbatim |
| 9 | Better than v2 baseline on evidence + variety | ✅ 95 > 89 by reduced static panels and real diff/cases UI |
| 10 | Captions provided | ✅ `final/blackbox_demo_final.srt` (silent AAC track; SRT non-destructive) |

## Why hybrid wins
- v2 already passed all engineering hard gates; cleanroom re-cut would regress the documented v2 fixes (transition pipeline, layout-safe panels, freeze-trim).
- Hybrid keeps every v2 fix and only swaps two surgical points where v2's designed-panel surfaces could be replaced by real UI captures of the same palette and resolution.
- Net effect: 17 fewer seconds of static designed-panel screen-time, two beats now demonstrated rather than asserted, no new captions or layouts to QA.

## Known limitations
- Audio track is silent AAC. No real VO recording exists in the repo. SRT ships alongside for downstream voiceover lay-in or burn-in.
- Visual QA used contact-sheet sampling (1 frame per 3s = 60 frames) plus freeze/black detection. Frame-by-frame human review of every cut transition was not performed.
- Two designed panels remain (operator_vs_blackbox, opus47_delta). Both are load-bearing for the climax + model-delta beats; preserved verbatim from v2.
