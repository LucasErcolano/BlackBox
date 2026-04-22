# pid_saturation_01

**Bug class:** `pid_saturation`
**Ground-truth window:** 12.0s – 18.0s

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
- PWM on /pwm pegs at 255 for all 4 motors starting at ~12.0s
- /odom/pose yaw and y drift from /reference after ~15.0s
- /cmd_vel linear command keeps rising while pose stops tracking

## Patch hint
Add anti-windup to PIDController.step: only accumulate the integral when the unclamped output is inside [PWM_MIN, PWM_MAX] or when the error would reduce saturation.
