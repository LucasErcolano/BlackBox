# Video / image prompts — pid_saturation_01

> Feed these to Nano Banana Pro (stills) and Wan 2.2 (short clips). The output
> MP4s should be placed under `video/cam{0..4}.mp4` for ingestion.

## Nano Banana Pro (key frames)

First-person and top-down key frames of a small four-wheeled indoor delivery robot (matte grey chassis, ~40 cm wheelbase) driving down a long warehouse aisle between grey shelving. Concrete floor with faded yellow lane markings. In the first frames the robot tracks the lane centerline cleanly. In the final frames the robot is drifting off the lane to the right with a visibly yawed heading. Window context: from t=12.0s to t=18.0s: motors pinned at max, path drifting off-lane despite full throttle.. Motors audibly strain: exhaust whine implied by motion blur on the wheels (pinned at max RPM). Composition: low three-quarter hero angle and a matching top-down plan view. Sharp focus on the robot, mild depth of field on shelves. Strictly no humans in frame, no faces, no identifiable branding, no text overlays, no gore, no NSFW content. Daytime outdoor or industrial-floor lighting. Realistic consumer-robotics aesthetic, slightly worn.

## Wan 2.2 (video clip, 3-6s)

4-6 second clip. A small grey four-wheel indoor delivery robot drives forward down a warehouse aisle at a steady pace. For the first ~60% of the clip it tracks the painted lane centerline smoothly. Then, over ~1.5 seconds, it begins drifting laterally to the right while its heading yaws further off-axis; wheels keep spinning at maximum RPM (no visible deceleration) even as trajectory error grows. Camera holds steady. Background: shelves with blurred boxes, faint fluorescent flicker. No cuts, no text, no UI overlays. Emphasize the disconnect between commanded motion (full throttle) and actual path (diverging). Window context: from t=12.0s to t=18.0s: motors pinned at max, path drifting off-lane despite full throttle.. Strictly no humans in frame, no faces, no identifiable branding, no text overlays, no gore, no NSFW content. Daytime outdoor or industrial-floor lighting. Realistic consumer-robotics aesthetic, slightly worn.

## Camera layout (replicate x5)

Replicate the same 3-6 second clip across 5 synchronized cameras mounted on the mobile robot: (1) front-bumper wide (90 deg FOV), (2) rear-bumper wide, (3) left-side fisheye low, (4) right-side fisheye low, (5) mast top-down 45 deg. Keep world geometry and timing identical; only change the viewpoint with correct parallax and occlusion. Small (~2 cm) baseline jitter is acceptable; do not re-render the environment per view.

## Notes

The visible signature is actuator-pinned-at-rail while pose error grows: wheels maxed, trajectory walking off. Integral windup is not directly visible; infer it from the sustained saturation + divergence.
