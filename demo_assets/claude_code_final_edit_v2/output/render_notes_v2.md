# render_notes_v2.md — Black Box demo (Claude Code edit v2)

## Overview
- Final video: `output/blackbox_demo_claude_edit_v2.mp4`
- Captions-only: `blackbox_demo_claude_edit_v2_no_audio.mp4`
- Subtitles: `..._captions.srt` + `..._captions.ass`
- Spec: 1920x1080, 30 fps CFR, H.264, yuv420p, **172.47 s (2:52.5)**. AAC silent stereo muxed.
- Source pool: `demo_assets/editor_raw_footage_pack/clips/` + 6 stills.

## Pipeline
1. `scripts/build_timeline_v2.py` -> `output/timeline_v2.json` (27 segs, 42 captions, 4 xfade boundaries).
2. `scripts/normalize_footage_v2.py` -> `segments/<i>_<id>.mp4` (1920x1080@30 yuv420p; stills with `zoom=true` get a 1.0→1.045 zoompan from a 3840x2160 source pad).
3. `scripts/render_final_v2.py`:
   - For each xfade boundary, blend `seg[i-1]` + `seg[i]` via `xfade=transition=fade:duration=0.25` into a single MP4 (`_blend_<i>.mp4`); fixes the timebase mismatch that breaks a single-pass filter_complex chain.
   - Concat-demux remaining segments (with 4 blends substituted for 8 raw segments) -> `_concat_v2.mp4`.
   - Burn captions with `subtitles=...ass` -> `_no_audio.mp4`.
   - Mux silent AAC -> final `.mp4`.
4. `scripts/qa_final_v2.py` -> `qa_report_v2.json`, `contact_sheet_v2.png`, `transition_contact_sheet_v2.png`, `v1_vs_v2_comparison.md`.

## QA results
- Spec checks: **PASS** on every check (`qa_report_v2.json.overall = PASS`).
- 13 freezedetect windows reported. All are intentional: held PNG stills (3 s each w/ subtle zoom that ffmpeg still flags below its motion threshold), or intrinsically-static UI between scrolls.

## Intentional static holds (with subtle 1.0 → 1.045 zoompan)
| id | source | duration | beat |
|----|--------|----------|------|
| r3 | `stills/operator_refutation.png` | 3.0 s | refutation verdict card |
| rc2 | `stills/rtk_root_cause_chart.png` | 3.0 s | root cause evidence |
| px2 | `stills/patch_diff.png` | 3.0 s | patch payoff |
| out1 | `stills/breadth_cases_archive.png` | 3.0 s | outro card 1 |
| out2 | `stills/hero_report_top.png` | 3.0 s | outro card 2 |

## What changed vs v1
- Hook trimmed to 11 s; "that story is wrong" lands at ~0:08.
- 4 strategic 0.25 s xfade dissolves: hook→problem, mining→refutation, patch→opus, grounding→outro. Everywhere else: hard cuts.
- Slow zoom on stills (no more dead-frame holds).
- Opus 4.7 section condensed to 16 s ("Same accuracy. Better judgment.").
- Doc-scroll usage reduced (4 s of `17_opus47_delta_doc_scroll`, 5 s of `11_sanfer_pdf_scroll`; v1 used 7 s and 8 s).
- Outro rebuilt: 2-still title-card sequence with caption payoff, replacing v1's archive-tail reuse.
- Captions tightened: ASS Inter 42 px, MarginV 72, ≤48 chars/line, increased outline for readability over UI.

## What is NOT used
- No Remotion. No AI-generated terminal. No fake UI.
- No AI voiceover (silent AAC track only).

## Caveats vs human editor cut
- No real VO audio recorded; pacing remains caption-driven.
- xfades only at 4 boundaries; everywhere else hard cuts. Some viewers may want more dissolves — kept conservative to keep evidence beats sharp.
- Outro stills are real artifacts (cases archive, report hero) — not a custom motion-graphics title.

## Reproduce
```bash
cd /home/hz/Desktop/BlackBox
python3 demo_assets/claude_code_final_edit_v2/scripts/build_timeline_v2.py
python3 demo_assets/claude_code_final_edit_v2/scripts/normalize_footage_v2.py
python3 demo_assets/claude_code_final_edit_v2/scripts/render_final_v2.py
python3 demo_assets/claude_code_final_edit_v2/scripts/qa_final_v2.py
```
