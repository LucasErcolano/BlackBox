# Black Box — Forensic Report

**Case:** `sanfer_tunnel` &nbsp;·&nbsp; **Mode:** `post_mortem`  
**Duration:** 3626.70 s  
**Generated:** 2026-04-23 16:32:05Z  
**Model:** `claude-opus-4-7` (inference-only)

> Moving-baseline RTCM uplink from /ublox_moving_base to /ublox_rover is silently dead for the whole session — rover's differential-input port never receives MB carrier-phase observations, so carr_soln never leaves 'none'

---

## Executive Summary

| # | bug class | confidence | summary |
|---|-----------|-----------:|---------|
| 1 | `sensor_timeout` **[ROOT CAUSE]** | `██████░░░░` 0.60 | Moving-baseline RTCM uplink from /ublox_moving_base to /ublox_rover is silently dead for the whole session — rover's differential-input port never receives MB carrier-phase observations, so carr_soln never leaves 'none' |
| 2 | `missing_null_check` | `██████░░░░` 0.55 | ekf_se_map has no guard on rel_pos_heading_valid / carr_soln, so when the RTK source fails silently it produces no /odometry/filtered at all instead of raising a loud error |
| 3 | `other` | `████░░░░░░` 0.35 | NTRIP RTCM stream is misframed end-to-end — caster/mountpoint mismatch or HTTP-body bytes leaking into the RTCM3 parser, producing chronic CRC-24Q failures |
| 4 | `latency_spike` | `██░░░░░░░░` 0.15 | Moving-base PVT driver exhibits transient back-stamping (timestamps-in-past + frequency-too-low) at 193–198 s; a symptom rather than the root cause |
| 5 | `other` | `░░░░░░░░░░` 0.05 | REFUTED — operator narrative that a GPS anomaly at tunnel entry caused behavior degradation |

## Timeline

| t | label | source |
|---|-------|--------|
| `   0.24 s` | First NAV-RELPOSNED arrives with carr_soln=none, rel_pos_valid=0, rel_pos_heading_valid=0 — the state it will hold for the entire 3626 s session |  |
| `   0.40 s` | ekf_se_map diagnostic ERROR: /odometry/filtered 'No events recorded' — fused localizer never emits a single message |  |
| `   0.49 s` | ntrip_client logs its first RTCM CRC-24Q mismatch (before the vehicle has even moved) |  |
| `   0.52 s` | diagnostics WARN: ublox_rover + ublox_moving_base both report 'TMODE3: Not configured' at boot → receivers came up without an RTK-role preset |  |
| `   4.12 s` | moving_base fix topic: 'Frequency too high; Timestamps too far in past seen' (level 2) — MB driver already back-stamping |  |
| `  17.54 s` | Vehicle first exceeds 0.5 m/s — but DBW throttle/brake enabled=0, and remains 0 for every 20 Hz sample thereafter (manual drive throughout) |  |
| `03:13.31` | MB PVT deteriorates: Timestamps-in-past → Frequency-too-low sequence 193.31–197.73 s. Coincides with dense-frame cluster 133–210 s | cross-view |
| `27:44.17` | ntrip_client: 'Unable to send NMEA sentence to server. Exception: timed out' — first hard socket failure |  |
| `28:04.20` | ntrip_client auto-restart after 5 NMEA send failures; 30 ms later 'RTCM requested before client was connected' — rover has zero corrections during the reconnect window |  |
| `34:29.83` | Rover h_acc spikes to 1.30 m (session floor ≈0.48 m), num_sv≈26 — first multipath/occlusion episode; carr_soln STILL 'none' | cross-view |
| `43:44.83` | Second h_acc spike to 1.29 m, num_sv drops to 16–22, inside dense-frame window 2606–2696 s (visually the tunnel/overpass transit). carr_soln STILL 'none' | cross-view |
| `55:47.73` | ntrip_client ERROR (level 8): 'RTCM data not received for 4 seconds, reconnecting' — inside dense-frame window 3332–3362 s | cross-view |
| `60:26.63` | Session ends. carr_soln='none' for 18133/18133 NAV-RELPOSNED messages; rel_pos_heading_valid=0 always; /odometry/filtered never published; DBW never enabled. Operator's 'tunnel entry' framing is not supported by the data |  |

## Hypotheses — Detail

### 1. `sensor_timeout` — confidence 0.60

Moving-baseline RTCM uplink from /ublox_moving_base to /ublox_rover is silently dead for the whole session — rover's differential-input port never receives MB carrier-phase observations, so carr_soln never leaves 'none'

**Evidence**

- **telemetry** · `ublox_rover_navrelposned.csv` @ `   0.24 s`
  > carr_soln value_counts={'none':18133}; rel_pos_valid={0:18133}; rel_pos_heading_valid={0:18133} over 3626.4 s
- **telemetry** · `ublox_rover_navpvt.csv`
  > fix_type=3 everywhere, num_sv 27–31, h_acc floor ≈480 mm — open-sky conditions prevailed, so failure to reach float/fixed is not a satellite-geometry issue
