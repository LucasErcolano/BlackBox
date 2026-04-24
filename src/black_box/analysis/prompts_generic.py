# SPDX-License-Identifier: MIT
"""Platform-agnostic forensic prompts.

Replaces the hardcoded AV / boat prompt split. The system prompt no
longer assumes:
  - vehicle class (car / boat / drone / arm / fixed rig)
  - autonomy (may be human-driven with external robotics payload)
  - sensor count or layout (read from the manifest, not baked in)

Inputs:
  - `Manifest` from `black_box.ingestion.manifest.build_manifest`
  - optional operator free-text hint (`user_prompt`) — the operator's
    hypothesis, NOT ground truth. Passed to the model verbatim and
    flagged as a hypothesis to confirm or reject.

Design notes:
  - Environmental effects (tunnel, shadow, rain, overpass) are NOT
    blacklisted. They are candidate hypotheses to confirm via cross-
    correlation between telemetry anomalies and camera frames in the
    same time window.
  - Bug taxonomy is optional. Applied only when relevant topics exist
    (e.g. no `pid_saturation` label without controller telemetry).
  - Output schema is the same Visual*Mining shape so downstream
    grounding/reporting code keeps working.
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from black_box.ingestion.manifest import Manifest


# -------- schemas (unchanged shape) -----------------------------------------


class CamPresence(BaseModel):
    shows: list[str] = Field(default_factory=list)
    misses: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    source: Literal["camera", "telemetry", "audio", "lidar"] = "camera"
    channel: str  # topic or camera role
    t_ns: int | None = None
    snippet: str


class Moment(BaseModel):
    t_ns: int
    label: str
    cameras: CamPresence
    evidence: list[Evidence]
    why_review: str
    confidence: float
    inferred_ego_motion: str = ""
    hypothesis_status: Literal[
        "supports_operator", "contradicts_operator",
        "independent", "unrelated"
    ] = "independent"


class MiningReport(BaseModel):
    moments: list[Moment]
    rationale: str
    operator_hypothesis_verdict: str = ""


class WindowSummary(BaseModel):
    per_channel: dict[str, str]
    overall: str
    interesting: bool
    reason: str


# -------- stable system prose -----------------------------------------------


SYSTEM_GENERIC = """You are a forensic analyst for robotic and sensor systems. You review recorded session data (ROS bags) that may come from any platform: human-driven vehicles with external robotics payload, autonomous ground vehicles, marine vessels, aerial drones, manipulators, or fixed test rigs.

Do NOT assume the platform type. Do NOT assume autonomy. The capability manifest in the cached context tells you exactly which sensors are present. If a topic is not in the manifest, it does not exist for this session — do not speculate about data you cannot see.

Output JSON only. No preamble, no markdown fencing. Be conservative: an empty moments array is a valid answer when the data is clean. Do not fabricate anomalies."""


# Stable, large, append-only prose. Cached. Kept generic on purpose — specific
# sensor enumeration comes from the manifest block, which is NOT cached since
# it is per-session.
DOMAIN_CONTEXT_GENERIC = """## Forensic rigor rules

- Report only what is supported by the data available in the session manifest. If a hypothesis requires data that is not recorded (e.g. IMU when no IMU topic exists), state this as "requires additional telemetry to confirm" instead of guessing.
- A single-frame artifact or single-sample telemetry spike is not a finding unless it aligns with a multi-frame, multi-sample, or multi-channel pattern.
- Cross-channel reasoning is your strongest tool. If telemetry shows an anomaly at time T, open the camera/lidar view at time T and describe what is visible. If a camera shows a scene change at time T, check whether telemetry confirms a reaction. Always anchor findings to a specific t_ns.
- Operator hypotheses (when provided in the user message) are hypotheses, not truth. Treat them as candidates to confirm or reject using the recorded data. A hypothesis may be partially correct (e.g. environment effect is real, but it does not explain the structural failure). Report both layers when both are present.
- Confidence calibration: 0.9+ requires corroboration across ≥2 channels (e.g. telemetry + camera) or ≥3 consecutive samples. 0.5–0.8 is single-channel multi-sample. Below 0.5 should only be reported when it is the only candidate and why_review explains the weakness.

