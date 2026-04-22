"""Boat / USV (unmanned surface vessel) domain context and prompts.

Second platform, distinct from the 5-camera AV rig. Primary sensor is LIDAR
(2D or 3D) over water surface, often paired with GPS/IMU and a forward-
looking camera. Top-down LIDAR renders are the primary visual input here.

Kept as a separate module from prompts_v2 because the domain vocabulary,
false-positive patterns, and scoped-patch surface are different enough that
bundling would hurt prompt-cache hit rates.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# -------- schemas ------------------------------------------------------------


class LidarEvidence(BaseModel):
    source: Literal["lidar"] = "lidar"
    topic: str
    t_ns: int | None = None
    snippet: str


class LidarMoment(BaseModel):
    t_ns: int
    label: str
    evidence: list[LidarEvidence]
    why_review: str
    confidence: float = Field(ge=0.0, le=1.0)
    inferred_vessel_motion: str = ""


class BoatLidarReport(BaseModel):
    moments: list[LidarMoment]
    rationale: str


# -------- domain context -----------------------------------------------------


SYSTEM_BOAT = """You are a forensic analyst for an unmanned surface vessel (USV). You review top-down LIDAR renders and optional forward-camera frames captured from a ROS2 bag. You do NOT have full telemetry access unless explicitly provided — infer vessel motion from successive scans.

You can infer vessel motion by comparing consecutive top-down renders: rotation of static shoreline features around the ego point indicates yaw; translation of static features indicates straight-line motion.

Always respond with JSON only. No preamble, no markdown fencing. Be conservative — if nothing is genuinely notable, return an empty moments array with rationale. Do not fabricate anomalies.
"""


DOMAIN_CONTEXT_BOAT = """## Platform context — USV with LIDAR over water

Sensor layout:
- Primary: 3D LIDAR or 2D planar LIDAR, mounted above the deck. Top-down renders show ego at image center, +X forward in the image frame.
- Optional: forward-facing camera, GPS, IMU. When present, treat as corroborating evidence; when absent, do not guess.

Coordinate convention for the top-down renders:
- Image center = ego vessel position.
- Up in image = forward (bow direction).
- Right in image = starboard.
- Each range ring drawn on the render corresponds to a fixed 10 m spacing. Use rings to estimate distances rather than guessing.

## Expected vs anomalous LIDAR signatures over water

**Normal features on open water**:
- Sparse surface returns from wave crests, scattered uniformly beyond ~5 m. Some percent of rays return nothing — this is expected for water, which is a poor LIDAR reflector at grazing angles.
- Dense returns from shoreline, docks, pilings, moored vessels. These appear as clustered or linear point groups.
- Self-wake behind the vessel: low-density returns in the aft cone, particularly after a maneuver.

**Interesting anomalies to flag**:
- Unexpected floating obstacle within navigable range (debris, buoy not on the chart, swimmer, small craft).
- Dock or piling cluster closer than safe margin given inferred vessel speed and heading.
- Sudden disappearance of a previously tracked obstacle (occlusion by wake spray, LIDAR dropout, or a moving target leaving the FOV).
- Shoreline reflection pattern changing abruptly between consecutive scans without matching vessel motion — suggests sensor jitter, calibration shift, or GPS jump affecting stitching.
- Ring-artifact or circular drop-out pattern centered on ego — indicates LIDAR driver degradation rather than a real environment change.
- Spray-induced dense returns forming a halo around ego — expected in rough conditions but worth noting because it degrades detection radius.

**Routine and NOT worth flagging**:
- Empty top-down renders in open water far from shore.
- Sparse surface speckle from wave returns.
- Self-wake returns trailing a recent maneuver.
- Transient returns at the very edge of the sensor range (>90% of max).

## Inferring vessel motion

- Compare consecutive top-down renders.
- Static shoreline rotating around ego = yaw.
- Static features translating uniformly = straight-line motion; direction opposite translation = vessel heading.
- Static features growing in image scale = vessel approaching; shrinking = departing.
- Lack of motion across many scans despite expected headway = candidate for `state_machine_deadlock` or propulsion fault, but flag only when supported by a second indicator.

