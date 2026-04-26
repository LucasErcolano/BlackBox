# block_05_first_moment — notes

## What is real
- **Session identity** — real rosbag at `/mnt/ssd_boat/rosbag2_2025_09_17-14_01_14`, 13.7 GB `.db3`, declared duration 416.76 s. Source path shown on screen is the actual mount.
- **Stream counts** — `/lidar_imu` msg_count=0 and `/lidar_points` n=4318 / 10.00 Hz / median_dt 100.0 ms come verbatim from `data/runs/boat_lidar_rerun/report.md`, which was produced by a real `scripts/run_session.py` pass over the bag this session. No fixture numbers.
- **Diagnosis** — `sensor_timeout` with confidence 0.95 is the real output of `_classify_moment` for the silent-IMU / healthy-points pattern; the contract is asserted by `tests/test_no_camera_pipeline.py::test_silent_imu_classifies_as_sensor_timeout`.
- **"Not a QoS mismatch"** — direct quote from the generated `patch_hint` in the re-run report. The three "why not QoS" bullets (identical QoS advertised, no recorder warnings, zero emissions) mirror the reasoning the pipeline already encodes.
- **Driver-param footer** (`imu_publish`, `imu_port`) — same tokens the `patch_hint` surfaces for Ouster/Velodyne.

## What is composited
- All layout, typography, color, card geometry, staggered reveal timings, strike-through and REJECTED tag. No screenshot of a product UI is used.
- The "session metadata" card on beat A is a hand-built summary of real values — no UI element of the actual tool is shown.
- The 4-dot beat indicator is the same shared film-language element used in blocks 01/02/07/08.

## What is placeholder
- Nothing. All on-screen numbers, topic names, message types, paths, and classifications are sourced from real artifacts in the repo / mounted bag.

## UI-independence
- UI-independent. Renders entirely from PIL + ffmpeg. No browser, no product app. Survives full UI change.

## Why this block supports the VO
- "Here. USV session, 416 seconds." → beat A opens on the USV case and shows `416.76 s` at hero size.
- "LIDAR companion IMU was declared but never published a single message" → left card on beat B, `SILENT · 0 messages published across entire session`, 0.00 Hz.
- "while the point cloud stream on the same sensor ran nominal at 10 Hz" → right card, `NOMINAL · 4318 · 10.00 Hz`, connector labeling "same LIDAR sensor pod".
- "A silent driver failure, not a QoS mismatch." → beat C rejects QoS with strike + REJECTED, beat D lockup "silent driver failure." in ACCENT amber with `bug_class sensor_timeout · 0.95 · session-global`.
- Session-global framing is preserved: no moment spike, no timestamp pulse; instead, "0 across entire session" vs "4318 over 416.76 s" hammered at hero scale.

## Visual continuity with finished blocks
- **Palette**: same BG (#0a0c10), FG (#e6e8ec), DIM (#78808c), PANEL (#12141a), BORDER (#3c424e).
- **Accent**: full ACCENT amber (#ffb840) re-enters (matches block_01/02/08), as expected for a finding beat after block_07's stricter muted-amber treatment.
- **Rejection language** (strike-through + MUTED_RED #aa5656 + REJECTED tag) is borrowed verbatim from block_07.
- **Typography**: DejaVu Sans / Sans Mono, same weight ramp as prior blocks.
- **Grid**: 80 px grid backdrop, identical to 01/02/07/08.
- **Beat dots**: same 4-dot indicator, bottom-center, label "block 05 · first finding".
- **Shadow recipe**: same `shadow_for()` (pad 20, alpha 140, blur 18).
- **Transitions**: 450 ms smoothstep crossfades — same pacing family as block_07 (clinical) and block_08 (payoff); midway between them in energy.

## Energy compared with neighboring blocks
- **vs block_07**: re-introduces full amber and forward motion; staggered card reveal instead of long clinical holds.
- **vs block_08**: no BUG/FIX lockup, no amber flood on added lines, no hero diff. The diagnosis lockup is a single amber phrase, not a payoff scoreboard. This block announces evidence, block_08 delivers the patch.

## Regenerate later if
- the re-run report's `/lidar_points` count changes (currently 4318 vs raw metadata 4168 — the pipeline re-counted from the actual `.db3`, trust the re-run); update the "4318" overlay in `render_block_05_first_moment.py` and the manifest.
- the VO timing shifts; beat D hold (5.5 s) is the easiest to compress.
- additional supporting evidence becomes available (e.g. `/rosout` driver error lines) — can be added as a 4th bullet to the "why not QoS" panel without disturbing layout.

## Status
- **FINAL_READY** for the 3-minute cut.