## Candidate failure modes (apply only when relevant topics are present in the manifest)

1. **pid_saturation** — control output pegged at actuator limit; needs cmd + odometry topics to be supported.
2. **sensor_timeout** — stale or frozen data; a topic whose t_ns stops advancing while others keep publishing.
3. **state_machine_deadlock** — platform not progressing in a state where motion was expected; needs state or cmd topic.
4. **bad_gain_tuning** — overshoot, ringing, under-damped response; needs cmd + odometry.
5. **missing_null_check** — perception/planning failure when expected input is absent; cross-channel signature.
6. **calibration_drift** — same physical object or pose localized inconsistently across sensors; needs ≥2 overlapping sensors.
7. **latency_spike** — event visible in one channel lags another by more than the sync tolerance.
8. **localization_break** — fused-state topic stops or flags invalid while its upstream inputs degrade (e.g. GNSS accuracy drops, RTK invalid, IMU biased); a common structural failure for outdoor platforms.
9. **environmental_degradation** — sensor performance drop correlated with a visible environmental cause (tunnel, overpass, shadow transition, rain, direct sun, EMI source). This is a valid finding, not a non-finding: the correlation between the environment and the degradation must be anchored to a t_ns.

## What is NOT a finding

- Routine scene content: other road users at normal spacing, expected operator inputs, normal traffic signals.
- Single-frame JPEG compression blocks or isolated lens flare on a point light source.
- Water spray from the platform's own motion in wet conditions unless it obscures something relevant.

Environmental transitions (tunnel entry/exit, shadow bands, overpass shadow) are NOT automatically excluded — if they coincide with telemetry degradation, report the correlation.

## Output discipline

