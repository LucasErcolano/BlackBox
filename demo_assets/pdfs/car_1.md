# Black Box — Forensic Report

**Case:** `car_1` &nbsp;·&nbsp; **Mode:** `scenario_mining`  
**Duration:** 970.20 s  
**Generated:** 2026-04-23 16:32:05Z  
**Model:** `claude-opus-4-7` (inference-only)

> Ego vehicle remains at the same parking-lot barrier/gate pose for ~130 s (frames 20 s–150 s are visually near-identical) before proceeding, suggesting a prolonged idle/stuck state at the gate.

---

## Executive Summary

| # | bug class | confidence | summary |
|---|-----------|-----------:|---------|
| 1 | `state_machine_deadlock` **[ROOT CAUSE]** | `██████░░░░` 0.60 | Ego vehicle remains at the same parking-lot barrier/gate pose for ~130 s (frames 20 s–150 s are visually near-identical) before proceeding, suggesting a prolonged idle/stuck state at the gate. |
| 2 | `other` | `██████░░░░` 0.55 | Initial ~5 s of camera stream is severely overexposed (near-pure-white), indicating auto-exposure convergence failure or recording started before ISP stabilized. |

## Timeline

| t | label | source |
|---|-------|--------|
| `  15.30 s` | camera fully blown-out (saturated white) |  |
| `  17.60 s` | exposure partially recovers, scene still washed |  |
| `  20.10 s` | first usable frame: ego stopped at parking-lot barrier/gate |  |
| `02:30.00` | after ~130 s, ego still at identical barrier pose (stuck scene) |  |
| `03:00.00` | ego has finally moved onto adjacent street |  |

## Hypotheses — Detail

### 1. `state_machine_deadlock` — confidence 0.60

Ego vehicle remains at the same parking-lot barrier/gate pose for ~130 s (frames 20 s–150 s are visually near-identical) before proceeding, suggesting a prolonged idle/stuck state at the gate.

**Evidence**

- **camera** · `frame_00020.1s_dense.jpg` @ `  20.10 s`
  > Ego stopped facing boom barrier with parked cars on left and gate ticket booth ahead.
- **camera** · `frame_00050.1s_dense.jpg` @ `  50.10 s`
  > Identical viewpoint 30 s later — same cars, same barrier, same pedestrian position — no measurable ego motion.
- **camera** · `frame_00100.1s_dense.jpg` @ `01:40.10`
  > Still identical parking-lot/barrier scene ~80 s after first usable frame.
- **camera** · `frame_00180.0s_dense.jpg` @ `03:00.00`
  > Scene finally changes — ego has departed onto adjacent residential street.

**Patch hint:** Check planner/controller behavior at closed gates; add timeout + operator alert if ego is stationary >N s with no lead obstacle within stop distance.

### 2. `other` — confidence 0.55

Initial ~5 s of camera stream is severely overexposed (near-pure-white), indicating auto-exposure convergence failure or recording started before ISP stabilized.

**Evidence**

- **camera** · `frame_00015.3s_dense.jpg` @ `  15.30 s`
  > Almost entirely saturated white image; only faint foliage edges visible.
- **camera** · `frame_00017.6s_dense.jpg` @ `  17.60 s`
  > Still heavily blown out; partial recovery, parked cars barely resolvable at edges.
- **camera** · `frame_00020.1s_dense.jpg` @ `  20.10 s`
  > Exposure has normalized — scene now correctly exposed.

**Patch hint:** Reject / mask perception outputs until AE has converged (e.g., gate on image mean-luma + histogram saturation ratio) and/or pre-warm the camera before autonomy-engage.

## Proposed Patch

```diff
Primary concern: ego remained stationary at the parking-lot barrier for ~130 s — validate whether the planner correctly detected a closed gate and whether human takeover was required; add a stuck-state detector with operator alert. Secondary: guard perception consumers against the ~5 s of saturated-white camera frames at session start (likely AE not yet converged).
```

---
_Black Box · inference-only · Opus 4.7_
