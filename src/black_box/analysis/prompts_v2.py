"""DEPRECATED: AV-specific vision-only prompts.

Kept for back-compat with older callers and the mocked grounding-gate
tests. New code should use `black_box.analysis.prompts_generic`, which
is platform-agnostic and accepts a Manifest + optional operator prompt.

This module will be removed once scripts and tests are fully migrated.
"""
import warnings

from pydantic import BaseModel, Field
from typing import Literal

warnings.warn(
    "black_box.analysis.prompts_v2 is deprecated; use prompts_generic instead.",
    DeprecationWarning,
    stacklevel=2,
)


# -------- schemas ------------------------------------------------------------


class CamPresence(BaseModel):
    shows: list[str] = Field(default_factory=list)
    misses: list[str] = Field(default_factory=list)


class VisualEvidence(BaseModel):
    source: Literal["camera"] = "camera"
    camera: str
    t_ns: int | None = None
    snippet: str


class VisualMoment(BaseModel):
    t_ns: int
    label: str
    cameras: CamPresence
    evidence: list[VisualEvidence]
    why_review: str
    confidence: float
    inferred_ego_motion: str = ""


class VisualMiningReport(BaseModel):
    moments: list[VisualMoment]
    rationale: str


class WindowSummary(BaseModel):
    per_camera: dict[str, str]
    overall: str
    interesting: bool
    reason: str


# -------- prompts ------------------------------------------------------------


SYSTEM_AV = """You are a forensic analyst for autonomous vehicles reviewing footage from a ROS bag that has NO telemetry available (no odometry, IMU, velocity, steering, or GPS). You have ONLY 5 synchronized cameras around the vehicle.

Camera roles:
- cam1: front_left
- cam5: front_right
- cam6: right (side)
- cam4: rear
- cam3: left (side)

You can infer ego-vehicle motion by comparing consecutive frames of the same camera. Indicate whenever a moment appears to involve sudden change of speed or direction inferred visually (e.g., rapid forward scene compression = braking; horizon rotation = yaw).

Always respond with JSON only. No preamble, no markdown fencing. Be conservative — if nothing is genuinely notable, return an empty moments array with rationale. Do not fabricate anomalies.
"""


