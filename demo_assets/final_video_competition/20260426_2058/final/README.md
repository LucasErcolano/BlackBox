# BlackBox demo · final delivery (hybrid v3)

## Chosen approach
Hybrid v3 = v2 backbone (preferred baseline) + two surgical real-UI swaps. Score 95/100 vs v2 baseline 89/100.

## Why it won
v2 already passed every engineering hard gate (transitions, layout-safe panels, freeze trim, duration). A cleanroom re-cut would have regressed those fixes. The hybrid keeps every v2 improvement and patches v2's only remaining weakness — 51s of static designed-panel screen-time (28% of runtime). Two of the three designed panels were replaceable with real UI captures of the exact same palette: `06_patch_diff_ui.mp4` (real /report deep-scroll) and `07_cases_archive_ui.mp4` (real /cases archive). The third (operator_vs_blackbox climax panel) was preserved verbatim because it is the load-bearing refutation beat.

## Evidence
- `final/contact_sheet_final.jpg` — 6×10 grid, 1 frame per 3s. Visible variety in second half (rows 5-7) where v2 was monotonous.
- `final/visual_qa_report.md` — per-beat verification + automated freeze/black counts vs v2.
- `final/scorecard_final.md` — full rubric scoring vs v2 baseline.
- `qa_baseline/v2_contactsheet.jpg` and `drafts/hybrid/contactsheet.jpg` for direct A/B comparison.

## Known limitations
- **Silent AAC audio.** No real VO recording exists in the repo. SRT ships alongside (`blackbox_demo_final.srt`) for downstream voiceover lay-in. Did not generate synthetic VO per the user's non-negotiable constraint.
- **Two designed panels remain** (operator_vs_blackbox, opus47_delta_panel). Both are load-bearing and were specifically called out in the editor handoff. Preserved verbatim.
- Visual QA used contact-sheet + automated detectors; not frame-by-frame human review. Sufficient for the 30fps panel-heavy content but a polished VFX pass could be added later.

## Exact output paths
- `final/blackbox_demo_final.mp4` — 178.10s, 1920×1080@30, h264 + AAC silent stereo (the deliverable).
- `final/blackbox_demo_final_no_audio.mp4` — same video, no audio track.
- `final/blackbox_demo_final.srt` — caption track, 12 cues aligned to script beats.
- `final/timeline_final.json` — per-segment timeline with cumulative xfade math.
- `final/contact_sheet_final.jpg` — 60-frame visual grid.
- `final/scorecard_final.md` — rubric vs v2.
- `final/visual_qa_report.md` — per-beat findings.
- `final/production_ledger.md` — decisions and command history.

## How to re-render
```bash
cd /home/hz/Desktop/BlackBox
.venv/bin/python demo_assets/final_video_competition/20260426_2058/build_hybrid.py
```
Source clips referenced (read-only):
- `demo_assets/final_demo_pack/trimmed_clips/block_*.mp4`
- `demo_assets/final_demo_pack/panels/{operator_vs_blackbox,opus47_delta_panel}.png`
- `demo_assets/editor_raw_footage_pack/clips/06_patch_diff_ui.mp4`
- `demo_assets/editor_raw_footage_pack/clips/07_cases_archive_ui.mp4`
