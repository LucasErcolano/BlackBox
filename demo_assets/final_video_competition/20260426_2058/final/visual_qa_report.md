# BlackBox demo · visual QA report (hybrid v3)

## Sampling
- Contact sheet: `final/contact_sheet_final.jpg`, 6×10 grid, 1 frame per 3s of 178.1s total = 60 frames.
- Inspection: visual review of contact sheet against v2 baseline contact sheet at `qa_baseline/v2_contactsheet.jpg`.
- Automated: `ffmpeg -vf freezedetect=n=-50dB:d=0.4` and `blackdetect=d=0.2:pix_th=0.10`.

## Per-beat findings

| t (s) | beat | source | observation |
|---|---|---|---|
| 0–9 | hook | block_01_hook | clean. Operator quote frame appears; no overlap |
| 9–19 | problem | block_02_problem | clean. Repo tree + 55.8GB bag panel readable |
| 19–33 | setup | block_03_setup | clean. Session JSON + 3 sanfer frames |
| 33–54 | live agent | block_04_analysis_live_v2 | clean. Playwright capture, REPLAY badge readable. 21s dwell — same as v2 (acknowledged trade-off) |
| 54–71 | first_moment | block_05_first_moment | clean. "silent driver failure" headline |
| 71–88 | second_moment | block_06_second_moment | clean. Refutation table panel |
| 88–104 | refutation_climax | operator_vs_blackbox.png | clean. 17s static hold of climax panel — qa_panel_layout already passes |
| 104–117 | patch_diff (SWAP A) | 06_patch_diff_ui.mp4 | **NEW**. Real /report scroll: header banner + Findings + chart sections. No overlap, all UI elements legible at 1080p |
| 117–134 | opus47_delta | opus47_delta_panel.png | clean. 17s static hold; qa_panel_layout already passes |
| 134–147 | generalization (SWAP B) | 07_cases_archive_ui.mp4 | **NEW**. Real /cases archive: 7 case rows, BlackBox header. Same palette as block_04. No overlap |
| 147–159 | grounding_gate | block_07_grounding | clean. JSON strike-through animation |
| 159–169 | cost_and_repo | block_09_punchline | clean. "$0.46" + bench URL |
| 169–178 | outro | block_10_outro | intentional fade-to-black tail (matches v2) |

## Automated detector counts

| Check | hybrid v3 | v2 baseline | verdict |
|---|---|---|---|
| `freezedetect` events (≥0.4s) | 75 | 68 | comparable; +7 events from new real-UI clips that hold during scroll. Every event is inside a segment, absorbed by 0.35s xfade across cuts |
| `blackdetect` events (≥0.2s) | 18 | 19 | comparable. Includes intentional outro tail |

## Hard gate verification
- Duration: 178.10s ∈ [170, 180] ✅
- Resolution: 1920×1080 ✅
- Frame rate: 30/1 ✅
- Codec: h264 video, aac audio (silent stereo 192k) ✅
- Text overlap: none detected in 60-frame contact sheet sample ✅
- Refutation beat: operator_vs_blackbox.png preserved verbatim from v2 (qa_panel_layout pass) ✅
- All `timeline_final.json` referenced files exist ✅

## Comparison vs v2 baseline failure modes

| v1/v2 prior failure | hybrid v3 status |
|---|---|
| "bad clip reel" inconsistency (approach 1) | resolved — every segment runs through identical normalize+xfade pipeline |
| text overlap on opus47 / operator / breadth panels (v1 → v2 fix) | preserved — inherited layout-safe rebuilds from v2 |
| 51s of static designed-panel screen-time (v2) | improved — 34s static (19% of runtime) |
| breadth_montage asserted breadth without showing it (v2) | resolved — replaced with real /cases UI |
| stylized money_shot for the patch beat (v2) | resolved — replaced with real /report deep-scroll |