# Stable domain context reused across prompts. Kept large and stable on purpose:
# Anthropic cache threshold is ~1024 tokens per cached block for Opus/Sonnet. Below
# that, cache_control is ignored and every call re-ingests. Keep this text
# append-only; edits invalidate the cache for every downstream call.
DOMAIN_CONTEXT_AV = """## Platform context — 5-camera AV rig

Sensor layout on the test vehicle:
- cam1 (front_left): forward-facing left of centerline, ~55° HFOV, mounted behind windshield. Primary driving camera for left-lane awareness.
- cam5 (front_right): forward-facing right of centerline, ~55° HFOV, same vertical level as cam1. Primary for right-lane and shoulder awareness.
- cam6 (right, side): lateral right, ~90° HFOV, mirrors-level. Covers right blind spot; overlaps cam5 on the far right and cam4 on the right quarter.
- cam4 (rear): rearward, ~100° HFOV, roof-mounted. Covers following vehicles and reverse maneuvers.
- cam3 (left, side): lateral left, ~90° HFOV, mirrors-level. Covers left blind spot; overlaps cam1 on the far left and cam4 on the left quarter.

Exposure: each camera runs an independent auto-exposure loop. A bright object in front of one camera does not change another camera's exposure. This means overexposure symptoms (bloom, clipped highlights, AE hunt) are per-camera and can appear in one view while neighbors look normal.

Sync: all 5 streams share a common hardware trigger. Frame timestamps within a single window are expected to agree within ~20 ms. Larger skew is itself a finding.

## Known failure modes (bug taxonomy, closed set)

When reporting moments, label the underlying suspected cause only when visually supported. Do NOT guess at software state. The taxonomy below is the authorized vocabulary:

1. **pid_saturation** — control output pegged at actuator limit; symptoms are drift or oscillation that the controller cannot correct despite visible effort.
2. **sensor_timeout** — stale or frozen data; visually, a camera frame that is byte-identical or near-identical across multiple timestamps is a candidate.
3. **state_machine_deadlock** — vehicle stopped in a non-terminal state with no progress despite clear path; visual signature is a held-still ego with unchanged scene.
4. **bad_gain_tuning** — overshoot, ringing, or under-damped response; visually, horizon rotation that oscillates around a setpoint.
5. **missing_null_check** — perception or planning failure when an expected input is absent; visually, mismatched reaction to an obvious hazard (e.g., cyclist visible in 2+ cameras, no response).
6. **calibration_drift** — same physical object localized differently across cameras; visually, an object crossing a camera boundary appears to jump laterally or vertically.
7. **latency_spike** — event visible in one camera lags its neighbor by more than expected sync tolerance.

## Forensic rigor rules

- Report only what is visible. If the cause requires non-visual data (IMU, odom, controller state), note this as "requires telemetry to confirm" in why_review instead of guessing.
- A single-frame artifact (compression block, isolated glare pixel, single dropped frame) is NOT a moment worth reporting unless it aligns with a multi-frame or multi-camera pattern.
- Overlap-camera reasoning: if an object should appear in two cameras given the geometry above and appears only in one, that is a calibration_drift or latency_spike candidate.
- Ego-motion inference: rapid increase in image-space object size across consecutive frames = approach or ego deceleration; decrease = departure or ego acceleration; horizon roll = yaw; lateral translation of distant features = straight-line motion at the inferred speed.
- Confidence calibration: 0.9+ requires corroboration across ≥2 cameras or ≥3 frames. 0.5–0.8 is single-camera multi-frame. Below 0.5 should usually not be reported unless it is the only candidate and why_review explains the weakness.

## Output discipline

- JSON only. No prose outside the JSON. No markdown fencing.
- Empty moments array is a valid answer. A clean window is not a failure of analysis; it is the expected output when nothing unusual occurred.
- Rationale field explains the overall window call, including why clean windows were judged clean. One or two sentences.

## Glossary — terms used in evidence snippets

- **bloom**: bright pixels leaking into neighboring darker pixels; signals sensor saturation.
- **clipped highlights**: pixel values at 255 with no texture recoverable; AE failed to stop down fast enough.
- **AE hunt**: auto-exposure oscillating between over- and under-exposed frames in sequence; indicates controller instability in the AE loop itself, not necessarily a driving bug.
- **scene compression**: rapid growth of fixed-size objects across frames, indicating ego approach or the external object approaching; used to infer speed change without odometry.
- **frame dropout**: visible discontinuity where the scene advances by more than one expected inter-frame interval; usually a logging or bandwidth issue.
- **ghost object**: object present in one camera and missing from its overlap partner despite being within both FOVs; candidate for calibration_drift or per-camera latency.
- **occlusion cascade**: multiple cameras losing track of the same object as it passes behind a single obstacle; normal behavior, not a finding.
- **sun glare**: specular reflection of the sun, typically single-camera and lasting seconds; report only if it coincides with a missed hazard or a planning reaction.
- **rain artifact**: droplets on the lens that persist across frames in fixed image positions; distinguishes from environmental hazards which move.
- **horizon roll**: pitch/roll of the visible horizon line between frames; direct visual proxy for vehicle yaw/pitch rate.
- **ego stall**: consecutive frames nearly identical across all 5 cameras for >2 seconds; candidate for state_machine_deadlock if context implies motion was expected.

## What is NOT a finding

- Routine scene content: pedestrians walking on sidewalks in the direction of travel, cars in adjacent lanes at normal spacing, standard traffic signals, expected cone placement in construction zones.
- Single-frame compression blocks from JPEG encoding.
- Lens flare on bright pointwise light sources when it does not interfere with hazard detection.
- Water spray from the ego's own tires in wet conditions, unless it obscures a hazard.

Environmental transitions (tunnel entry/exit, shadow bands, overpass shadow, glare) are NOT automatically excluded: when they coincide with telemetry degradation or a downstream planning/perception anomaly, report the correlation anchored to a t_ns.
"""

