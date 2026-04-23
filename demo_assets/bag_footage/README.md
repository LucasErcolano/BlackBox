# Real .bag camera footage

Frames extracted directly from operator-supplied ROS bags — this is the raw pixel data Black Box analyzed, not a UI screencast.

## car_1/  (2.4 MB JPG + 12 MB mp4)

Source bag: `1_cam-lidar.bag`, duration 970.2 s, topic `/cam1/image_raw/compressed` (29 109 msgs @ ~30 Hz).

Sampled by the ingestion pipeline at 30 s intervals → 32 JPGs. This is the exact same frame set the vision pipeline saw when producing `data/final_runs/car_1/analysis.json`.

| file | what |
|------|------|
| `frame_0015s.jpg` … `frame_0945s.jpg` | 32 raw JPGs, ~80 KB each, 715×600 native |
| `timelapse_cam1.mp4` | unannotated 1920×1080 letterboxed timelapse @ 2 fps (16 s total), H.264 CRF 18 |
| `timelapse_cam1_annotated.mp4` | same + top/bottom chrome + red border on the 45-135 s DWELL window flagged by the analysis |

Key frames the analysis called out:
- `frame_0015s.jpg` — near-white luma >240, AE didn't converge (2nd hypothesis)
- `frame_0045s.jpg` / `0075s` / `0105s` / `0135s` — identical framing, ~90 s dwell at gate (root-cause hypothesis)
- `frame_0165s.jpg` — motion resumes, pedestrian <1 m clearance off front-left (3rd hypothesis)

## sanfer_tunnel/  (~11 MB JPG)

Telemetry-anchored sample of `/cam1/image_raw/compressed` from `2_cam-lidar.bag` (364 GB, ROS1 Noetic, `/mnt/hdd/sanfer_sanisidro/`). Same session as the ingested `2_sensors.bag` / `2_diagnostics.bag` / `2_dataspeed.bag` trio, discovered automatically via `discover_session_assets(folder)` (`2_*` prefix grouping).

Topic has 36 235 messages across a 3626.7 s session. We pulled **54 frames** via `scripts/extract_sanfer_cam_smart.py`:

- 8 baseline frames at uniform stride across the full hour
- 46 dense frames (5 s stride) inside the 7 telemetry-flagged windows the pre-camera analysis already identified: session start (RTK break), NTRIP misframing at ~148 s, MB frequency fault at ~195 s, NTRIP socket timeout at ~1664 s, predicted tunnel ingress ~2617 s, predicted tunnel egress ~2681 s, NTRIP dropout at ~3348 s, session close

One `AnyReader` pass, ~38 min wall (27 min index build + 11 min stream).

| file | what |
|------|------|
| `frame_NNNN.Ns_(base|dense).jpg` | 54 raw JPGs, 1224×1026 native, ~200 KB each |
| `timelapse_cam1.mp4` | unannotated 1920×1080 letterboxed timelapse @ 2 fps, H.264 CRF 18 |
| `timelapse_cam1_annotated.mp4` | same + top/bottom chrome + red border + "RTK HEADING INVALID" label |

Bundle copies at `data/final_runs/sanfer_tunnel/bundle/frames/` stay native quality — Claude vision budget on Opus 4.7 can take 1224×1026 directly.

Why this matters: uniform-stride 29-frame sampling (`extract_sanfer_cam.py`, retired) produced a REFUTES hypothesis that claimed "no tunnel in any sampled frame" — technically true but narratively wrong, since the 125 s stride straddled the 60 s tunnel window. The telemetry-anchored rerun sees the tunnel (frames 2617 s → 2696 s show a real tunnel pass with num_sv 29 → 16, h_acc climbing to 1.3 m) AND still refutes the operator's causal claim: RTK was broken from t=0, the tunnel only exposed an already-broken localization stack.

## boat_lidar/  — LIDAR only

USV bag carries `/lidar_points` (PointCloud2, 4168 msgs) and a silent `/lidar_imu`. No camera. A future asset could be a Velodyne-style BEV render of the point cloud, but it is not implemented here.

## Reproduce

```bash
# Re-extract from the raw bag (requires the .bag file, not in this repo):
python -m black_box.ingestion --bag 1_cam-lidar.bag --out bundle/

# Re-build the annotated timelapse from the sampled JPGs (in-repo):
.venv/bin/python scripts/build_bag_timelapse.py
```
