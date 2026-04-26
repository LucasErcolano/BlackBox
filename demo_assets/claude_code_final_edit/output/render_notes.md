# render_notes.md — Black Box demo (Claude Code edit v1)

## Overview
- Final video: `output/blackbox_demo_claude_edit_v1.mp4`
- Captions-only version (no VO audio recorded): `blackbox_demo_claude_edit_v1_no_audio.mp4`
- Subtitles: `blackbox_demo_claude_edit_v1_captions.srt` + `.ass`
- Spec: 1920x1080, 30 fps CFR, H.264, yuv420p, 175.00 s. AAC silent stereo track muxed for player compatibility.
- Source pool: `demo_assets/editor_raw_footage_pack/clips/` (20 real UI/B-roll clips) + 2 stills.

## Pipeline (deterministic, scripted)
1. `scripts/probe_inputs.py` -> `output/input_probe.json`
2. `scripts/build_timeline.py` -> `output/timeline.json` (25 segments, 42 captions)
3. `scripts/normalize_footage.py` -> `segments/<i>_<id>.mp4` (1920x1080@30 yuv420p, fixed VF, libx264 crf 18)
4. `scripts/render_final.py`
   - concat demuxer (`-c copy`) -> `_concat.mp4`
   - burn captions (`subtitles=…ass`) -> `_no_audio.mp4`
   - mux silent AAC -> final `.mp4`
5. `scripts/qa_final.py` -> `qa_report.json`, `contact_sheet_final.png`, `transition_contact_sheet.png`

## QA results
- Spec checks (duration, resolution, fps, codec, pix_fmt): **PASS** on every check.
- `qa_report.json.overall` = `PASS`.
- `freezedetect` flagged ~12 windows. Expected and intentional:
  - Stills held 3–4 s (`r3` operator_refutation.png, `px2` patch_diff.png).
  - Slow text/scroll clips (intake hero, agent stream feed, doc scroll) carry mostly static UI between scroll bursts; that is the source content, not a transition glitch.
  - No mid-segment frozen-fade artefacts; transitions are clean hard cuts.

## Editorial decisions
- Hard cuts only (no crossfades): every clip already shares 1920x1080@30 yuv420p, so cuts are clean and read like a premium technical demo. Crossfades skipped to avoid timebase drift.
- Captions are the primary explanatory layer (no VO audio recorded). ASS style: Inter 40px white with black outline, bottom-center, MarginV 80, MarginL/R 80 — readable at 1080p, never overlaps the active UI region above 920 px.
- Caption text is condensed from the supplied VO script — 8-word max per line, max 2 lines, never paragraph overlays.
- Opus 4.7 vs 4.6 beat uses the existing `19_opus47_delta_panel_real_capture.mp4`, `17_opus47_delta_doc_scroll.mp4` (cropped to readable middle window 5–12 s) and `20_vision_ab_artifact.mp4`. No fake panel rebuilt.
- Refutation and Patch beats hold a real PNG still for 3–4 s so viewers can read the line "operator hypothesis: refuted" and "engineer approves" without UI motion competing.

## What is NOT used
- No Remotion. No AI-generated terminal animation. No synthetic product UI.
- No on-screen voiceover synthesis. Audio track is silent (AAC null source).
- No transitions other than hard cuts.

## Caveats vs the human editor cut
- We have no real VO audio yet, so pacing is governed by the script's natural cadence (matched 1:1 to caption timing). A human editor with VO recorded may pull tighter on Hook + Outro.
- Some live-UI clips (02_live_analysis_ui, 06_patch_diff_ui) include their own scroll cadence; we did not retime, so caption rhythm follows clip rhythm rather than ideal speech rhythm.
- Boat case uses `15_boat_report_broll.mp4` (markdown report scroll) because no boat camera frames exist in the repo (documented in editor_raw_footage_pack `missing_assets.md`).
- 4 s outro reuses tail of `07_cases_archive_ui.mp4` because no dedicated benchmark/cost still ships in the pack.

## Reproduce
```bash
cd /home/hz/Desktop/BlackBox
python3 demo_assets/claude_code_final_edit/scripts/probe_inputs.py
python3 demo_assets/claude_code_final_edit/scripts/build_timeline.py
python3 demo_assets/claude_code_final_edit/scripts/normalize_footage.py
python3 demo_assets/claude_code_final_edit/scripts/render_final.py
python3 demo_assets/claude_code_final_edit/scripts/qa_final.py
```
