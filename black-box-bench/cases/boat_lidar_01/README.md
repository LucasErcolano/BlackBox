# boat_lidar_01

**Bug class:** TBD (pending bag inspection)
**Platform:** USV / unmanned surface vessel (ROS2, .db3 or .mcap)
**Status:** **skeleton — awaiting real bag from collaborator**

## Story

A ROS2 bag from an unmanned surface vessel, including LIDAR scans over water. The collaborator has not yet specified the failure mode; this case may turn out to be a scenario-mining case (Tier 2: find moments of interest in a clean bag) rather than a forensic one. Determine after first inspection.

## Expected ground-truth contents (fill in after first review)

- `bug_class`: one of the closed taxonomy, or `scenario_mining` if no injected bug.
- `window_s`: period of interest.
- `evidence_hints`: LIDAR features a human reviewer would flag (docking approach too tight, floating obstacle, LIDAR driver dropout, etc.).
- `patch_target`: only if a real bug is found.

## Run plan once bag arrives

1. Inspect topics: confirm PointCloud2 or LaserScan topics + their rates.
2. Decide the mode:
   - If a real incident is known → Tier 1 forensic + `telemetry_drop_v1` (for driver faults) or `boat_lidar_mining_v1` (for environment-side findings).
   - If it's a clean operational bag → Tier 2 scenario-mining with `boat_lidar_mining_v1`. Expected output: a short list of moments (docking maneuvers, near-shore passes, debris sightings, etc.) or an empty list with rationale.
3. Ingestion: use `black_box.ingestion.load_bag(path, lidar_topics=[...])` to pull scans, then `top_down_render` for each scan into an 800×800 PNG. Sample scans at ~1 Hz initially; densify on flagged windows.
4. Prompt: `boat_lidar_mining_prompt()` from `src/black_box/analysis/prompts_boat.py`.

## Ingestion notes

- `rosbags` library handles ROS2 `.db3` and `.mcap` directly. No ROS runtime required.
- `decode_pointcloud2` downsamples to 50 k points by default. Raise cap if the bag's clouds are much smaller and the reduction is hiding structure.
- For 2D LaserScan, `decode_laserscan` produces a planar scan at z=0; `top_down_render` handles it identically to 3D.

## Open questions for collaborator

- Is there a known incident, or is this an operational bag?
- Approximate duration of the bag?
- Topic names for LIDAR and (if present) forward camera / GPS / IMU?
- Any chart / context we should use to judge what "near shore" or "safe margin" means for this vessel?

## Fixtures

Ported 2026-04-23 from the deprecated `bench/fixtures/boat_lidar/` during the P5-E benchmark-directory consolidation:

- `fixtures/stream_events.jsonl` — recorded Opus 4.7 stream events for a 416.76 s USV clip (`bag_duration_s` from the original `bench/cases.yaml` entry).
- `fixtures/analysis.json` — curated `PostMortemReport` flagging `/lidar_imu` with `msg_count=0` over the full session (LIDAR-only platform; IMU silence removes the only inertial reference on open water). `bug_class: other`.

Reference artifacts for offline plumbing checks, not the scorable ground truth — the authoritative bag is still pending.
