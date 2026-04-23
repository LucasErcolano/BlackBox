# Top findings — 3 cases

| case | t_ns (first evidence) | bug_class | conf | finding | evidence topic | patch summary |
|------|----------------------:|-----------|-----:|---------|----------------|---------------|
| sanfer_tunnel | 240000000 | calibration_drift | 0.78 | Dual-antenna moving-baseline RTK is mis-configured: `carr_soln` never leaves `none` and `rel_pos_heading_valid` is 0 for every one of 18 133 NAV-RELPOSNED messages — RTK heading unavailable from t=0, a session-wide baseline/configuration defect, not a tunnel event. | `ublox_rover_navrelposned.csv` | Provision TMODE3 + moving-baseline on both F9Ps, force MSM7/1230 RTCM output, and gate autonomy engage on RTK-heading-valid before run is considered autonomy-ready. |
| boat_lidar | 1756916766957187027 | other | 0.85 | `/lidar_imu` topic declared w/ QoS but msg_count=0 over 416.76s. Platform is LIDAR-only (no GPS/encoder/camera), so IMU silence removes the only inertial reference on an autonomous USV. | `/lidar_imu` (sensor_msgs/msg/Imu) | Enable IMU output in LIDAR driver config (Ouster `imu_port` / Livox `publish_imu_data: true`); add liveness watchdog aborting mission if `/lidar_imu` silent >1s. |
| car_1 | 45000000000 | other | 0.75 | Ego stationary ~90s at parking-lot egress w/ pedestrian+hand-cart in lane under raised barrier; no escalation or progress. | `frame_0045s..0135s` (identical framing across four 30s-spaced samples) | Progress watchdog in behavior planner: v<0.1 m/s w/ dynamic obstacle for >15s → courtesy; >45s → remote assist; >90s → min-risk pull-over. |

## Secondary findings

### sanfer_tunnel
- (0.62, sensor_timeout) NTRIP correction stream chronically unhealthy: ~100 RTCM checksum mismatches, 20 s server-restart @ t≈1664 s, 4 s dropout @ t≈3348 s. `diff_soln=1` only 15.0 % of session.
- (0.55, missing_null_check) `/vehicle/gps/fix` publishes frozen latitude (~−3e-7°) for all 3591 msgs while lon/alt vary — Dataspeed NMEA bridge stuck/zero-init bug, downstream consumers no validation.
- (0.35, state_machine_deadlock) DBW never engaged — `brake.enabled`/`throttle.enabled` = 0 for all 36 208/36 210 samples. Operator's "behavior degradation" cannot be attributed to autonomous behavior at all; DBW handshake / EKF-availability gate blocked engage.
- (0.08, other) **REFUTES operator hypothesis**: no tunnel appears in any of the 29 sampled camera frames, `num_sv` ≥19 for full hour, every RTK/localization fault observed from t<1 s — not a localized tunnel-entry event. *Vision-grounded refutation using `/cam1/image_raw/compressed` frames extracted from `2_cam-lidar.bag`.*

### boat_lidar
- (0.70, other) 10 Hz PointCloud2 without synchronized IMU → no motion compensation for wave-induced roll/pitch/yaw.
- (0.55, other) Rosbag recorder subscription raced un-launched or misnamed IMU publisher.

### car_1
- (0.50, other) Forward camera globally saturated for first ~15-30s (AE/gain didn't converge) — luma>240 in `frame_0015s`.
- (0.35, other) On motion resume ego passes pedestrian at <1m lateral clearance off front-left.
