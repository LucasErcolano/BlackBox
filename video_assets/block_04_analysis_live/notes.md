# block_04_analysis_live — notes

## Run mode on camera
**REPLAY.** The underlying event stream is `data/final_runs/sanfer_tunnel/stream_events.jsonl` (97 recorded events from a real ForensicSession run on the sanfer_tunnel bag). Badge shown in the UI reads `▶ REPLAY` with the amber-family styling from `src/black_box/ui/static/style.css` L277-286. Not live. Not sample. Never disguised.

## UI surfaces captured / recreated
Recreated pixel-faithfully (structure, not CSS theme) from `src/black_box/ui/templates/progress.html`:
- sticky header: `case` label + `case_name` + `source-badge` + elapsed + spend
- `stage-pills` list with active modifier (ingest / analyze / report)
- `progress-head` stage label + percentage
- `.bar` progress rect
- `.reasoning-stream` with header, stream dot, scrolling pre, blinking cursor
- `.meta` row with job / mode / source

## What is real
- every reasoning-stream line is a real event from `data/final_runs/sanfer_tunnel/stream_events.jsonl`, formatted identically to `black_box.ui.app._fmt_replay_event` (tool_call / tool_result / assistant / reasoning)
- every filename in the `scanning evidence` panel is a real artifact inside `data/final_runs/sanfer_tunnel/bundle/` or `/mnt/session/uploads/`
- every candidate moment (timestamp + label) is `analysis.json['timeline'][0,1,2,4]` verbatim
- every ranked hypothesis (confidence + summary) is `analysis.json['hypotheses'][0..3]` verbatim, including the REFUTED entry which is drawn struck-through in `MUTED_RED`
- case name `sanfer_tunnel` matches `analysis.json['case']`
- source badge label and glyph match `_SOURCE_LABELS['replay']` in `black_box.ui.app`

## What is composited
- progress card is rendered with PIL into the dark film palette instead of captured from a running browser, because the shipped UI is light-themed and would fracture the film language shared across blocks 01-10
- progress-bar percentage interpolates 0.10 → 0.88 over 21s; the real replay finishes much faster so this is a presentation schedule, not a captured clock
- elapsed and spend counters tick in demo time, not wall time, for the same reason
- stage pill advances ingest → analyze at t=3.5s; never advances to report

## What is placeholder
Nothing is placeholder. The visual frame is composited; every piece of *content* (text, numbers, filenames, timestamps, confidence values) is pulled from repo artifacts.

## UI independence
**UI-dependent in content, UI-independent in render pipeline.** The block reads `progress.html`, `style.css`, `analysis.json`, and `stream_events.jsonl` directly — it does not require the FastAPI app to be running. It will regenerate correctly on any machine with DejaVu fonts and the repo checked out.

## Final-ready or partial
**PARTIAL_NOW.** Ready to ship as part of the 3-minute cut. Optional upgrade path: replace with a real browser capture once the UI has a dark-theme mode, or once a video-mode CSS override is added. See `manifest.json.remaining_work`.

## Why this block supports the VO
| VO phrase | visual support |
|-----------|----------------|
| "fuses heterogeneous artifacts" | `scanning evidence` panel tags 4 classes: TELEMETRY / DIAGNOSTICS / VIDEO / CONTROLLER, each with real filenames |
| "telemetry, video, and controller context" | those three classes are visually distinct (amber / red / blue-ish / green strips) |
| "scans the full session" | progress bar advancing ingest → analyze; 50 real reasoning events streaming |
| "surfaces moments worth review" | `candidate moments` panel with 4 real timestamped timeline entries |
| "cross-checks signals against each other" | `cross-checking` phase with amber hairline connectors between telemetry, diagnostics, and video rows |
| "ranks only the hypotheses that survive the evidence" | `ranked hypotheses` panel with confidence bars and a REFUTED row struck through — survival is visible |

## Visual continuity with prior blocks
- same BG `#0a0c10`, FG `#e6e8ec`, ACCENT `#ffb840`, MUTED_AMBER / MUTED_RED / STRIKE values as blocks 01-10
- same DejaVu Sans / Sans Mono typography stack
- same 80 px grid backdrop (`grid_bg` helper, identical to blocks 02/03/07)
- same drop-shadow recipe (`shadow_for(pad=18, alpha=130, blur=16)`)
- beat-dot indicator at bottom uses the same pattern as blocks 02/03/07 but advances 5 dots instead of 4 (this block has 5 phases)
- cross-block narrative beat: block_03 ended on `find what matters.` lockup; this block is the literal act of finding — the engine turning on. It does **not** reveal the answer (that belongs to blocks_05/_06).

## Anything to regenerate later?
- if final edit wants the block to run a real browser capture of the progress UI (post dark-theme), rerun with a headless Chromium script instead of `scripts/render_block_04_analysis_live.py`
- if VO lands at <20s or >22s, adjust `DUR` and redistribute the 5 phase centers proportionally
- if the sanfer_tunnel stream is ever re-recorded, the reasoning lines will update automatically on re-render (pure function of the file)
