"""v2 prompts for vision-only AV bag analysis (no telemetry available)."""

from pydantic import BaseModel, Field
from typing import Literal


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


def visual_mining_prompt():
    return {
        "name": "visual_mining_v2",
        "system": SYSTEM_AV,
        "cached_blocks": [
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
        "cached_blocks": [],  # keep tiny for cheapness
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
