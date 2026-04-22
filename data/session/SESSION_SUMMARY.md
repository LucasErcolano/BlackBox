# Black Box — Autonomous Session Summary

**Date**: 2026-04-22
**Operator**: Opus 4.7 autonomous run
**Mode**: vision-only (ROS1 bags contain no telemetry topics)

## TL;DR

3 real ROS1 autonomous-vehicle bags on HDD. 5 cameras (compressed images) + velodyne lidar. NO odometry / IMU / steering / GPS topics — pipeline adapted to vision-only scenario mining. Two-stage Claude analysis (cheap summary pre-filter at 400×300 → deep forensic mining at 800×600 only on interesting windows) across 3 time-windows per bag (start/middle/end, 20 s each, 20 frames/cam).

## Phases

| Phase | Status | Note |
|------|--------|------|
| 1 Inspect bags | ✓ | Real topic names: `/camN/image_raw/compressed` for N ∈ {1,3,4,5,6}, `/velodyne_points`. No telemetry. |
| 2 Frame extraction | ✓ | 3 windows × 20 frames × 5 cams per bag. Saved at 800×600 (`_big`) + 400×300 (`_small`). |
| 3 Plots | ∅ skipped | No telemetry to plot. |
| 4 Scenario mining bag 1 | ✓ | 5 moments (overexposure, door-open, pedestrian close). |
| 5 Bags 3 (+ 0 if finished) | (see below) | |
| 6 Summary + commit | in-progress | this file |

## Bags

| Bag | Size | Duration | Status |
|-----|------|----------|--------|
| 1_cam-lidar.bag | 55 GB | 970 s | ✓ extracted + analyzed |
| 3_cam-lidar.bag | 74 GB | 1193 s | ✓ extracted + analyzed |
| 0_cam-lidar.bag | 206 GB | unknown | **SKIPPED**: AnyReader open phase stalls — bag appears to lack EOF index, forcing linear scan at ~20 MB/s ≈ 2.8 hrs just to open. Two extraction attempts killed after 3 min each (no frames produced). Workaround: `rosbag reindex` (ROS1 CLI) or slice with `rosbag filter` before using rosbags lib. |

## Topics (confirmed)

```
/cam1/image_raw/compressed  sensor_msgs/CompressedImage  ~10 Hz  (front_left)
/cam5/image_raw/compressed  sensor_msgs/CompressedImage  ~10 Hz  (front_right)
/cam6/image_raw/compressed  sensor_msgs/CompressedImage  ~30 Hz  (right)
/cam4/image_raw/compressed  sensor_msgs/CompressedImage  ~30 Hz  (rear)
/cam3/image_raw/compressed  sensor_msgs/CompressedImage  ~30 Hz  (left)
/velodyne_points            sensor_msgs/PointCloud2      ~10 Hz
```

## Moments of Interest (combined, ranked by confidence)

### Bag 1 — start window (15-35 s)
- **0.95** Severe overexposure on front_left + front_right cameras — sensor failure or extreme exposure fault. Data-quality anomaly.
- **0.90** Recurrent front-camera overexposure after recovery — suggests persistent auto-exposure issue.
- **0.80** Ego vehicle stationary for extended period — confirmed visually (side/rear scenes identical across frames).
- **0.75** Person at close range to left side of vehicle — door-open scenario.
- **0.70** Rear camera shows indoor garage while other cameras show outdoor lot — mixed indoor/outdoor view at startup.

### Bag 3 — end window (~1158-1178 s)
- **0.70** Pedestrian near traffic cones at gated checkpoint / level crossing (cam_left).
- **0.60** Lens flare / sun glare artifact in forward view.
- **0.55** Oncoming vehicle close pass on narrow tree-lined street.
- **0.40** Possible near-stall / very low forward progress.

### Bag 3 — start window (15-35 s)
- **0.70** Oncoming white SUV passing at close range.
- **0.60** Roundabout / traffic island negotiation.

### Bag 3 — middle window — nothing flagged by summary pass (savings).

## Cost summary

(See `data/costs.jsonl` for full log.)

| Call | Kind | Tokens in (unc/cache_read) | Tokens out | USD | Wall s |
|------|------|---------------------------|-----------|----|--------|
| old smoke (synth_qa) | unknown | 2058/2058 | 826 | $0.055 | 12 |
| old smoke (scenario mining) | unknown | 26864/0 | 218 | $0.458 | 14 |
| bag1 v2 summary start | window_summary_v2 | 4430/0 | 515 | $0.105 | 13 |
| bag1 v2 deep start | visual_mining_v2 | 67101/0 | 2483 | $1.193 | 58 |
| bag1 v2 summary middle | window_summary_v2 | 4430/0 | 422 | $0.098 | 11 |
| bag1 v2 summary end | window_summary_v2 | 4430/0 | 465 | $0.101 | 11 |
| bag3 v2 summary start | window_summary_v2 | 4430/0 | 481 | $0.103 | 12 |
| bag3 v2 deep start | visual_mining_v2 | 67101/0 | 1037 | $1.084 | 38 |
| bag3 v2 summary middle | window_summary_v2 | 4430/0 | 503 | $0.104 | 13 |
| bag3 v2 summary end | window_summary_v2 | 4430/0 | 495 | $0.104 | 15 |
| bag3 v2 deep end | visual_mining_v2 | 67101/0 | 1607 | $1.127 | 45 |

