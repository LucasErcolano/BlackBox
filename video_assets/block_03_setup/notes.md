# block_03_setup — notes

## Exact session assets used
- `data/final_runs/boat_lidar/bundle/summary.json` — real. Case `boat_lidar`, duration 416.76 s, platform "unmanned surface vessel (USV), LIDAR-only", sensor counts `/lidar_points=4168` and `/lidar_imu=0` (silent stream), bag_recovery_note about malformed sqlite3.
- `data/final_runs/sanfer_tunnel/bundle/summary.json` — real. Case `sanfer_tunnel`, session_duration_s 3626.8, vehicle_platform "Lincoln MKZ drive-by-wire, dual-antenna u-blox RTK", artifact list (CSVs + frames).
- `data/final_runs/sanfer_tunnel/bundle/frames/frame_00000.0s_dense.jpg`, `frame_01036.3s_base.jpg`, `frame_02072.5s_base.jpg` — three real extracted frames used as thumbnails in beat C.

## What is real
- Both session folders exist on disk at `data/final_runs/boat_lidar/` and `data/final_runs/sanfer_tunnel/`.
- All numeric facts on screen (durations, platforms, message counts, row counts) come straight from the summary JSONs.
- `$ ls data/final_runs/` listing is a real intake subset: the repo also contains `car_0/`, `car_1/`, and `.memory/` siblings, but this block intentionally shows only the two sessions that make it into the film — no invented entries.
- Artifact names (metadata.yaml, /lidar_points, /lidar_imu, ublox_rover_navrelposned.csv, ublox_rover_navpvt.csv, diagnostics_nonzero_unique.csv, bag_recovery_note) are verbatim from the summaries.
- Sanfer NavRELPOSNED row count (18,133) matches `topics.txt` (`/ublox_rover/navrelposned n=18133`).
- Palette, fonts, grid, drop-shadow, beat-dot indicator — identical to blocks 01/02/05/06/07/08/09/10.

## What is composited
- Layout, typography, two-card side-by-side session view, two-column evidence view, UNSEEN badge, column eyebrows, strike-through animation, final lockup.
- The `session_manifest.json` cards are compositional — no literal `session_manifest.json` file exists in the repo; the values in them are read from the real `summary.json` files, so the card is a styled view of real data, not a fiction.
- The `ls` listing only shows `boat_lidar/` and `sanfer_tunnel/` side-by-side — the actual `data/final_runs/` directory has a couple of other entries that are not featured in the film.

## What is placeholder
- None of the on-screen text is placeholder. Every label, artifact name, count, and duration is either real or a direct render of a real summary field.
- Boat column shows pills only because the boat session is LIDAR-only with no cameras — this is accurate, not a missing asset. Could later add a pointcloud still if desired (see `remaining_work` in manifest).

## Why this block supports the VO
- "I give Black Box sessions it has never seen." → beat A reveals two real folders with UNSEEN tag.
- "No labels. No handcrafted rubric." → beat B shows both cards with `prior labels: none` / `prior rubric: none`; beat D makes the negation explicit with strike-through.
- "Just raw evidence." → beat C lays out per-session raw artifact pills + real sanfer frame tiles, under the "no curation · no pre-sorting" subtitle.
- "Find what matters, reject what doesn't, return a grounded hypothesis." → beat D final lockup `find what matters.` + `reject what doesn't · return a grounded hypothesis`.

## Visual continuity with finished blocks
- **Palette**: identical BG/FG/DIM/PANEL/BORDER/ACCENT/MUTED_AMBER to blocks 01/02/05/06/07/08/09/10.
- **Typography**: DejaVu Sans / Sans Mono, same weight ramp.
- **Grid**: 80 px backdrop, same as prior blocks.
- **Shadow recipe**: same `shadow_for()` (pad 20, alpha 140, blur 18) from 05/06/07/09.
- **Beat dots**: same 4-dot indicator, bottom-center, active dot advances per beat, label `block 03 · setup`.
- **Amber rationing**: ACCENT only on (a) hairlines under eyebrows, (b) UNSEEN tag outline, (c) final lockup underline. MUTED_AMBER on column eyebrows and pill strips. MUTED_RED only on the silent /lidar_imu pill strip and on the strike-through lines — matches block_02's red-for-anomaly discipline without introducing a finding.
- **Crossfade cadence**: 0.40 s smoothstep between beats — sits between block_02 (0.35) and block_07 (0.45), bridging the two tonalities.

## Energy compared with neighboring blocks
- **vs block_02_problem**: narrower and more controlled. Block_02 is evidence-overload across many artifacts; block_03 reduces to exactly two sessions and a small per-session pill grid. Still uses the same visual language, but the artifact count on screen is about half.
- **vs block_05/06**: strictly anticipatory. No RTK carr_soln bar, no timeline, no anomaly spike, no convergence graph, no ranked hypotheses. Beat C intentionally stops at artifact inventory so 05/06 can carry the actual findings.
- **vs block_10_outro**: block_03 is the intake mirror of block_10's output. Block_10 shows one deliverable bundle; block_03 shows two intake bundles.

## UI-independence
- Fully UI-independent. Renders from PIL + ffmpeg only. No product UI, no dashboard, no drag-and-drop, no upload form, no live-analysis screen.

## Regenerate later if
- final edit wants a real LIDAR pointcloud still for the boat column instead of pills-only → generate one from `/lidar_points` via rosbags + matplotlib and swap into beat C's boat column.
- VO lands before/after 14.5 s → the easiest knob is the hold length of beat D (`phase_swap` in `make_lockup_beat`, currently 2.1 s).
- a single additional session (e.g., `car_0/`) is added to the film → extend `ls` listing in beat A and add a third column in beat C; beat B's two-card layout would need to become three cards.

## Status
- **FINAL_READY** for the 3-minute cut.