DOMAIN_CONTEXT_BLOCK = {
    "type": "text",
    "text": DOMAIN_CONTEXT_AV,
    "cache_control": {"type": "ephemeral"},
}


def visual_mining_prompt():
    return {
        "name": "visual_mining_v2",
        "system": SYSTEM_AV,
        "cached_blocks": [
            DOMAIN_CONTEXT_BLOCK,
            {
                "type": "text",
                "text": (
                    "## What to look for (visual-only)\n\n"
                    "1. **Cross-camera inconsistency**: object visible in one view that geometry says should also appear in a neighboring view and does not, or appears with delay/latency.\n"
                    "2. **Near-misses / tight margins**: close passes with pedestrians, cyclists, other vehicles, static obstacles.\n"
                    "3. **Environmental rarities**: pedestrian in unusual position, animal, debris, unsigned construction, road hazard.\n"
                    "4. **Inferred ego behavior anomalies**: sudden braking (scene compression jumps), swerve (horizon rotation between adjacent frames), stall (identical scene across frames).\n"
                    "5. **Perception blockers**: critical occlusion, sun glare, rain drops on lens, sensor blur, frame dropouts visible as jumps.\n\n"
                    "For each moment reported:\n"
                    "- exact t_ns (pick from one of the frame timestamps provided)\n"
                    "- label: short phrase\n"
                    "- cameras.shows / cameras.misses: which cameras see it, which should have but do not\n"
                    "- evidence: per-camera concrete visual description (what is SEEN, not speculated causes)\n"
                    "- why_review: why an AV engineer should look at this manually\n"
                    "- confidence: 0.0–1.0\n"
                    "- inferred_ego_motion: one short phrase\n"
                ),
                "cache_control": {"type": "ephemeral"},
            },
        ],
        "user_template": (
            "Analyze the following window from an AV dataset. You will receive {n_images} synced frames across 5 cameras.\n\n"
            "## Frame Index\n{frames_index}\n\n"
            "## Window Info\n{window_info}\n\n"
            "Return JSON with EXACTLY this shape:\n"
            "{{\n"
            '  "moments": [\n'
            "    {{\n"
            '      "t_ns": <int>,\n'
            '      "label": "<short>",\n'
            '      "cameras": {{"shows": ["front_left",...], "misses": ["rear",...]}},\n'
            '      "evidence": [{{"source":"camera","camera":"<role>","t_ns":<int|null>,"snippet":"<what is seen>"}}],\n'
            '      "why_review": "<str>",\n'
            '      "confidence": <float 0..1>,\n'
            '      "inferred_ego_motion": "<str>"\n'
            "    }}\n"
            "  ],\n"
            '  "rationale": "<str>"\n'
            "}}\n"
            "No preamble, no markdown fencing."
        ),
        "schema": VisualMiningReport,
    }


def window_summary_prompt():
    """Cheap pre-filter: 2 sentences per camera, flag if interesting."""
    return {
        "name": "window_summary_v2",
        "system": SYSTEM_AV,
        "cached_blocks": [DOMAIN_CONTEXT_BLOCK],
        "user_template": (
            "Quick triage of this {window_len_s}s window. For each of the 5 cameras, write 1–2 sentences describing what is visible (scene, other road users, hazards). Then decide if the window is interesting enough to merit deep forensic review.\n\n"
            "## Frame Index\n{frames_index}\n\n"
            "Return JSON with EXACTLY this shape:\n"
            "{{\n"
            '  "per_camera": {{\n'
            '    "front_left": "<1-2 sentences>",\n'
            '    "front_right": "<1-2 sentences>",\n'
            '    "right": "<1-2 sentences>",\n'
            '    "rear": "<1-2 sentences>",\n'
            '    "left": "<1-2 sentences>"\n'
            "  }},\n"
            '  "overall": "<one short sentence summary>",\n'
            '  "interesting": <bool — true if unusual road users, close margins, weather/occlusion, or inferred erratic ego motion; false if routine/uneventful>,\n'
            '  "reason": "<why interesting or why not>"\n'
            "}}\n"
            "No preamble, no markdown fencing."
        ),
        "schema": WindowSummary,
    }