- **telemetry** · `ublox_moving_base_navpvt.csv`
  > 16639/16639 msgs with fix_type=3, num_sv mean 27.7 — MB receiver is healthy; only its RTCM-output side is silent
- **telemetry** · `diagnostics_nonzero_unique.csv` @ `   0.52 s`
  > 'ublox_rover: TMODE3, Not configured' + 'ublox_moving_base: TMODE3, Not configured' at 0.52 s — receivers booted without RTK-role preset

**Patch hint:** Enable RTCM3 4072.0/4072.1 + MSM7 (1077/1087/1097/1127) on MB UART2 and CFG-UART2INPROT-RTCM3X=1 on rover UART2; add pre-drive diagnostic that blocks launch until carr_soln∈{float,fixed} for ≥10 s

### 2. `missing_null_check` — confidence 0.55

ekf_se_map has no guard on rel_pos_heading_valid / carr_soln, so when the RTK source fails silently it produces no /odometry/filtered at all instead of raising a loud error

**Evidence**

- **telemetry** · `diagnostics_nonzero_unique.csv` @ `   0.40 s`
  > 'ekf_se_map: odometry/filtered topic status, No events recorded.' level=2 (ERROR) — filter never published in 1 h
- **telemetry** · `throttle_20hz.csv`
  > enabled=0 for all 36208 rows; brake_20hz.csv enabled=0 for all 36210 rows — DBW refused to engage the whole session, which is the only reason this silent failure did not become a crash
- **timeline** · `timeline` @ `   0.24 s`
  > RTK was invalid from t=0.243 s yet no higher-level alarm fired; the only tells were the rosout checksum warnings and a single ekf diagnostic

**Patch hint:** In ekf_se_map, reject RELPOSNED unless rel_pos_heading_valid==1 AND carr_soln>=FLOAT; publish diagnostic ERROR with latched stamp when gate fails instead of silently suppressing output

### 3. `other` — confidence 0.35

NTRIP RTCM stream is misframed end-to-end — caster/mountpoint mismatch or HTTP-body bytes leaking into the RTCM3 parser, producing chronic CRC-24Q failures

**Evidence**

- **telemetry** · `rosout_warnings.csv` @ `   0.49 s`
  > First 'Actual Checksum: 0x5A525C' at 0.49 s, followed by ~140 Expected/Actual mismatch pairs spanning 0.49–3586 s
- **telemetry** · `rosout_warnings.csv` @ `02:28.33`
  > 'Found packet, but checksums didn't match' — RTCM3 CRC-24Q failure is the parser's own framer
- **timeline** · `timeline` @ `   0.49 s`
  > Mismatches start BEFORE the vehicle moves (17.5 s) and continue through open-sky segments, so they are not tunnel/packet-loss driven

**Patch hint:** Replace ad-hoc RTCM framer with RTKLIB rtcm.c; validate caster with str2str (bytes must start 0xD3 and pass CRC-24Q); switch to an NTRIPv2 MSM-enabled mountpoint for the -34.445,-58.531 CORS region

### 4. `latency_spike` — confidence 0.15

Moving-base PVT driver exhibits transient back-stamping (timestamps-in-past + frequency-too-low) at 193–198 s; a symptom rather than the root cause

**Evidence**

- **telemetry** · `diagnostics_nonzero_unique.csv` @ `03:13.31`
  > 193.31→195.39→197.73 s chain: Timestamps too far in past → Frequency too low
- **telemetry** · `diagnostics_nonzero_unique.csv` @ `   4.12 s`
  > Same MB topic earlier: 'Frequency too high; Timestamps too far in past' at 4.12 s

**Patch hint:** Raise ublox driver serial read thread priority; switch MB→ROS transport to USB CDC-ACM at 1 Mbaud or use /dev/ttyACMx with low_latency

### 5. `other` — confidence 0.05

REFUTED — operator narrative that a GPS anomaly at tunnel entry caused behavior degradation

**Evidence**

- **telemetry** · `ublox_rover_navrelposned.csv` @ `   0.24 s`
  > carr_soln='none' and rel_pos_heading_valid=0 from t=0.243 s — pre-drive, open-sky, long before any tunnel
- **camera** · `frames/frame_02606.5s_dense.jpg..frame_02696.2s_dense.jpg` @ `43:44.83`
  > Dense camera coverage 2606–2696 s coincides with h_acc bump to 1.3 m but carr_soln was already 'none' for the preceding 43 minutes — tunnel could not have 'caused' a state that already existed
- **telemetry** · `throttle_20hz.csv`
  > DBW enabled=0 for the entire session → there was no autonomous 'behavior' to degrade; the operator drove the whole route manually
- **telemetry** · `rosout_warnings.csv` @ `   0.49 s`
  > ntrip_client RTCM checksum failures begin at 0.49 s, 17 s before the vehicle first moves

**Patch hint:** Revise incident framing: failure is session-wide RTK pipeline, not a tunnel-entry event; tunnel only exposed an already-broken localization stack

## Proposed Patch

