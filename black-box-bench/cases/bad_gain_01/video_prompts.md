# Video / image prompts — bad_gain_01

> Feed these to Nano Banana Pro (stills) and Wan 2.2 (short clips). The output
> MP4s should be placed under `video/cam{0..4}.mp4` for ingestion.

## Nano Banana Pro (key frames)

Key frames of the four-wheeled indoor robot attempting to follow a gently curving painted line on a polished floor. Instead of tracking smoothly, the robot weaves left-right-left with increasing amplitude, the yaw visibly overshooting each correction. Later frames show the robot nearly sideways to the line. Wide hero angle and top-down plan with the painted reference path clearly visible as a green curve. Window context: from t=5.0s to t=20.0s: robot weaves left-right across a painted reference line with growing amplitude.. Strictly no humans in frame, no faces, no identifiable branding, no text overlays, no gore, no NSFW content. Daytime outdoor or industrial-floor lighting. Realistic consumer-robotics aesthetic, slightly worn.

## Wan 2.2 (video clip, 3-6s)

5-6 second clip. The robot tries to follow a painted serpentine reference line on a polished lab floor. It oscillates side-to-side around the line, each swing larger than the last (growing limit cycle). Wheels whir; the chassis visibly jerks with each overshoot. By the end of the clip the heading error is large enough that the robot is nearly perpendicular to the reference for brief moments. Steady camera, no cuts, no text, no UI. Emphasize the growing amplitude of the oscillation. Window context: from t=5.0s to t=20.0s: robot weaves left-right across a painted reference line with growing amplitude.. Strictly no humans in frame, no faces, no identifiable branding, no text overlays, no gore, no NSFW content. Daytime outdoor or industrial-floor lighting. Realistic consumer-robotics aesthetic, slightly worn.

## Camera layout (replicate x5)

Replicate the same 3-6 second clip across 5 synchronized cameras mounted on the mobile robot: (1) front-bumper wide (90 deg FOV), (2) rear-bumper wide, (3) left-side fisheye low, (4) right-side fisheye low, (5) mast top-down 45 deg. Keep world geometry and timing identical; only change the viewpoint with correct parallax and occlusion. Small (~2 cm) baseline jitter is acceptable; do not re-render the environment per view.

## Notes

Signature is growing-amplitude oscillation around a reference: the classic 'Kp too high' fingerprint. Distinguishable from sensor_timeout because the robot keeps moving forward and the reaction is periodic.
