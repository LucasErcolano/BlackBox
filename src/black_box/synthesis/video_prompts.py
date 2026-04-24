# SPDX-License-Identifier: MIT
"""Textual prompts for image/video generation (Nano Banana Pro + Wan 2.2).

These are artifacts only — no API is called from here. A human operator feeds
these into the respective tools and drops the resulting MP4s into
``black-box-bench/cases/<key>/video/``.
"""

from __future__ import annotations

from typing import Dict


_SAFETY_SUFFIX = (
    "Strictly no humans in frame, no faces, no identifiable branding, no text "
    "overlays, no gore, no NSFW content. Daytime outdoor or industrial-floor "
    "lighting. Realistic consumer-robotics aesthetic, slightly worn."
)


_CAMERA_LAYOUT = (
    "Replicate the same 3-6 second clip across 5 synchronized cameras mounted "
    "on the mobile robot: (1) front-bumper wide (90 deg FOV), (2) rear-bumper "
    "wide, (3) left-side fisheye low, (4) right-side fisheye low, (5) mast "
    "top-down 45 deg. Keep world geometry and timing identical; only change "
    "the viewpoint with correct parallax and occlusion. Small (~2 cm) baseline "
    "jitter is acceptable; do not re-render the environment per view."
)


def _pid_saturation_prompts(window_description: str) -> Dict[str, str]:
    nb = (
        "First-person and top-down key frames of a small four-wheeled indoor "
        "delivery robot (matte grey chassis, ~40 cm wheelbase) driving down a "
        "long warehouse aisle between grey shelving. Concrete floor with faded "
        "yellow lane markings. In the first frames the robot tracks the lane "
        "centerline cleanly. In the final frames the robot is drifting off the "
        f"lane to the right with a visibly yawed heading. Window context: {window_description}. "
        "Motors audibly strain: exhaust whine implied by motion blur on the "
        "wheels (pinned at max RPM). Composition: low three-quarter hero angle "
        "and a matching top-down plan view. Sharp focus on the robot, mild "
        "depth of field on shelves. " + _SAFETY_SUFFIX
    )
    wan = (
        "4-6 second clip. A small grey four-wheel indoor delivery robot drives "
        "forward down a warehouse aisle at a steady pace. For the first ~60% "
        "of the clip it tracks the painted lane centerline smoothly. Then, "
        "over ~1.5 seconds, it begins drifting laterally to the right while "
        "its heading yaws further off-axis; wheels keep spinning at maximum "
        "RPM (no visible deceleration) even as trajectory error grows. Camera "
        "holds steady. Background: shelves with blurred boxes, faint fluorescent "
        "flicker. No cuts, no text, no UI overlays. Emphasize the disconnect "
        "between commanded motion (full throttle) and actual path (diverging). "
        f"Window context: {window_description}. " + _SAFETY_SUFFIX
    )
    notes = (
        "The visible signature is actuator-pinned-at-rail while pose error "
        "grows: wheels maxed, trajectory walking off. Integral windup is not "
        "directly visible; infer it from the sustained saturation + divergence."
    )
    return {"nano_banana_pro_prompt": nb, "wan22_prompt": wan, "notes": notes}


def _sensor_timeout_prompts(window_description: str) -> Dict[str, str]:
    nb = (
        "Key frames of the same four-wheeled indoor robot cruising an open "
        "lab floor. Mid-shot: the robot is moving forward calmly. Next frame: "
        "the robot abruptly brakes and begins a sharp, jerky in-place rotation "
        "as if avoiding something — but the space in front of it is visibly "
        "empty (no obstacle, no person, no object). A small 2D lidar dome is "
        "visible on top. Polished concrete floor, soft overhead lighting, a few "
        "blurry cardboard boxes ~5 m away. Composition: hero side angle plus "
        f"top-down. Window context: {window_description}. " + _SAFETY_SUFFIX
    )
    wan = (
        "4 second clip. The robot cruises forward at a steady walking pace "
        "down an open lab aisle. Around the 1.5 s mark it abruptly stops "
        "(linear velocity drops to zero) and begins a fast oscillating "
        "in-place yaw — left, right, left — as though reacting to a close "
        "obstacle. Crucially, the space in front of and around the robot is "
        "empty; no object, no person, no shadow that could justify the "
        "reaction. Hold the camera steady. No cuts. Emphasize the phantom "
        "nature of the avoidance: a reaction with no visible cause. "
        f"Window context: {window_description}. " + _SAFETY_SUFFIX
    )
    notes = (
        "Signature is 'reaction without cause': empty scene, violent avoidance "
        "maneuver. This is what a stale range reading looks like from outside."
    )
    return {"nano_banana_pro_prompt": nb, "wan22_prompt": wan, "notes": notes}


def _bad_gain_prompts(window_description: str) -> Dict[str, str]:
    nb = (
        "Key frames of the four-wheeled indoor robot attempting to follow a "
        "gently curving painted line on a polished floor. Instead of tracking "
        "smoothly, the robot weaves left-right-left with increasing amplitude, "
        "the yaw visibly overshooting each correction. Later frames show the "
        "robot nearly sideways to the line. Wide hero angle and top-down plan "
        "with the painted reference path clearly visible as a green curve. "
        f"Window context: {window_description}. " + _SAFETY_SUFFIX
    )
    wan = (
        "5-6 second clip. The robot tries to follow a painted serpentine "
        "reference line on a polished lab floor. It oscillates side-to-side "
        "around the line, each swing larger than the last (growing limit "
        "cycle). Wheels whir; the chassis visibly jerks with each overshoot. "
        "By the end of the clip the heading error is large enough that the "
        "robot is nearly perpendicular to the reference for brief moments. "
        "Steady camera, no cuts, no text, no UI. Emphasize the growing "
        f"amplitude of the oscillation. Window context: {window_description}. "
        + _SAFETY_SUFFIX
    )
    notes = (
        "Signature is growing-amplitude oscillation around a reference: the "
        "classic 'Kp too high' fingerprint. Distinguishable from sensor_timeout "
        "because the robot keeps moving forward and the reaction is periodic."
    )
    return {"nano_banana_pro_prompt": nb, "wan22_prompt": wan, "notes": notes}


_DISPATCH = {
    "pid_saturation": _pid_saturation_prompts,
    "sensor_timeout": _sensor_timeout_prompts,
    "bad_gain_tuning": _bad_gain_prompts,
}


def video_prompt_for(bug_class: str, window_description: str) -> Dict[str, str]:
    """Return image + video prompts + camera layout + notes for a bug class."""
    if bug_class not in _DISPATCH:
        raise KeyError(f"unknown bug_class {bug_class!r}; expected one of {list(_DISPATCH)}")
    base = _DISPATCH[bug_class](window_description)
    return {
        "nano_banana_pro_prompt": base["nano_banana_pro_prompt"],
        "wan22_prompt": base["wan22_prompt"],
        "camera_layout": _CAMERA_LAYOUT,
        "notes": base["notes"],
    }
