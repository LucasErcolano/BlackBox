# Black Box — Forensic Report

**Case:** `boat_lidar` &nbsp;·&nbsp; **Mode:** `scenario_mining`  
**Duration:** 416.76 s  
**Generated:** 2026-04-23 16:32:05Z  
**Model:** `claude-opus-4-7` (inference-only)

> The LIDAR companion IMU stream was declared with a QoS profile but published zero messages for the entire 7-minute USV session, indicating the IMU publisher never came online (driver disabled, hardware disconnect, or misconfigured port).

---

## Executive Summary

| # | bug class | confidence | summary |
|---|-----------|-----------:|---------|
| 1 | `other` **[ROOT CAUSE]** | `████████░░` 0.85 | The LIDAR companion IMU stream was declared with a QoS profile but published zero messages for the entire 7-minute USV session, indicating the IMU publisher never came online (driver disabled, hardware disconnect, or misconfigured port). |
| 2 | `other` | `██████░░░░` 0.55 | The rosbag recorder was configured to capture /lidar_imu but the driver's parameter set (or a remap) disabled IMU publication, producing a topic registration with no traffic. |
| 3 | `other` | `███████░░░` 0.70 | With IMU silent and no GPS/odometry/camera, any downstream scan deskewing, ego-motion estimation, or LIDAR-inertial odometry was operating open-loop on pure point clouds, a dangerous configuration for an autonomous USV on open water. |

## Timeline

| t | label | source |
|---|-------|--------|
| `29281946:06.96` | Recording starts; /lidar_imu topic declared but silent from t=0 |  |
| `29281946:06.96` | /lidar_points begins streaming at ~10 Hz (nominal) |  |
| `29281953:03.72` | Recording ends after 416.76 s; /lidar_imu msg_count still 0 |  |

## Hypotheses — Detail

### 1. `other` — confidence 0.85

The LIDAR companion IMU stream was declared with a QoS profile but published zero messages for the entire 7-minute USV session, indicating the IMU publisher never came online (driver disabled, hardware disconnect, or misconfigured port).

**Evidence**

- **telemetry** · `/lidar_imu`
  > topic /lidar_imu (sensor_msgs/msg/Imu) message_count=0 over 416.76 s; QoS profile advertised identically to /lidar_points, so the recorder subscribed but no publisher ever emitted.
- **telemetry** · `summary.json`
  > 'IMU topic declared but NEVER published during session' — platform is LIDAR-only with no GPS/encoder/camera fallback, so IMU silence removes the only inertial reference.
- **telemetry** · `/lidar_points`
  > 4168 PointCloud2 messages / 416.76 s = 10.00 Hz — LIDAR itself is healthy, which isolates the fault to the IMU branch rather than the sensor pod as a whole.

**Patch hint:** Enable IMU output in the LIDAR driver config (e.g., Ouster `imu_port`/`imu_topic`, Livox `publish_imu_data: true`) and add a liveness watchdog that aborts the mission if /lidar_imu goes silent > 1 s.

### 2. `other` — confidence 0.55

The rosbag recorder was configured to capture /lidar_imu but the driver's parameter set (or a remap) disabled IMU publication, producing a topic registration with no traffic.

**Evidence**

- **telemetry** · `metadata.yaml`
  > /lidar_imu advertises the same reliability/durability QoS as /lidar_points yet carries 0 messages — consistent with a recorder subscription racing an un-launched or misnamed IMU publisher.
- **telemetry** · `/rosout`
  > Only 9 /rosout messages in ~7 min — too sparse to contain run-time warnings; a missing IMU node would typically log, but logging may have been suppressed or the node never started.

**Patch hint:** Audit launch file: verify the IMU-publishing node is actually started and that topic remaps resolve to /lidar_imu; add startup assertion on expected publisher count.

### 3. `other` — confidence 0.70

With IMU silent and no GPS/odometry/camera, any downstream scan deskewing, ego-motion estimation, or LIDAR-inertial odometry was operating open-loop on pure point clouds, a dangerous configuration for an autonomous USV on open water.

**Evidence**

- **telemetry** · `summary.json`
  > 'No GPS, no encoders, no camera' combined with zero IMU messages means the vessel had no inertial or absolute pose source for the whole session.
- **telemetry** · `/lidar_points`
  > 10 Hz PointCloud2 without synchronized IMU cannot be motion-compensated against wave-induced roll/pitch/yaw, biasing any obstacle localization.

**Patch hint:** Gate autonomy on IMU liveness; if /lidar_imu stays silent at mission start, refuse to arm or drop to safe-hold.

## Proposed Patch

```diff
Root cause: /lidar_imu publisher never ran during the 416.76 s session (msg_count=0) while /lidar_points was nominal at 10 Hz. Fix: (1) enable IMU publication in the LIDAR driver configuration and confirm the node is launched, (2) add a pre-arm check that verifies non-zero publication rate on every declared critical sensor topic, (3) add a runtime watchdog that faults autonomy if /lidar_imu Hz drops below threshold, and (4) refuse open-water autonomy on a LIDAR-only platform without at least one live inertial or absolute-pose source.
```

---
_Black Box · inference-only · Opus 4.7_
