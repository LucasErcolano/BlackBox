# block_04_analysis_live_v2 — notes

## Run mode on camera
**REPLAY.** Captured live from the shipped FastAPI UI at
`/analyze?replay=sanfer_tunnel&theme=dark`. The source badge visible on camera
reads `REPLAY` (from `_SOURCE_LABELS['replay']` in `black_box.ui.app`). The
underlying event stream is the genuine
`data/final_runs/sanfer_tunnel/stream_events.jsonl` — 97 recorded events from a
real ForensicSession run, scheduled onto the demo clock by
`_run_pipeline_replay`.

## Capture method
Headless Chromium driven by Playwright, 1920x1080 viewport, dark theme enabled
via the `?theme=dark` query param honored by the theme boot script in
`src/black_box/ui/templates/index.html`. HTMX polls `/status/{job_id}` every
1 s and replaces the `#progress-card` in-place; the recording captures the
real UI as it naturally animates.

## What is real
- progress surface, sticky header, source badge, stage pills, progress bar,
  reasoning stream, meta row — **real**, rendered by `progress.html`
- every reasoning line streamed on camera — **real**, from
  `stream_events.jsonl`, formatted by `_fmt_replay_event`
- case name, mode, elapsed counter, cost badge — **real**, from
  `_progress_context`
- stage advancement (queued → ingest → analyze) — **real**, driven by
  `_run_pipeline_replay`
- colour palette, typography, badge glyphs — **real**, from the shipped
  stylesheet (no video-only CSS override)

## What is composited
Nothing inside the progress card. The only post-processing is ffmpeg transcode
(libx264 CRF 18, 30 fps, yuv420p, faststart) and a `-t 21.0` trim so the clip
lands in the 20-22 s narration window and hands off to blocks_05/_06 before
the `done` pill flips.

## Capture-readability adjustments
Outside the progress card, the capture script removes the site header, intro
copy, upload form, hero-cases grid, and footer from the DOM so the real card
dominates the 1920x1080 frame. `<main>` is widened to 1400 px, and the
reasoning panel's CSS `max-height` is bumped from 320 px to 600 px so more of
the genuine streamed reasoning is readable on camera. No content inside the
card is fabricated, reordered, or restyled — these are viewport adjustments,
not content adjustments.

## What is placeholder
Nothing.

## Why this version is more final than v1
- v1 was a PIL-composited recreation of `progress.html` in the dark film
  palette, because the shipped UI was light-themed and would have fractured
  the film language.
- The UI now supports a real dark theme. v2 captures the actual rendered UI
  under that theme. No compositing, no recreation, no risk of drift between
  the film and the product.
- Every beat the VO names (fuses artifacts, scans, cross-checks, ranks) is
  rendered by the live system itself.

## Replaces
`video_assets/block_04_analysis_live/clip.mp4` — keep v1 on disk as a
compositing reference and fallback, but the edit should pick up v2.

## Honesty
The source badge is visible and explicit throughout the clip. The mode
(`REPLAY`) is honest. No viewer can confuse this for a live run. No viewer
will see a final report; the block deliberately holds below completion.
