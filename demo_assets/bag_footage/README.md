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

## sanfer_tunnel/  (6.2 MB JPG + ~14 MB mp4)

Sparse sample of `/cam1/image_raw/compressed` from `2_cam-lidar.bag` (364 GB, ROS1 Noetic, `/mnt/hdd/sanfer_sanisidro/`). Same session as the ingested `2_sensors.bag` / `2_diagnostics.bag` / `2_dataspeed.bag` trio — cameras exist, just not decoded in the original ingestion run (size/speed). Topic has 36 235 messages across a 3626.7 s session; we pulled **29 frames at uniform 125 s stride** via `scripts/extract_sanfer_cam.py` (27 min wall-time, dominated by index build).

| file | what |
|------|------|
| `frame_0000s.jpg` … `frame_3502s.jpg` | 29 raw JPGs, 1224×1026 native, ~200 KB each |
| `timelapse_cam1.mp4` | unannotated 1920×1080 letterboxed timelapse @ 2 fps (14.5 s), H.264 CRF 18 |
| `timelapse_cam1_annotated.mp4` | same + top/bottom chrome + red border + "RTK HEADING INVALID" label across all frames |

Bundle copies at `data/final_runs/sanfer_tunnel/bundle/frames/` are downsized to 800×600 q=82 (~73 KB each, 2.1 MB total) for the Claude vision budget — native quality is preserved only in `demo_assets/` for presentation.

Why the post-mortem still stands: the RTK-heading root cause (`carr=NONE` 100 % of the session, `REL_POS_VALID` never set — see `data/final_runs/sanfer_tunnel/analysis.json`) is a GNSS-fix-integrity bug diagnosable from u-blox NAV-RELPOSNED + NAV-PVT alone. Camera frames are corroborative context (tunnel transition, environment, ego motion), not dispositive evidence.

## boat_lidar/  — LIDAR only

USV bag carries `/lidar_points` (PointCloud2, 4168 msgs) and a silent `/lidar_imu`. No camera. A future asset could be a Velodyne-style BEV render of the point cloud, but it is not implemented here.

## Reproduce

```bash
# Re-extract from the raw bag (requires the .bag file, not in this repo):
python -m black_box.ingestion --bag 1_cam-lidar.bag --out bundle/

# Re-build the annotated timelapse from the sampled JPGs (in-repo):
.venv/bin/python scripts/build_bag_timelapse.py
```
