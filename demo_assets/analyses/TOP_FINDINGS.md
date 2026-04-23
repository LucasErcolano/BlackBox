# Top findings — 3 cases

| case | t_ns (first evidence) | bug_class | conf | finding | evidence topic | patch summary |
|------|----------------------:|-----------|-----:|---------|----------------|---------------|
| sanfer_tunnel | 240000000 | sensor_timeout | 0.90 | Dual-antenna moving-base RTK never produces carrier-phase solution — rover never ingests MB observation stream (UBX-RXM-RAWX/SFRBX or RTCM3 4072.0/4072.1 + 1077/1087/1097/1127). Permanent wait-for-base state, session-wide, 43 min pre-tunnel. | ublox_rover_navrelposned.csv (carr_soln=none 18133/18133 samples) | Configure MB UART2 out_protocol=ubx+rtcm3 w/ RAWX+SFRBX+4072.x+107x@460800; rover UART2 in_protocol=ubx+rtcm3; disable tmode3 on both. |
| boat_lidar | 1756916766957187027 | other | 0.85 | `/lidar_imu` topic declared w/ QoS but msg_count=0 over 416.76s. Platform is LIDAR-only (no GPS/encoder/camera), so IMU silence removes the only inertial reference on an autonomous USV. | `/lidar_imu` (sensor_msgs/msg/Imu) | Enable IMU output in LIDAR driver config (Ouster `imu_port`/Livox `publish_imu_data: true`); add liveness watchdog aborting mission if `/lidar_imu` silent >1s. |
| car_1 | 45000000000 | other | 0.75 | Ego stationary ~90s at parking-lot egress w/ pedestrian+hand-cart in lane under raised barrier; no escalation or progress. | frame_0045s..0135s (identical framing across four 30s-spaced samples) | Progress watchdog in behavior planner: v<0.1 m/s w/ dynamic obstacle for >15s → courtesy; >45s → remote assist; >90s → min-risk pull-over. |

## Secondary findings

### sanfer_tunnel
- (0.75, state_machine_deadlock) DBW never engaged — `brake.enabled`/`throttle.enabled` = 0 for all 181k/362k samples. Operator narrative mislabeled (manual recon drive, not autonomous).
- (0.60, missing_null_check) Dataspeed NMEA parser emits `/vehicle/gps/fix` w/ latitude frozen at ~-3e-7 for all 3591 msgs — silent DDMM decode / hemisphere bug.
- (0.20, latency_spike) Two NTRIP starvation events (20s @ t=1664, 4s+ @ t=3347) — postdate RTK failure, not root cause.
- (0.10, other) **REFUTES operator hypothesis**: tunnel caused mild GNSS degradation (num_sv 29→16, h_acc 645→1294mm) but did NOT break RTK — session-wide carr_soln=none starts 43 min pre-tunnel.

### boat_lidar
- (0.70, other) 10 Hz PointCloud2 without synchronized IMU → no motion compensation for wave-induced roll/pitch/yaw.
- (0.55, other) Rosbag recorder subscription raced un-launched or misnamed IMU publisher.

### car_1
- (0.50, other) Forward camera globally saturated for first ~15-30s (AE/gain didn't converge) — luma>240 in frame_0015s.
- (0.35, other) On motion resume ego passes pedestrian at <1m lateral clearance off front-left.
