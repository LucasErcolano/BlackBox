# bad_gain_01

**Bug class:** `bad_gain_tuning`
**Ground-truth window:** 5.0s – 20.0s

## Telemetry topics
  - `/odom/pose` fields=['x', 'y', 'yaw']
  - `/cmd_vel` fields=['linear', 'angular']
  - `/pwm` fields=['m0', 'm1', 'm2', 'm3']
  - `/reference` fields=['x', 'y', 'yaw']

## Files

- `ground_truth.json` — machine-readable labels for eval.
- `telemetry.npz` — numpy arrays (use `np.load(..., allow_pickle=True)`).
- `source/buggy/` — the controller as shipped; reproduces the bug.
- `source/clean/` — intended fix; compare for patch diff demo.
- `video_prompts.md` — prompts for Nano Banana Pro (stills) and Wan 2.2 (clips).

## Evidence hints
- /cmd_vel angular oscillates at ~2.5 rad/s with growing amplitude
- /odom/pose yaw overshoots /reference yaw on every swing
- /pwm alternates left/right wheel pairs in square-wave fashion

## Patch hint
Reduce HeadingController.Kp from 4.5 to ~0.8 and add a dead-band guard: if |err| < 1e-3 rad, command 0 angular rate to avoid limit-cycling on sensor noise.
