# Black Box — Forensic Report

**Case:** `caba__no_prompt` &nbsp;·&nbsp; **Mode:** `run_session_v1`  
**Source:** `/mnt/ssd_boat/caba/0_dataspeed.bag`  
**Duration:** 11843.99 s  
**Generated:** 2026-04-24 16:18:22Z  
**Model:** `claude-opus-4-7` (inference-only)

> [telemetry_only] ublox_rover navheading frozen at zero for entire session

---

## Executive Summary

| # | bug class | confidence | summary |
|---|-----------|-----------:|---------|
| 1 | `sensor_timeout` **[ROOT CAUSE]** | `██████████` 0.95 | [telemetry_only] ublox_rover navheading frozen at zero for entire session |
| 2 | `sensor_timeout` | `███████░░░` 0.70 | [telemetry_only] RTCM correction stream flapping between flag states |

## Timeline

| t | label | source |
|---|-------|--------|
| `29571255:20.68` | [telemetry_only] ublox_rover navheading frozen at zero for entire session |  |
| `29571255:34.43` | [telemetry_only] RTCM correction stream flapping between flag states |  |

## Hypotheses — Detail

### 1. `sensor_timeout` — confidence 0.95

[telemetry_only] ublox_rover navheading frozen at zero for entire session

**Evidence**

- **telemetry** · `/ublox_rover/navheading` @ `29571255:20.68`
  > IMU stuck 51955 samples (11843.4s) vals=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
- **telemetry** · `/ublox_rover/navheading`
  > n=51955 span=11843.4s avg_rate=4.39Hz — publishes at nominal rate but payload is all zeros

**Patch hint:** Consumer must reject samples whose header.stamp has not advanced for N * expected_period. Add a freshness check at the fusion node boundary and raise a diagnostic_msgs/DiagnosticStatus on timeout so oncall paging fires instead of silent bad data.

### 2. `sensor_timeout` — confidence 0.70

[telemetry_only] RTCM correction stream flapping between flag states

**Evidence**

- **telemetry** · `/ublox_moving_base/rxmrtcm` @ `29571255:34.43`
  > flags 4->2->4->2->4 transitions within ~51.6s window

**Patch hint:** Review the flagged window against upstream driver logs and sensor health metrics; confirm whether the anomaly is reproducible.

## Proposed Patch

```diff
[telemetry_only] - `/imu/data`: n=1184376 span=11843.7s avg_rate=100.00Hz median_dt=9.5ms
- `/ublox_rover/navheading`: n=51955 span=11843.4s avg_rate=4.39Hz median_dt=200.1ms
    * IMU stuck 51955 samples (11843.4s) at t_ns=1774275320675642167 vals=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
- `/vehicle/imu/data_raw`: n=1184377 span=11843.6s avg_rate=100.00Hz median_dt=10.0ms
- `/vehicle/sonar_cloud`: n=59528 span=11843.5s avg_rate=5.03Hz median_dt=201.4ms
```

---
_Black Box · inference-only · Opus 4.7_
