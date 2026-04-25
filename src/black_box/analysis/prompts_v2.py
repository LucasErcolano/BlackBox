# SPDX-License-Identifier: MIT
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

## Sub-classification per taxonomy entry

Each top-level bug class breaks down further. Use the parent label in `evidence.snippet`; the sub-class belongs in `why_review` for reviewer triage.

### pid_saturation sub-classes
- `pid_saturation.steering_windup` — sustained steering output at limit while heading error continues to grow; visually, monotonic horizon roll without correction.
- `pid_saturation.throttle_windup` — throttle pegged with no acceleration response visible; scene compression flat across many frames where motion expected.
- `pid_saturation.brake_windup` — brake at limit with continued forward motion; scene compression continues despite expected stop cue (red light, lead-vehicle stop).

### sensor_timeout sub-classes
- `sensor_timeout.frozen_frame` — byte-identical frames across ≥3 timestamps from the same camera.
- `sensor_timeout.partial_dropout` — one camera frozen, neighbors live; cross-camera disagreement is the tell.
- `sensor_timeout.cascading_dropout` — multiple sensors freeze in sequence; usually a topic-bridge or DDS issue rather than per-sensor.

### state_machine_deadlock sub-classes
- `state_machine_deadlock.intersection_hold` — vehicle stopped at an intersection past the expected go-cue (light green ≥2s, no leading vehicle).
- `state_machine_deadlock.lane_change_abort` — partial lane-change attitude held without completion or rollback.
- `state_machine_deadlock.startup_hang` — engine on, no commanded motion, no obstruction in any camera.

### bad_gain_tuning sub-classes
- `bad_gain_tuning.steering_oscillation` — horizon yaw oscillates around a setpoint with decaying or undamped envelope.
- `bad_gain_tuning.speed_hunting` — scene compression alternates between approach and depart on a constant-speed setpoint.
- `bad_gain_tuning.lateral_overshoot` — lane-change attitude exceeds target lane center before correction.

### missing_null_check sub-classes
- `missing_null_check.absent_perception_input` — hazard visible in two cameras, no behavioral response (no scene compression / no horizon roll).
- `missing_null_check.absent_localization` — vehicle behavior consistent with not knowing its lane (drifts or holds against curb).
- `missing_null_check.absent_route` — vehicle stops at a routine waypoint with no clear blocker.

### calibration_drift sub-classes
- `calibration_drift.extrinsic` — same object jumps in image-space across overlap boundaries.
- `calibration_drift.intrinsic` — straight-line features bow toward image edges in one camera but not its peer.
- `calibration_drift.temporal` — overlap object lags by ≥2 frames across cameras with shared trigger.

### latency_spike sub-classes
- `latency_spike.network` — multi-topic synchronized lag across all cameras for a bounded interval.
- `latency_spike.bus_contention` — single-camera lag while others remain on schedule, repeating every N frames.
- `latency_spike.disk_io_pause` — burst-bounded freeze followed by catch-up frames clustered close in time.

## Canonical exemplars (positive + negative)

### Positive — should be reported

EX-P1 — calibration_drift.extrinsic. cam5 shows a parked van centered at image x≈1100 px at t_ns=T. cam6, whose left edge overlaps cam5's right edge, shows the same van centered at x≈40 px at t_ns=T+5ms. Geometry says these positions are inconsistent by ~0.4 m at 8 m range. confidence 0.85 (two cameras, multi-frame stable). why_review: extrinsic recalibration before the next mission.

EX-P2 — sensor_timeout.frozen_frame. cam3 produces visually identical frames across t_ns=T, T+33ms, T+66ms, T+100ms while cam1, cam5, cam6, cam4 all show smooth scene change. Pixels match within JPEG noise floor on the static-detail subregion. confidence 0.95. why_review: investigate cam3 driver buffer; correlate with `/diagnostics`.

EX-P3 — state_machine_deadlock.intersection_hold. All 5 cameras static for 4.2 s. cam1+cam5 show a green left-turn arrow throughout. No leading vehicle. confidence 0.7 (visual only, no behavior_planner state). why_review: requires telemetry to confirm; flag for replay.

EX-P4 — bad_gain_tuning.steering_oscillation. Horizon roll in cam1 swings ±2° at ~1.4 Hz across 6 cycles with no decay while ego is on a straight road (lane markings parallel to motion in cam4). confidence 0.8.

### Negative — must NOT be reported

EX-N1 — Single sun-glare frame in cam5 with no downstream behavior change. Reason: lens flare on bright pointwise light without hazard interference is excluded.

EX-N2 — Pedestrian on sidewalk walking parallel to ego heading. Reason: routine scene content.

EX-N3 — One JPEG compression block in cam6 lasting one frame. Reason: single-frame artifact without multi-frame or multi-camera pattern.

EX-N4 — Tunnel entry causing 0.5 s exposure dip on all cameras with vehicle continuing on path normally. Reason: environmental transition without coincident anomaly downstream.

EX-N5 — Water spray from ego tires visible in cam4. Reason: ego-generated, no hazard occlusion.

## Reviewer-priority hints

When multiple moments fit a single window, sort the response array by likely operator value:
1. Anything labelled missing_null_check sub-classes — these correlate with safety-critical failures.
2. calibration_drift.extrinsic — easy to verify offline, common root cause for downstream perception bugs.
3. sensor_timeout.cascading_dropout — points to platform-level health rather than a per-sensor flake.
4. state_machine_deadlock.* — high operator-experience impact.
5. bad_gain_tuning.* and pid_saturation.* — usually known-knowns, lower triage urgency.
6. latency_spike.* — useful for postmortem timing reconstruction.

## Glossary — extended

- **specular flare**: streak of light along a single axis caused by lens internal reflection; distinguish from sun glare which is a localized blob.
- **rolling-shutter skew**: vertical edges appear slanted on fast lateral motion; not a finding by itself.
- **chroma noise floor**: low-light grain primarily in chroma channels; separates real scene content from sensor noise when judging "frozen frame" candidates.
- **edge ringing**: halo around high-contrast edges from sharpening or compression; not a hazard, do not report.
- **ego-motion blur**: directional blur correlated with inferred ego speed; expected on long exposures.
- **handover marker**: brief loss of feature continuity at FOV overlap boundary; expected and not a finding unless persistent.
- **scene depth gradient**: foreground-to-background pixel-size change rate; useful proxy for inferred speed.

## Operator workflow context

The forensic copilot output feeds three downstream consumers:
1. Replay UI — picks `t_ns` to seek to. Therefore every reported moment MUST carry a real frame timestamp from the input list, never an interpolated value.
2. PDF report — renders `label`, `why_review`, and `evidence` snippets. Keep them human-readable; no JSON-inside-strings, no shell escapes.
3. Memory L2 — accumulates patterns across runs. Stable taxonomy labels (`pid_saturation`, `calibration_drift`, etc.) drive aggregation. Sub-classes are advisory in `why_review` and should NOT be invented outside the list above.

## Output discipline — extended

- Confidence floor 0.4 for any reported moment unless it is the only candidate in an otherwise unremarkable window.
- Use `inferred_ego_motion` even on still scenes — write "stationary" rather than leaving it empty.
- Empty `cameras.misses` is fine when only one camera could plausibly see the event.
- For multi-camera evidence, list per-camera `evidence` entries in geometric order: cam1, cam5, cam6, cam4, cam3 (front_left → front_right → right → rear → left). Reviewers scan in that order.
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