```diff
--- a/config/ublox_rover.yaml
+++ b/config/ublox_rover.yaml
@@ ublox_rover:
   ros__parameters:
     device: /dev/ttyACM0
     frame_id: gps_rover
-    uart1: { baudrate: 38400, in: UBX,         out: UBX }
-    uart2: { baudrate: 38400, in: none,        out: none }
+    uart1: { baudrate: 460800, in: UBX+RTCM3v3, out: UBX }
+    uart2: { baudrate: 460800, in: RTCM3v3,     out: none }  # MB→rover moving-baseline uplink
     cfg_msg:
+      - { class: 0x01, id: 0x3C, rate: 5 }   # NAV-RELPOSNED @5 Hz
+    dynamic_model: automotive                # CFG-NAVSPG-DYNMODEL=4
+    pre_drive_gate:
+      require_carr_soln: float               # none → block launch
+      require_rel_pos_heading_valid: true
+      timeout_s: 30
--- a/config/ublox_moving_base.yaml
+++ b/config/ublox_moving_base.yaml
@@ ublox_moving_base:
   ros__parameters:
     device: /dev/ttyACM1
     frame_id: gps_mb
-    uart2: { baudrate: 38400, in: none, out: none }
+    uart2: { baudrate: 460800, in: none, out: RTCM3v3 }   # wired to rover UART2
+    cfg_msg:
+      # moving-base must emit 4072.0/4072.1 + MSM7 on UART2 at 1 Hz
+      - { id: RTCM3_4072_0, rate_uart2: 1 }
+      - { id: RTCM3_4072_1, rate_uart2: 1 }
+      - { id: RTCM3_1077,   rate_uart2: 1 }
+      - { id: RTCM3_1087,   rate_uart2: 1 }
+      - { id: RTCM3_1097,   rate_uart2: 1 }
+      - { id: RTCM3_1127,   rate_uart2: 1 }
--- a/ekf_se_map/src/ekf_localization_node.cpp
+++ b/ekf_se_map/src/ekf_localization_node.cpp
@@ void Ekf::onRelPosNed(const ublox_msgs::msg::NavRELPOSNED9 & msg)
-  heading_rad_        = msg.rel_pos_heading * 1e-5 * M_PI / 180.0;
-  last_heading_stamp_ = now();
+  const bool rtk_ok = msg.rel_pos_heading_valid
+                      && msg.carr_soln >= ublox_msgs::msg::NavRELPOSNED9::CARR_FLOAT;
+  if (!rtk_ok) {
+    RCLCPP_ERROR_THROTTLE(get_logger(), *get_clock(), 1000,
+        "RELPOSNED rejected: carr_soln=%u heading_valid=%u",
+        msg.carr_soln, msg.rel_pos_heading_valid);
+    rtk_healthy_ = false;
+    diagnostic_updater_.broadcast(diagnostic_msgs::msg::DiagnosticStatus::ERROR,
+        "RTK heading invalid — holding /odometry/filtered");
+    return;               // was falling through and accepting bogus heading
+  }
+  heading_rad_        = msg.rel_pos_heading * 1e-5 * M_PI / 180.0;
+  last_heading_stamp_ = now();
+  rtk_healthy_        = true;
@@ void Ekf::step()
-  publish_filtered(state_);
+  if (!rtk_healthy_ && !params_.dr_fallback_enabled) {
+    // Previously produced zero /odometry/filtered messages for 3626 s and
+    // only surfaced as a single ekf_se_map 'No events recorded' diagnostic.
+    // Now we emit a loud ERROR every second so operators cannot miss it.
+    diagnostic_updater_.broadcast(diagnostic_msgs::msg::DiagnosticStatus::ERROR,
+        "Localization suspended: no valid RTK for "
+        + std::to_string((now() - last_heading_stamp_).seconds()) + " s");
+    return;
+  }
+  publish_filtered(state_);
--- a/dbw_interlock/src/enable_gate.cpp
+++ b/dbw_interlock/src/enable_gate.cpp
@@ bool EnableGate::allow()
-  return user_request_;
+  if (!user_request_) return false;
+  if (!localization_healthy_) {
+    RCLCPP_WARN(get_logger(),
+        "Refusing /vehicle/enable: localization_healthy=false");
+    return false;
+  }
+  return true;
--- a/ntrip_client/src/rtcm_framer.py
+++ b/ntrip_client/src/rtcm_framer.py
@@ def parse(self, buf):
-    # ad-hoc parser: advance until 0xD3, read length, emit slice
-    ...
+    # Replaced with RTKLIB-style CRC-24Q validated framer.
+    # Drop (don't forward) any frame whose CRC fails; update rolling
+    # crc_fail_ratio and publish /diagnostics ERROR if >10% over 5 s.
+    from .rtcm3 import decode_rtcm3_with_crc24q
+    for frame, ok in decode_rtcm3_with_crc24q(buf):
+        if not ok:
+            self.crc_fail_window.append(1); continue
+        self.crc_fail_window.append(0)
+        yield frame
+    if self.crc_fail_ratio() > 0.10:
+        self.diag.error(f"RTCM CRC fail rate {self.crc_fail_ratio():.0%}")
```

---
_Black Box · inference-only · Opus 4.7_