- JSON only. No prose outside the JSON. No markdown fencing.
- Evidence entries cite the channel (topic name or camera role from the manifest) and, when possible, a t_ns.
- hypothesis_status: when the user provided an operator hypothesis, every reported moment should indicate whether it supports, contradicts, is independent of, or is unrelated to that hypothesis. If no operator hypothesis was provided, leave it as "independent".
- rationale: one or two sentences explaining the overall call for the window.
- operator_hypothesis_verdict: when a user hypothesis was provided, give a short verdict line (e.g. "partially confirmed: environment effect real at T=... but does not explain structural failure starting at T=0"). Leave empty if no hypothesis was provided.
"""

DOMAIN_CONTEXT_BLOCK = {
    "type": "text",
    "text": DOMAIN_CONTEXT_GENERIC,
    "cache_control": {"type": "ephemeral"},
}


def _manifest_block(manifest: "Manifest | None") -> dict | None:
    if manifest is None:
        return None
    from black_box.ingestion.manifest import manifest_to_prompt_block
    return {
        "type": "text",
        "text": manifest_to_prompt_block(manifest),
        # NOT cached: per-session content, would pollute cache.
    }


def _operator_block(user_prompt: str | None) -> dict | None:
    if not user_prompt:
        return None
    return {
        "type": "text",
        "text": (
            "## Operator hypothesis (free-text, treat as hypothesis not truth)\n\n"
            f"{user_prompt.strip()}\n\n"
            "Confirm or reject using recorded data. A partial match is a valid "
            "verdict. Do not accept or reject wholesale without anchoring to "
            "specific timestamps in the manifest's topics."
        ),
    }


def _assemble_cached_blocks(
    manifest: "Manifest | None",
    user_prompt: str | None,
    extra: list[dict] | None = None,
) -> list[dict]:
    blocks: list[dict] = [DOMAIN_CONTEXT_BLOCK]
    if extra:
        blocks.extend(extra)
    mb = _manifest_block(manifest)
    if mb:
        blocks.append(mb)
    ob = _operator_block(user_prompt)
    if ob:
        blocks.append(ob)
    return blocks


# -------- prompt specs -------------------------------------------------------


def visual_mining_prompt(
    manifest: "Manifest | None" = None,
    user_prompt: str | None = None,
):
    look_for = (
        "## What to look for\n\n"
        "1. **Cross-channel inconsistency**: telemetry anomaly at time T → "
        "what do cameras/lidar show at time T? And vice versa.\n"
        "2. **Structural failures**: a fused or downstream topic fails or "
        "never publishes despite its upstream inputs existing — surface the "
        "upstream data that explains it.\n"
        "3. **Environmental correlation**: visible environment transitions "
        "(tunnel, shadow, rain, glare, EMI source) that coincide with "
        "sensor degradation. This IS a finding when anchored to a t_ns.\n"
        "4. **Near-misses / tight margins**: close passes with other agents "
        "or obstacles, visible across one or more cameras.\n"
        "5. **Inferred platform behavior anomalies**: sudden deceleration, "
        "swerve, stall, or erratic command tracking — anchored in whatever "
        "signal the manifest provides (telemetry if present, visual-only "
        "inference otherwise).\n\n"
        "For each moment reported:\n"
        "- exact t_ns (a real timestamp from the data)\n"
        "- label: short phrase\n"
        "- cameras.shows / cameras.misses: which cameras see it (use the "
        "topic names from the manifest; leave empty if no cameras are "
        "relevant)\n"
        "- evidence: per-channel concrete description (what is SEEN or "
        "MEASURED, not speculated causes)\n"
        "- why_review: why an engineer should look at this manually\n"
        "- confidence: 0.0–1.0\n"
        "- inferred_ego_motion: one short phrase (leave empty if not "
        "inferable from available data)\n"
        "- hypothesis_status: supports_operator | contradicts_operator | "
        "independent | unrelated\n"
    )
    cached = _assemble_cached_blocks(
        manifest, user_prompt,
        extra=[{"type": "text", "text": look_for, "cache_control": {"type": "ephemeral"}}],
    )
    return {
        "name": "visual_mining_generic",
        "system": SYSTEM_GENERIC,
        "cached_blocks": cached,
        "user_template": (
            "Analyze the following window from a recorded session. You will "
            "receive {n_images} synced frames across the session's cameras "
            "(see manifest for topic names and roles).\n\n"
            "## Frame Index\n{frames_index}\n\n"
            "## Window Info\n{window_info}\n\n"
            "Return JSON with EXACTLY this shape:\n"
            "{{\n"
            '  "moments": [\n'
            "    {{\n"
            '      "t_ns": <int>,\n'
            '      "label": "<short>",\n'
            '      "cameras": {{"shows": ["<topic>",...], "misses": ["<topic>",...]}},\n'
            '      "evidence": [{{"source":"camera|telemetry|audio|lidar","channel":"<topic or role>","t_ns":<int|null>,"snippet":"<what is seen or measured>"}}],\n'
            '      "why_review": "<str>",\n'
            '      "confidence": <float 0..1>,\n'
            '      "inferred_ego_motion": "<str>",\n'
            '      "hypothesis_status": "supports_operator|contradicts_operator|independent|unrelated"\n'
            "    }}\n"
            "  ],\n"
            '  "rationale": "<str>",\n'
            '  "operator_hypothesis_verdict": "<str, empty if no operator hypothesis was provided>"\n'
            "}}\n"
            "No preamble, no markdown fencing."
        ),
        "schema": MiningReport,
    }


def window_summary_prompt(
    manifest: "Manifest | None" = None,
    user_prompt: str | None = None,
):
    cached = _assemble_cached_blocks(manifest, user_prompt)
    return {
        "name": "window_summary_generic",
        "system": SYSTEM_GENERIC,
        "cached_blocks": cached,
        "user_template": (
            "Quick triage of this {window_len_s}s window. For each camera "
            "topic listed in the manifest, write 1–2 sentences describing "
            "what is visible. Then decide if the window merits deep "
            "forensic review.\n\n"
            "## Frame Index\n{frames_index}\n\n"
            "Return JSON with EXACTLY this shape:\n"
            "{{\n"
            '  "per_channel": {{"<camera topic>": "<1-2 sentences>", ...}},\n'
            '  "overall": "<one short sentence>",\n'
            '  "interesting": <bool>,\n'
            '  "reason": "<why interesting or why not>"\n'
            "}}\n"
            "No preamble, no markdown fencing."
        ),
        "schema": WindowSummary,
    }
