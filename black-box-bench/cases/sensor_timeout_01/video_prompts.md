# Video / image prompts — sensor_timeout_01

> Feed these to Nano Banana Pro (stills) and Wan 2.2 (short clips). The output
> MP4s should be placed under `video/cam{0..4}.mp4` for ingestion.

## Nano Banana Pro (key frames)

Key frames of the same four-wheeled indoor robot cruising an open lab floor. Mid-shot: the robot is moving forward calmly. Next frame: the robot abruptly brakes and begins a sharp, jerky in-place rotation as if avoiding something — but the space in front of it is visibly empty (no obstacle, no person, no object). A small 2D lidar dome is visible on top. Polished concrete floor, soft overhead lighting, a few blurry cardboard boxes ~5 m away. Composition: hero side angle plus top-down. Window context: from t=10.0s to t=14.0s: robot violently turns in place despite an empty corridor ahead.. Strictly no humans in frame, no faces, no identifiable branding, no text overlays, no gore, no NSFW content. Daytime outdoor or industrial-floor lighting. Realistic consumer-robotics aesthetic, slightly worn.

## Wan 2.2 (video clip, 3-6s)

4 second clip. The robot cruises forward at a steady walking pace down an open lab aisle. Around the 1.5 s mark it abruptly stops (linear velocity drops to zero) and begins a fast oscillating in-place yaw — left, right, left — as though reacting to a close obstacle. Crucially, the space in front of and around the robot is empty; no object, no person, no shadow that could justify the reaction. Hold the camera steady. No cuts. Emphasize the phantom nature of the avoidance: a reaction with no visible cause. Window context: from t=10.0s to t=14.0s: robot violently turns in place despite an empty corridor ahead.. Strictly no humans in frame, no faces, no identifiable branding, no text overlays, no gore, no NSFW content. Daytime outdoor or industrial-floor lighting. Realistic consumer-robotics aesthetic, slightly worn.

## Camera layout (replicate x5)

Replicate the same 3-6 second clip across 5 synchronized cameras mounted on the mobile robot: (1) front-bumper wide (90 deg FOV), (2) rear-bumper wide, (3) left-side fisheye low, (4) right-side fisheye low, (5) mast top-down 45 deg. Keep world geometry and timing identical; only change the viewpoint with correct parallax and occlusion. Small (~2 cm) baseline jitter is acceptable; do not re-render the environment per view.

## Notes

Signature is 'reaction without cause': empty scene, violent avoidance maneuver. This is what a stale range reading looks like from outside.
