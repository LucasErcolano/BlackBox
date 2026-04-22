# rtk_heading_break_01

**Bug class:** `sensor_timeout` (rover emits syntactically valid messages with payload that never becomes valid)
**Source:** real ROS 1 Noetic bag, session `sanfer_sanisidro` 2026-02-03
**Duration:** 3626.8 s (~1 h)
**Mode:** forensic post-mortem
**Why this case matters:** a forensic pipeline that only checks fix-quality metrics (numSV, hAcc, fixType) would pass this bag as healthy. The failure is in the dual-antenna RTK heading subsystem, visible only in `navrelposned.flags` and carrier-phase bits of `navpvt.flags`. Operator's self-reported hypothesis ("GPS falla bajo el túnel") is wrong. A grounded tool must disagree.

## Telemetry topics (in `telemetry.npz`)

| array | units | source topic |
|---|---|---|
| `rover_t_ns`, `rover_numSV`, `rover_hAcc_mm`, `rover_fixType`, `rover_carr` | ns, count, mm, enum, enum (0=none,1=float,2=fixed) | `/ublox_rover/navpvt` |
| `mb_t_ns`, `mb_numSV`, `mb_hAcc_mm`, `mb_carr` | ns, count, mm, enum | `/ublox_moving_base/navpvt` |
| `relpos_t_ns`, `relpos_flags`, `relpos_relPosLength_cm`, `relpos_accLength_0p1mm`, `relpos_relPosHeading_1e5deg` | ns, u32 bitfield, cm, 0.1 mm, 1e-5 deg | `/ublox_rover/navrelposned` |

Load: `np.load('telemetry.npz')`.

### Key flag bits (`relpos_flags`)

- bit 0 `GNSS_FIX_OK`
- bit 1 `DIFF_SOLN` (RTCM corrections applied)
- bit 2 `REL_POS_VALID` ← **never set in this bag**
- bits 3–4 `CARR_SOLN` (0 none / 1 float / 2 fixed)
- bit 5 `IS_MOVING`

### Key flag bits (`rover_carr`, derived from `navpvt.flags` bits 6–7)

- 0 = `CARRIER_PHASE_NO_SOLUTION`
- 1 = float
- 2 = fixed

## Signature of the anomaly

```
rover_carr  : 100% zero           (18133/18133 = CARR_NONE)
relpos_flags & 0x04 : 100% zero   (REL_POS_VALID never set)
mb_carr     : 5.7% zero, 63.6% float, 30.7% fixed   (base is healthy)
rover_numSV : min 16, max 32, median 29             (looks fine)
rover_hAcc  : min 0.47 m, median 0.65 m, max 1.3 m  (looks fine)
```

**Contrast between rover and moving-base is the load-bearing evidence.** Any hypothesis that blames signal strength, obstacles, or tunneling contradicts the rover's own NavPVT quality metrics.

## What the tool must do

1. Detect the carrier-phase NONE / REL_POS_VALID never-set pattern as primary evidence.
2. Use the moving-base healthy state as cross-source corroboration (rules out sky / interference).
3. **Not** accept the operator's tunnel hypothesis. Flag it as `anti_hypothesis` per `ground_truth.json`.
4. Emit a scoped patch prescription: gate `relPosHeading` consumption on `FLAGS_REL_POS_VALID` with an explicit degraded-heading fallback.

## Scoring

Pipeline output must satisfy:
- `bug_class == "sensor_timeout"` (closest match in closed taxonomy; `calibration_drift` acceptable alternate)
- Evidence cites at least 2 of: `/ublox_rover/navpvt`, `/ublox_rover/navrelposned`, `/ublox_moving_base/navpvt`
- Patch hint references `FLAGS_REL_POS_VALID` or equivalent bit-gate
- Does NOT emit a sub-window window_s (failure is session-wide)
- Does NOT confirm operator's tunnel hypothesis

## Files

- `ground_truth.json` — machine-readable labels + anti-hypothesis for eval
- `telemetry.npz` — numpy arrays extracted from the real bag (297 KB)
- `README.md` — this file

Full bag not redistributed (145 MB sensors + 364 GB cam-lidar, not licensed for public release).
