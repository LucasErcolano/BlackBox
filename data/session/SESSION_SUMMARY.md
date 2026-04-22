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
| 0_cam-lidar.bag | 206 GB | 3545 s | ✓ extracted + analyzed (3rd attempt succeeded — see notes) |

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

### Bag 0 — end window (~3510-3530 s)
- **0.90** Rear camera: indoor workshop/lab scene (speakers, whiteboards, desks, electronic equipment, fluorescent lights).
- **0.90** Left camera: indoor kitchen/doorway (red chair, cabinets, brooms, power outlet, open doorway to outside).
- **MANUAL VERIFICATION (2026-04-22)**: both confirmed real. Right cam (not originally flagged) also shows indoor lobby with mirror-reversed "CIA ARTIFICIAL Y ROBOTICA" lettering on glass doors — consistent with camera *inside* a robotics lab building. Front_left at same timestamp shows outdoor parking. Interpretation: vehicle parked at lab building entrance; rear/left/right cameras have line-of-sight through open doors into multiple interior rooms. This is NOT a topic-mux/feed-swap artifact — it is the end-of-recording park scenario captured by a fixed multi-camera rig in a robotics research setting.
- **Actionable**: trim bag 0 tail for driving-scene training data (roughly last ~90-120 s); the non-driving lab footage will poison anything trained on it as "road scenes".
- **0.78** Pedestrian group passes close to right side of ego vehicle.
- **0.60** Extended near-stationary / stall behavior (<1 m/s) — consistent with park-at-building end state.

### Bag 0 — start + middle windows — uneventful, filtered out by summary pass.

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

| hero bag1 deep-dive | hero_deep_dive | 27206/0 | 921 | $0.477 | 29 |
| bag0 v2 summary start | window_summary_v2 | 4430/0 | 491 | $0.103 | 11 |
| bag0 v2 summary middle | window_summary_v2 | 4430/0 | 485 | $0.103 | 11 |
| bag0 v2 summary end | window_summary_v2 | 4430/0 | 508 | $0.105 | 12 |
| bag0 v2 deep end | visual_mining_v2 | 67101/0 | 2112 | $1.165 | 51 |

**Running total: $6.48** (of $30 session cap). Room remaining: ~$23.50.

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
- `/home/hz/blackbox_cache/analyses/bag_0_v2/mining_report_v2.pdf` — 19.1 MB

Also v1 single-window reports (less interesting, kept for comparison):
- `/home/hz/blackbox_cache/analyses/bag_1/mining_report_v1.pdf` — 6.3 MB

## Top priority moments for manual review (ranked)

1. **Bag 1, t≈16-34 s (start window)**: Front_left and front_right cameras severely overexposed. Confidence 0.95 (plus hero deep-dive confirmed at 0.93). Systematic exposure fault; hero report diagnoses AE convergence failure with 4.5 s recovery window.
2. **Bag 0, t≈3510-3530 s (end window) — scene-integrity flag (verified)**: Vehicle parked at robotics lab entrance; rear/left/right cameras see into indoor workshop, kitchen, and lobby through open doors. Not a data-mux artifact but a dataset-quality issue: the tail of bag 0 is non-driving footage and should be trimmed before use as training data for road-scene perception.
3. **Bag 0 scene-integrity (continued)**: Detecting this as an anomaly is itself a useful demo — a forensic copilot that flags "this window does not look like driving" without any telemetry, purely from cross-camera cues, is exactly the value prop.
4. **Bag 0, t≈3505 s (end window)**: Pedestrian group passes close to right side of ego vehicle. Confidence 0.78.
5. **Bag 3, t≈1172 s (end window)**: Pedestrian near traffic cones at gated checkpoint / level crossing, captured on left cam. Confidence 0.70.
6. **Bag 3, t≈18 s (start window)**: Oncoming white SUV passing at close range. Confidence 0.70.

## Decisions logged

- **Bag copy strategy**: Do NOT full-copy bags (206 GB > free disk). Stream from HDD, cache decoded artifacts on SSD. Justification: full copy of bag 0 alone exceeds free space.
- **No telemetry topics present**: Pipeline adapted to vision-only cues. Plots phase skipped. Frame count raised (3 windows × 20 frames/cam vs 1 window × 8 frames/cam) to compensate.
- **v2 two-stage analysis**: Summary pass at 400×300 screens out uneventful windows before deep pass. Saved an estimated 33-50 % of API spend (middle-window deep calls skipped on both bags 1 and 3).