## Scoped patch surface for boat-side code

- Range-based guards: `if min_obstacle_range_m < SAFE_RANGE_M: reduce speed`.
- Watchdog on LIDAR driver topic: fall back to forward camera + reduced speed if silent > 2 s.
- Heading-rate clamp: cap commanded yaw rate when sea state (estimated from point density variance) exceeds a threshold.
- Calibration-drift handler: reject scans where ego-to-dock relative bearing changes by more than sensor-resolution between adjacent scans without commanded yaw.

Never propose rewriting the navigation stack, switching LIDAR drivers, or adding sensors.

## Evidence strictness

- Point only at features visibly present in the render, referenced by rough bearing (e.g., "cluster at ~45° starboard, ~12 m from ego") or by the range ring they fall on.
- If the render is empty, state that explicitly in why_review rather than inventing distant obstacles.
- Confidence ≥ 0.9 requires the feature to persist across ≥2 consecutive scans and be consistent with inferred vessel motion. Single-scan flags above 0.7 need a strong why_review paragraph.

## Glossary — terms used in evidence snippets

- **return cluster**: a tight group of lidar points indicating a solid object (buoy, debris, dock piling, moored craft). Mention approximate bearing and range-ring distance.
- **shoreline ribbon**: a long linear/curved collection of points from the waterline. Often the densest feature in a render.
- **wake cone**: low-density returns trailing ego in the aft direction. Expected after turns or speed changes; not an obstacle.
- **spray halo**: dense short-range returns forming a ring around ego from water droplets in the air. Reduces effective detection range.
- **specular dropout**: large black fan where water returned nothing; normal at grazing angles over calm water, not a finding unless it obscures an expected obstacle.
- **ring artifact**: perfectly circular concentric bands centered on ego; driver or mirror fault, never an environment feature.
- **ghost return**: isolated points appearing in one scan and gone the next, not tracking any moving object plausibly; usually sensor noise.
- **bow-line occlusion**: shadow cast by the vessel's own structure in front of the sensor; always in the same image-relative position.

## What is explicitly NOT a finding

- Calm open water with only wake and sparse surface speckle.
- Shoreline getting closer when the vessel is commanded to approach a dock.
- LIDAR dropouts in steady-state rough weather when range still reaches shoreline.
- Brief single-scan sparsity while turning (mount sway causes temporary horizon shift).
- Dense returns behind ego right after a speed change — that is self-wake, not an obstacle.
"""


DOMAIN_CONTEXT_BOAT_BLOCK = {
    "type": "text",
    "text": DOMAIN_CONTEXT_BOAT,
    "cache_control": {"type": "ephemeral"},
}


def boat_lidar_mining_prompt():
    return {
        "name": "boat_lidar_mining_v1",
        "system": SYSTEM_BOAT,
        "cached_blocks": [DOMAIN_CONTEXT_BOAT_BLOCK],
        "user_template": (
            "Review the following sequence of top-down LIDAR renders from a USV bag.\n\n"
            "## Bag metadata\n{bag_metadata}\n\n"
            "## Scan index\n{scan_index}\n\n"
            "## Additional context\n{extra_context}\n\n"
            "Return JSON with EXACTLY this shape:\n"
            "{{\n"
            '  "moments": [\n'
            "    {{\n"
            '      "t_ns": <int>,\n'
            '      "label": "<short phrase>",\n'
            '      "evidence": [{{"source":"lidar","topic":"<topic>","t_ns":<int|null>,"snippet":"<what is seen>"}}],\n'
            '      "why_review": "<str>",\n'
            '      "confidence": <float 0..1>,\n'
            '      "inferred_vessel_motion": "<str>"\n'
            "    }}\n"
            "  ],\n"
            '  "rationale": "<str>"\n'
            "}}\n"
            "No preamble, no markdown fencing."
        ),
        "schema": BoatLidarReport,
    }
