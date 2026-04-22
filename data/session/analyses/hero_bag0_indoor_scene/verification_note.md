# Hero deep-dive — human verification (2026-04-22)

**Status**: Hero report conclusion `topic_misrouting` (confidence 0.95) is **INCORRECT**.
Original scenario-mining interpretation (vehicle parked at lab, line-of-sight through open doors) stands.

## Context the model lacked

Three domain facts, known to the operator, invalidate the model's geometric-impossibility argument:

1. **"Tripod rig" in rear frames is a permanent vehicle fixture.** What the model called a bench-test tripod/handlebar is a physical sensor mount / structural tube present in 100% of frames across the entire bag. Not evidence of a stationary lab camera.
2. **Static consecutive frames = parked vehicle, not bench cam.** Protocol: vehicle sits still for minutes at bag start and bag end. Frame-to-frame identity is expected, not anomalous.
3. **Left stream "switch" (kitchen → vestibule) is the return maneuver, not within-drive mux.** Bags close the loop by returning to origin. The left camera is filming the same building from outside at start and from inside/adjacent at end. Single topic, consistent geometry.

## Corrected reading

End-of-bag window (~3510-3530 s): vehicle parked at entrance of home robotics lab. Rear / left / right cameras have line-of-sight into workshop, kitchen, lobby through open doors. Right cam shows outdoor lot because it faces the parking area. No topic misrouting. Data-quality recommendation unchanged: **trim last ~120 s** before using as road-scene training data.

## Methodological caveat (worth keeping as tool caveat)

Hi-res re-analysis with a more confident prompt **over-committed** to the integrity-failure hypothesis despite the scenario-mining pass having already produced the correct reading. Lessons:

- More resolution ≠ more ground truth. The model saw more pixels but invented a "bench calibration rig" from a legitimate vehicle-mounted sensor tube.
- Prompt pre-loaded with "prior automated flag" framing (conf 0.9 topic-mux) biased reasoning toward confirming the flag rather than re-evaluating it.
- Geometric-impossibility arguments are only as sound as the model's assumption set. Here it assumed vehicle-in-motion; operator knows vehicle-parked.
- **Human-in-the-loop is load-bearing**, not decorative. Keep this case as the canonical example for the demo.

Artifacts retained as evidence: `hero_report.json`, `cost.json`. Do not delete.
