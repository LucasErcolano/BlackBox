# sensor_drop_cameras_01

**Bug class:** `sensor_timeout`
**Platform:** Autonomous car (ROS1)
**Status:** **skeleton — awaiting real bag from collaborator**

## Story

Mid-drive, a sensor subsystem died. The failure propagated so that all camera topics stopped publishing simultaneously, while other topics (IMU, GPS, odometry) continued. This is the cleanest real-world case of the taxonomy bug `sensor_timeout` we have access to.

## Expected ground-truth contents (fill in when bag lands)

- `window_s`: approximate start and end of the silence window, in bag-time seconds from start.
- `dropped_topics`: list of camera topic names that went silent.
- `surviving_topics`: topics that kept publishing through the drop — critical for ruling out whole-stack crash.
- `patch_target.file`: likely path to the consumer that should watchdog the camera topics.
- `patch_target.function`: consumer callback or tick function to patch.

## Run plan once bag arrives

1. `python -m black_box.ingestion.cli inspect path/to/bag.bag` — enumerate topics, durations, message counts.
2. `python scripts/analyze_drop.py --bag path/to/bag.bag` (to be written) — builds activity matrix via `telemetry_drop.bucketize`, sends via `telemetry_drop_prompt`, writes `prediction.json` here.
3. `python scripts/score.py --case cases/sensor_drop_cameras_01 --prediction prediction.json`.

## Evidence hints (speculative, verify against real bag)

- Multiple camera topics simultaneously go from N messages/bucket to 0.
- Non-camera topics keep publishing through the silence window.
- Rate decay pattern indicates bus/driver fault rather than node crash (single-node fault would only kill its own topics).

## Patch hint (speculative)

Add a camera-freshness watchdog in the perception consumer: if any camera topic has no message within `CAMERA_WATCHDOG_S`, log error and trigger a safety-stop. Do not architecturally rewrite the driver pipeline.

## Scoring notes

Once the bag is in, decide if this is scored with the standard 2.0 rubric (root-cause + IoU + patch target) or needs an extension for multi-topic drop events. The `telemetry_drop_v1` prompt emits a list of events rather than a single bug; the scorer may need a mode that picks the highest-confidence event for scoring.