| hero bag1 deep-dive | hero_deep_dive | 26k+/0 | 1.6k | $0.477 | 29 |

**Running total: $5.01** (of $30 session cap). Room remaining: ~$25.

## Hero moment deep-dive (demo material)

Target: bag 1 front-camera overexposure (highest-confidence finding).

40 frames (20 front_left + 20 front_right, 800×600), single focused prompt requesting structured forensic report. $0.48, 29s.

**Anomaly class**: `sensor_overexposure` (confidence 0.93)
**Onset → Recovery**: `t_ns=1709228361059324518` → `t_ns=1709228365523823377` (~4.5 s)
**Root cause hypothesis**: Auto-exposure convergence failure at log/bag start — cameras booted with an exposure/gain configured for a darker calibration scene; AE control loop took seconds to step down under bright overcast daylight. Startup race between AE init and frame publication. Symmetric bilateral clipping rules out direct sun or lens occlusion.
**Suggested patch**: seed AE with daylight-biased initial exposure/gain, gate frame publication until AE converges, add fast anti-windup on AE PID.
**Safety impact**: forward perception unavailable on both front cameras for ~4.5 s at scene entry — autonomy should remain in hold/creep state until AE recovery confirmed.

JSON: `data/session/analyses/hero_bag1_overexposure/hero_report.json`.

## PDFs

- `/home/hz/blackbox_cache/analyses/bag_1_v2/mining_report_v2.pdf` — 16.2 MB
- `/home/hz/blackbox_cache/analyses/bag_3_v2/mining_report_v2.pdf` — 20.2 MB
- bag 0 — skipped (see above)

Also v1 single-window reports (less interesting, kept for comparison):
- `/home/hz/blackbox_cache/analyses/bag_1/mining_report_v1.pdf` — 6.3 MB

## Top 3 priority moments for manual review

1. **Bag 1, t≈16-34 s (start window)**: Front_left and front_right cameras severely overexposed. Confidence 0.95. This could be a systematic exposure fault; worth inspecting raw images and auto-exposure logs.
2. **Bag 3, t≈1172 s (end window)**: Pedestrian near traffic cones at gated checkpoint / level crossing, captured on left cam. Confidence 0.70. High forensic value (safety-relevant interaction).
3. **Bag 3, t≈18 s (start window)**: Oncoming white SUV passing at close range. Confidence 0.70. Manual check for actual lateral margin and reaction behavior.

## Decisions logged

- **Bag copy strategy**: Do NOT full-copy bags (206 GB > free disk). Stream from HDD, cache decoded artifacts on SSD. Justification: full copy of bag 0 alone exceeds free space.
- **No telemetry topics present**: Pipeline adapted to vision-only cues. Plots phase skipped. Frame count raised (3 windows × 20 frames/cam vs 1 window × 8 frames/cam) to compensate.
- **v2 two-stage analysis**: Summary pass at 400×300 screens out uneventful windows before deep pass. Saved an estimated 33-50 % of API spend (middle-window deep calls skipped on both bags 1 and 3).

## Known issues / TODOs for manual follow-up

- **Cost accounting bug**: `uncached_input_tokens: -656` in synthetic smoke entry. Cache-read double-subtract in `claude_client.py`. Cosmetic.
- **Token caching not triggering** on v2 deep calls (cached blocks are <1024 tokens → below Anthropic cache threshold). Pad `cached_blocks` in `prompts_v2.py` to >1024 tokens if rerunning bags.
- **Bag 0 extraction hung-ish** on HDD: first attempt stuck after 3:20 with no file output, killed & retried. May need to retry again.
- **Verify bag 1 overexposure finding manually**: check raw frames in `/home/hz/blackbox_cache/frames/bag_1_v2/start__front_left_*.png`. If genuine, this is a concrete sensor-level defect worth writing a dedicated PDF report for.
- **Verify bag 3 close-pass SUV**: inspect `start__front_left_*.png` and `end__left_*.png`.
- **Curate 3 best frames for demo video**: strongest moment is the overexposure anomaly (bag 1) — clear visual story.

## Artifacts layout

```
/home/hz/blackbox_cache/
├── session_log.md                   # chronological step-by-step log
├── SESSION_SUMMARY.md               # this file
├── bag_manifest_1.json              # inspected topic list for bag 1
├── frames/
│   ├── bag_1/                       # v1: 8 frames × 5 cams central window
│   ├── bag_1_v2/                    # v2: 3 windows × 20 frames × 5 cams (big+small)
│   ├── bag_3/                       # v1 single-window
│   ├── bag_3_v2/                    # v2 3-window
│   └── bag_0_v2/                    # (if extraction completes)
└── analyses/
    ├── bag_1/                       # v1 scenario mining
    ├── bag_1_v2/                    # v2 two-stage mining
    ├── bag_3_v2/                    # v2 two-stage mining
    └── bag_0_v2/                    # (if analysis completes)
```
