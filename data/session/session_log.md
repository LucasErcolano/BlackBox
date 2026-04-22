# Black Box — Autonomous Session Log

Start: 2026-04-22
Operator: Opus 4.7 autonomous run

## Phase 0 — Environment

- `df -h`: No /mnt/ssd mount. `/dev/sda2` = 140GB free, `/dev/sdb1` (HDD) = 233GB free.
- Bags (all on HDD):
  - `/mnt/hdd/0_cam-lidar.bag` — 206 GB
  - `/mnt/hdd/1_cam-lidar.bag` — 55 GB (smallest)
  - `/mnt/hdd/3_cam-lidar.bag` — 74 GB
- Cache dir: `/home/hz/blackbox_cache/` (on sda2, since no SSD mount exists).

## DECISION NEEDED: bag copy strategy.
Operator default: do NOT copy full bags — bag 0 (206GB) exceeds free space, full copy of any bag burns 15-30 min of IO. Instead: stream directly from HDD once, extract only 30-second windows, cache decoded frames + telemetry arrays. Re-reads come from SSD cache, not HDD. This matches the stated optimization goal ("no re-extract if analyzed twice") at lower IO cost.

## Plan
1. Phase 1: inspect bag 1 (smallest) — enumerate topics, freqs, duration.
2. Phase 2: stream 30s central window, decode compressed images, save PNGs + npz.
3. Phase 3: plot real telemetry.
4. Phase 4: Claude scenario mining, one bag.
5. Phase 5: repeat on bags 3 and 0 (if time + budget).
6. Phase 6: summary + commit.

## Phase 1 — Bag 1 inspection (DONE)

- Duration: 970.2s (~16 min)
- Topics (5 cameras CompressedImage + lidar + 5 camera_info):
  - `/cam1/image_raw/compressed` 9.7 Hz (front_left guess)
  - `/cam3/image_raw/compressed` 30 Hz (left)
  - `/cam4/image_raw/compressed` 30 Hz (rear)
  - `/cam5/image_raw/compressed` 9.7 Hz (front_right)
  - `/cam6/image_raw/compressed` 30 Hz (right)
  - `/velodyne_points` 9.8 Hz
- Message type: `sensor_msgs/msg/CompressedImage` (ROS2-style typename, but bag is ROS1 — rosbags lib normalizes).
- Topic prefix IS `/camN/image_raw/compressed` (NOT flat `cam1_image_raw_compressed`). User's guess was close but topics are namespaced.
- **CRITICAL finding**: no odometry / IMU / velocity / steering / cmd_vel / GPS topics. Dataset is PURELY visual + lidar.
- Cam1 & cam5 are at 10 Hz; cam3/4/6 at 30 Hz. Asymmetric — cam1/5 likely fisheye/higher-res (hence slower), cam3/4/6 narrow/faster.

## DECISION NEEDED: no telemetry topics.
Operator default: scenario-mining prompt will use frames-only (no plots). Re-label Phase 3 as "skip plots, use frame timestamps directly". This still delivers demo value (cross-view visual anomaly detection) and matches the hard rule "conservative — say nothing anomalous if nothing is found".

## Phase 2 (bag 1, window 470-500s, 8 frames/cam) — DONE
- 57s wall. 40 frames saved at 800×600.

## Phase 4 v1 (scenario mining, bag 1 central 30s) — DONE
- Cost: $0.4579 (0 cached / 26864 uncached / 218 output tokens).
- Result: `moments=[]`, rationale cites "consistent residential street driving, no anomalies". Conservative behavior working.

## UPDATE from operator: video-only pipeline v2
Applied changes (2026-04-22):
1. Scenario-mining prompt reframed (AV forensic analyst framing, visual-only cues, inferred motion, cross-camera inconsistency).
2. Multi-window sampling: 3 windows × 20s per bag (start / middle / end), ~1 frame / sec = 20 frames/cam/window (100/window total).
3. Two-stage: cheap 400×300 summary pass ("describe each 20s window in 2 sentences per cam") → filter → deep pass only on interesting windows.
4. Explicit prompt language re: inferring ego-motion from consecutive frames.
5. PDF generator + repo structure unchanged.

## Phase 2/3/4 (v2 bag 1) — DONE
- Extraction: 135s wall. 3 windows × 20 frames/cam × 5 cams × 2 res (big+small) = 600 files.
- Summary pass × 3 windows: start interesting, middle+end uneventful. $0.30 total.
- Deep pass × 1 window (start only, because summary filter worked): 5 moments. $1.19.
- Total bag 1 v2: $1.50. Wall 96s.
- Top finding: front-camera overexposure (confidence 0.95).

## Phase 2/3/4 (v2 bag 3) — DONE
- Extraction: 47s (second attempt — first attempt stuck reading 4GB without producing output, killed & retried; second attempt was clean).
- Summary pass × 3: start interesting, middle uneventful, end interesting.
- Deep pass × 2 (start + end). 6 moments total. $1.08 + $1.13.
- Total bag 3 v2: $2.52. Wall 126s.
- Top findings: pedestrian at gated checkpoint (0.70); oncoming vehicle close passes (0.70 / 0.55); sun glare (0.60).

## Phase 2/3/4 (v2 bag 0) — SKIPPED
- Bag 0 is 206 GB on HDD. Two extraction attempts — both stuck in `AnyReader.__enter__` phase reading multiple GB without producing the first frame.
- Probe (just opening reader): 227 MB read in 17s at ~20 MB/s. Extrapolated full-open time: ~2.8 hours (and extraction would require more reads after that).
- Diagnosis: bag 0 likely has no bag index at EOF (or rosbags lib is scanning chunk-by-chunk for this file), forcing a linear scan. Without `rosbag reindex` (ROS1 CLI) to repair/add a proper index, rosbags lib can't seek efficiently for this bag.
- Budget check: continuing would burn ≥3 hrs of wallclock on extraction alone for questionable return. SKIPPING per rule "Si te empantanás en debugging de un error: 15 min MAX, después workaround o skip."
- Workaround for future session: run `rosbag reindex` (requires ROS1 install on a machine with capacity), or copy bag 0 to SSD once SSD has 210+ GB free, or slice bag 0 into smaller bags with `rosbag filter --duration` first.

## Phase 6 (summary + commit) — DONE

- SESSION_SUMMARY.md written, copied into `data/session/`.
- Hero deep-dive on bag 1 overexposure: $0.48, anomaly_class=sensor_overexposure, conf=0.93, onset→recovery 4.5s, root cause = AE startup convergence failure. Full JSON at `data/session/analyses/hero_bag1_overexposure/hero_report.json`.
- `git init` + initial commit `0639b7c`. 81 files tracked. Bags/frames/reports excluded by .gitignore.
- Final session spend: **$5.01** of $30 cap.


