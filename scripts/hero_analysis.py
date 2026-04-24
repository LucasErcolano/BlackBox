# SPDX-License-Identifier: MIT
"""Focused hero analysis for demo: deepest dive into ONE moment using existing frames.

Bag 1 start-window front_left+front_right overexposure (conf 0.95).
Uses existing 800×600 frames; sends all 16 (8 per cam) for cross-camera temporal analysis.
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

from PIL import Image
from dotenv import load_dotenv
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from black_box.analysis import ClaudeClient  # noqa: E402


FRAMES_DIR = Path("/home/hz/blackbox_cache/frames/bag_1_v2")


class HeroReport(BaseModel):
    anomaly_class: str  # e.g., "sensor_overexposure" or bug_taxonomy key
    confidence: float
    what_is_seen: str  # dense description
    affected_cameras: list[str]
    onset_t_ns: int
    recovery_t_ns: int | None = None
    duration_s_est: float
    cross_view_consistency: str  # does rear/side also show it?
    root_cause_hypothesis: str
    suggested_patch: str
    safety_impact: str


SYSTEM_HERO = """You are a forensic analyst for autonomous vehicles. Deep-dive one specific moment with cross-camera temporal analysis. Be precise about what you see. Respond JSON only."""


def run():
    client = ClaudeClient()

    # Load bag1 v2 start window — front_left + front_right frames
    manifest = json.loads((FRAMES_DIR / "windows_manifest.json").read_text())
    start_win = manifest["windows"]["start"]

    images = []
    image_desc = []
    for topic in ["/cam1/image_raw/compressed", "/cam5/image_raw/compressed"]:
        role = {"/cam1/image_raw/compressed": "front_left", "/cam5/image_raw/compressed": "front_right"}[topic]
        for i, f in enumerate(start_win["saved"].get(topic, [])):
            img_path = FRAMES_DIR / f["file_big"]
            if img_path.exists():
                images.append(Image.open(img_path).convert("RGB"))
                image_desc.append(f"img#{len(images)-1}: {role} t_ns={f['t_ns']}")

    prompt_spec = {
        "system": SYSTEM_HERO,
        "cached_blocks": [],
        "user_template": (
            "Deep-dive this suspicious moment. Bag 1 start window, 15-35 s from bag start.\n"
            "You will receive {n} frames interleaved: {n_fl} front_left frames first, then {n_fr} front_right frames, in chronological order.\n\n"
            "Prior automated analysis flagged: 'Severe overexposure on front_left and front_right cameras' (confidence 0.95).\n\n"
            "## Frame Index\n{idx}\n\n"
            "Produce a structured forensic report. Fields:\n"
            '- anomaly_class: best-matching taxonomy key (e.g. "sensor_overexposure", "exposure_saturation", "white_balance_failure", or another short key).\n'
            "- confidence: 0-1.\n"
            "- what_is_seen: dense 3-5 sentence description of exactly what is visible across the sequence.\n"
            "- affected_cameras: subset of [front_left, front_right, left, right, rear].\n"
            "- onset_t_ns / recovery_t_ns / duration_s_est: pick from frame timestamps.\n"
            "- cross_view_consistency: does the overexposure also appear on left/right/rear cams (recall we are NOT sending those here — state unknown or inferable only from prior overall scene brightness cues if any).\n"
            "- root_cause_hypothesis: what could cause this (auto-exposure failure, occluded lens, direct sun, sensor defect, firmware glitch, startup race).\n"
            "- suggested_patch: short technical fix scoped to exposure subsystem.\n"
            "- safety_impact: brief.\n\n"
            "JSON shape EXACTLY (no wrappers):\n"
            "{{\n"
            '  "anomaly_class": "<str>", "confidence": <float>,\n'
            '  "what_is_seen": "<str>",\n'
            '  "affected_cameras": ["<role>", ...],\n'
            '  "onset_t_ns": <int>, "recovery_t_ns": <int|null>, "duration_s_est": <float>,\n'
            '  "cross_view_consistency": "<str>",\n'
            '  "root_cause_hypothesis": "<str>",\n'
            '  "suggested_patch": "<str>",\n'
            '  "safety_impact": "<str>"\n'
            "}}\n"
            "No preamble, no markdown."
        ),
        "schema": HeroReport,
        "name": "hero_deep_dive",
    }

    n_fl = sum(1 for d in image_desc if "front_left" in d)
    n_fr = len(image_desc) - n_fl
    user_fields = {
        "n": len(images),
        "n_fl": n_fl,
        "n_fr": n_fr,
        "idx": "\n".join(image_desc),
    }

    print(f"[hero] sending {len(images)} images ({n_fl} front_left + {n_fr} front_right) to Claude Opus 4.7...", flush=True)
    t0 = time.time()
    report, cost = client.analyze(
        prompt_spec=prompt_spec,
        images=images,
        user_fields=user_fields,
        resolution="hires",  # up to 1920 — but source is 800, no upscale
        max_tokens=2000,
    )
    wall = time.time() - t0
    print(f"[hero] done in {wall:.1f}s cost=${cost.usd_cost:.4f}", flush=True)

    out = Path("/home/hz/blackbox_cache/analyses/hero_bag1_overexposure")
    out.mkdir(parents=True, exist_ok=True)
    (out / "hero_report.json").write_text(report.model_dump_json(indent=2))
    (out / "cost.json").write_text(json.dumps({
        "usd": cost.usd_cost,
        "wall_s": wall,
        "tokens": {
            "cached": cost.cached_input_tokens,
            "uncached": cost.uncached_input_tokens,
            "output": cost.output_tokens,
        },
    }, indent=2))

    print("\n=== HERO REPORT ===")
    print(report.model_dump_json(indent=2))
    print(f"\nTotal spent across session: ${client.total_spent_usd():.4f}")


if __name__ == "__main__":
    run()
