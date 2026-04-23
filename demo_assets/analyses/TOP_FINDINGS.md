# Top findings — 3 cases

| case | t_ns (first evidence) | bug_class | conf | finding | evidence topic | patch summary |
|------|----------------------:|-----------|-----:|---------|----------------|---------------|
| sanfer_tunnel | 240000000 | sensor_timeout | 0.60 | Moving-baseline RTCM uplink from `/ublox_moving_base` to `/ublox_rover` is silently dead for the whole session — rover's differential-input port never receives MB carrier-phase observations, so `carr_soln` never leaves `none`. A tunnel pass IS visible in frames 2617–2696 s (num_sv 29→16, h_acc 1.3 m), but the autonomy fault pre-existed: it only became operationally visible at the tunnel. | `ublox_rover_navrelposned.csv` + dense cam1 frames 2617–2696 s | Enable RTCM3 4072.0/4072.1 + MSM7 (1077/1087/1097/1127) on MB UART2 and `CFG-UART2INPROT-RTCM3X=1` on rover UART2; add pre-drive diagnostic that blocks launch until `carr_soln ∈ {float,fixed}` for ≥10 s. |
| boat_lidar | 1756916766957187027 | other | 0.85 | `/lidar_imu` topic declared w/ QoS but msg_count=0 over 416.76s. Platform is LIDAR-only (no GPS/encoder/camera), so IMU silence removes the only inertial reference on an autonomous USV. | `/lidar_imu` (sensor_msgs/msg/Imu) | Enable IMU output in LIDAR driver config (Ouster `imu_port` / Livox `publish_imu_data: true`); add liveness watchdog aborting mission if `/lidar_imu` silent >1s. |
| car_1 | 20100000000 | state_machine_deadlock | 0.60 | Ego stationary ~130 s at parking-lot barrier/gate (frames 20 s–150 s visually identical — same cars, same pedestrian position, same booth) before finally departing onto the adjacent street. Second vision pass with dense 5 s stride across 0–180 s window confirms the dwell is continuous, not intermittent. | `frame_00020.1s..00150.0s_dense.jpg` (27 dense frames across the dwell) | Planner/controller timeout + operator alert when ego stationary > N s with no lead obstacle inside stop distance; verify closed-gate detection path. |

## Secondary findings

### sanfer_tunnel
- (0.55, missing_null_check) `ekf_se_map` has no guard on `rel_pos_heading_valid` / `carr_soln` — RTK source fails silently and EKF produces no `/odometry/filtered` at all instead of raising. Downstream consumers can't tell "no solution" from "degraded solution".
- (0.35, other) NTRIP RTCM stream misframed end-to-end: caster/mountpoint mismatch or HTTP-body bytes leaking into RTCM3 parser, producing chronic CRC-24Q failures. Fix: replace ad-hoc framer with RTKLIB `rtcm.c`, validate caster with `str2str`, switch to NTRIPv2 MSM-enabled mountpoint for the CORS region.
- (0.15, latency_spike) MB PVT driver transient back-stamping (`timestamps-in-past` + `frequency-too-low`) at 193–198 s — symptom, not cause. Raise serial-read thread priority, switch MB→ROS to USB CDC-ACM at 1 Mbaud or `/dev/ttyACMx` `low_latency`.
- (0.05, other) **REFUTES operator narrative**: tunnel at t≈2617–2696 s IS visible in dense cam1 frames and produces a real num_sv dip (29→16) + h_acc climb (1.3 m), but rover RTK was already broken from t=0. The tunnel exposed an already-broken localization stack; it did not cause the fault. *Vision-grounded using 54 telemetry-anchored cam1 frames from `2_cam-lidar.bag` (8 baseline + 46 dense inside suspicious windows).*

### boat_lidar
- (0.70, other) 10 Hz PointCloud2 without synchronized IMU → no motion compensation for wave-induced roll/pitch/yaw.
- (0.55, other) Rosbag recorder subscription raced un-launched or misnamed IMU publisher.
- *Note: session discovery (`discover_session_assets`) correctly identifies `/mnt/ssd_boat/rosbag2_2025_09_17-14_01_14/` as a single ROS2 sqlite3 bag. No camera stream present, so telemetry-anchored vision re-run is a no-op — pipeline keeps its original metadata-only analysis. Demonstrates the pipeline's graceful degradation path on platforms without cameras.*

### car_1
- (0.55, other) Forward camera severely overexposed for first ~5 s of the stream (`frame_00015.3s` near-pure white, `frame_00017.6s` partial recovery, normalized by `frame_00020.1s`) — AE didn't converge before recording started. Gate perception consumers behind an AE-converged check.