## Bag 0 extraction resolution

Two initial attempts stalled in AnyReader open phase (both killed after 3-4 min with 0 frames). Third attempt succeeded — index scan took 11 min (~15 GB read at 22 MB/s) on first open, then frame extraction ran in ~2 min. Conclusion: rosbags ROS1 Reader needs a long index-building scan on bag 0 (possibly missing footer index, or chunk index located far from EOF), but once the open completes, seek-and-read works normally. Subsequent re-opens of the same bag in the same session can reuse the built index (in-memory) — if a workflow needs multiple passes on bag 0, keep the Reader open across passes rather than reopening per pass.

Bag 0 total pipeline: 449 s extraction + 87 s analysis + $1.48 API. 4 moments including 2 high-confidence data-integrity anomalies.

## Known issues / TODOs for manual follow-up

- **Cost accounting bug**: `uncached_input_tokens: -656` in synthetic smoke entry. Cache-read double-subtract in `claude_client.py`. Cosmetic.
- **Token caching not triggering** on v2 deep calls (cached blocks are <1024 tokens → below Anthropic cache threshold). Pad `cached_blocks` in `prompts_v2.py` to >1024 tokens if rerunning bags.
- ~~Verify bag 1 overexposure finding manually~~ DONE: `start__front_left_00` JPEG is 5 KB (compressed-flat → near-pure white saturated pixels), `start__front_left_02` is 209 KB (normal scene recovered). Overexposure is real, 4.5 s duration matches hero report.
- ~~Investigate bag 0 data-integrity anomaly~~ DONE: manually verified 2026-04-22. Finding is real but reinterpreted — vehicle parked at robotics lab; cameras see indoor spaces through doors. Not a mux artifact. Recommend trimming bag 0 tail (~last 120 s) when using as road-scene training data.
- **Verify bag 3 close-pass SUV**: inspect `start__front_left_*.png` and `end__left_*.png`.
- **Curate 3 best frames for demo video**: strongest moment is the overexposure anomaly (bag 1); runner-up is the bag 0 indoor-scene data-integrity flag (very visual, very demo-worthy).
- **Bag 0 rosbag reindex**: if future workflows need to re-open bag 0 cold repeatedly, run ROS1 `rosbag reindex` once (needs ROS install on another machine) to add/fix the EOF index and make subsequent opens instantaneous.

## Hypothesis revision log

One case this session where a follow-up analysis **disagreed with the original reading and was wrong**. Kept as demo material for the human-in-the-loop story.

### Case 1 — Bag 0 end window, indoor-scene anomaly

| Stage | Diagnosis | Confidence | Verdict |
|-------|-----------|-----------|---------|
| Scenario mining (v2, 800×600) | Indoor scenes on rear/left; possible mux artifact, needs audit | 0.90 | Flagged |
| Manual check (2026-04-22, operator) | Vehicle parked at lab entrance; cameras see interior through open doors. Dataset-quality issue, not software bug. | — | **Correct reading** |
| Hero deep-dive (hi-res 3.75 MP, 18 frames, `hero_bag0_indoor_scene/`) | `topic_misrouting` — rear/left topics bound to bench cameras | 0.95 | **Rejected by operator** |
| Operator re-verification (2026-04-22) | Hero reasoning used three faulty domain assumptions (see `verification_note.md`): mistook permanent sensor mount for tripod rig, mistook parked-vehicle static frames for bench-cam evidence, mistook end-of-loop return for within-drive stream switch. | — | Original reading stands |

**Final**: trim last ~120 s of bag 0 before road-scene training. No topic misrouting. No software bug. See `data/session/analyses/hero_bag0_indoor_scene/verification_note.md`.

**Lesson for the tool**: hi-res re-analysis with a confident prompt can over-commit to an integrity-failure hypothesis. Pre-loading the "prior flag" in the prompt biased the model toward confirmation. More pixels ≠ more ground truth. Human verification is a required layer of the pipeline, not optional polish.

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
│   └── bag_0_v2/                    # 3-window vision extraction (450 s wall)
└── analyses/
    ├── bag_1/                       # v1 scenario mining
    ├── bag_1_v2/                    # v2 two-stage mining
    ├── bag_3_v2/                    # v2 two-stage mining
    ├── bag_0_v2/                    # 3-window mining (2 data-integrity anomalies)
    └── hero_bag1_overexposure/      # AE convergence failure deep-dive
```
