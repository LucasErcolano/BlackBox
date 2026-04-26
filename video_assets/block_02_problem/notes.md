# block_02_problem — notes

## Visual continuity with block_01_hook
Same palette (bg #0a0c10, amber #ffb840), same fonts (DejaVu Sans + Mono), same 80px grid backdrop, same drop-shadow recipe, same 350ms eased crossfade between beats, same 4-dot progress indicator. Drops into a sequence with block_01 without any stylistic seam.

## What is real
- Repo tree text — hand-curated from the actual top-level layout of this repo (`src/`, `data/`, `demo_assets/`, `black-box-bench/`, `scripts/`, `docs/`). Paths exist.
- Folder-listing panels — real entries taken from `ls` of: `data/bags/` (1_cam-lidar.bag @ 55.8 GB is the real size), `demo_assets/bag_footage/` (3 sessions), `black-box-bench/cases/` (7 cases), `scripts/` (37 real filenames), `docs/`.
- Evidence tiles:
  - video tile → real frame from `demo_assets/bag_footage/car_1/frame_0045s.jpg`
  - plot tile → real `demo_assets/diff_viewer/moving_base_rover.png`
  - log tile → real first 6 records of `data/costs.jsonl` rendered as `cached/uncached/out/usd`
  - controller tile → compact PID `step()` modeled on `src/black_box/synthesis/controllers.py` (shape-accurate, not byte-identical — fits tile width)
  - trace tile → `rosbag info` style header (numbers reflect real bag: 42 topics, 55.8 GB, 305.5s)

## What is composited
- Title text, overlays, grid, drop shadows, vignette, amber traversal outline, beat crossfades, tile stagger, tree scroll — all PIL-composited.
- Beat D background is the Beat C tile composite dimmed to 22% alpha for visual continuity.

## What is placeholder
- Controller snippet is shape-accurate but reformatted to fit tile width. The real file is longer; this is a representative excerpt, not an exact substring.
- Rosbag info numbers come from the real bag size and typical topic mix for this session; exact per-topic message counts are illustrative (no rosbag info command was run for this render).

## Why this block supports the VO
- "More sessions than any human can review" → title + tree establishes the scale of a single repo working directory.
- "Logs, video, controller behavior, sensor traces" → four of the five tiles map 1:1 to those four words; the fifth (plots) is an adjacent real artifact type.
- "Evidence is there, but the forensic work is still manual" → final lockup says it plainly with amber emphasis on "Manual forensic work."

## Why it is UI-independent
No FastAPI/HTMX screens. No "live analysis" chrome. No dashboards. Every panel is either a filesystem listing, a plain-text code/log/trace block, or a real image artifact. Rendering does not read from the running UI.

## Final-ready?
Yes. Drops into the final edit as the 11–24.5s segment (assuming block_01 at 0–11s).

## What should be regenerated later
- If editorial swaps the hero case, update `FRAME`/`PLOT` constants in the render script.
- If VO timing slips, pad beat D by 500ms (trivial edit in `SEG_BOUNDS`).
- If branding lands, swap title font and amber hex globally.

## Reproduce
```
python3 scripts/render_block_02_problem.py
```
Outputs `video_assets/block_02_problem/{clip.mp4,preview.png}`.
