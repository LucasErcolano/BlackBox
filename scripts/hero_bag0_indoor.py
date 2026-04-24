# SPDX-License-Identifier: MIT
"""Hero deep-dive: bag 0 end window, cross-camera indoor-scene anomaly.

Focus: rear/left/right cameras, t=3505-3530s from bag start.
Prior automated flag (conf 0.9): rear + left streams show indoor workshop/kitchen
while front_left/front_right/right show outdoor parking lot at same timestamps.

Extracts hires frames fresh from bag 0, then runs focused Opus 4.7 analysis.
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
from extract_hires import run as extract_hires_run  # noqa: E402


BAG = Path("/mnt/hdd/0_cam-lidar.bag")
HIRES_DIR = Path("/home/hz/blackbox_cache/frames/bag_0_v2_hires_indoor")
OUT_DIR = Path("/home/hz/Desktop/BlackBox/data/session/analyses/hero_bag0_indoor_scene")
CACHE_OUT = Path("/home/hz/blackbox_cache/analyses/hero_bag0_indoor_scene")

# cam3=left, cam4=rear, cam6=right
TOPICS = [
    ("/cam4/image_raw/compressed", "rear"),
    ("/cam3/image_raw/compressed", "left"),
    ("/cam6/image_raw/compressed", "right"),
]
WIN_START_S = 3505.0
WIN_LEN_S = 25.0
N_PER_CAM = 6  # 3*6 = 18 frames hires


class HeroReport(BaseModel):
    anomaly_class: str
    confidence: float
    what_is_seen: str
    affected_cameras: list[str]
    onset_t_ns: int
    recovery_t_ns: int | None = None
    duration_s_est: float
    cross_view_consistency: str
    spatial_reasoning: str
    root_cause_hypothesis: str
    data_quality_recommendation: str
    trim_t_start_ns: int | None = None
    trim_t_stop_ns: int | None = None
    safety_impact: str


SYSTEM_HERO = """You are a forensic analyst for autonomous vehicles. Deep-dive ONE specific moment with cross-camera spatial+temporal reasoning. Be precise about geometry: if an interior scene (walls, furniture, indoor lighting) appears on a camera whose role is outdoor-mounted, reason about whether this is plausible (e.g., vehicle inside a garage) or an integrity failure (topic mis-mapping, stale buffer, wrong camera assignment). Respond JSON only."""


def extract():
    if HIRES_DIR.exists() and any(HIRES_DIR.glob("*.png")):
        print(f"[extract] reusing {HIRES_DIR}")
        return
    print(f"[extract] running hires extract from {BAG} -> {HIRES_DIR}")
    topics_only = [t for t, _ in TOPICS]
    extract_hires_run(BAG, HIRES_DIR, topics_only, WIN_START_S, WIN_LEN_S, N_PER_CAM)


def run():
    extract()
    manifest = json.loads((HIRES_DIR / "hires_manifest.json").read_text())

    images: list[Image.Image] = []
    image_desc: list[str] = []
    for topic, role in TOPICS:
        saved = manifest["saved"].get(topic, [])
        for entry in sorted(saved, key=lambda e: e["t_ns"]):
            p = HIRES_DIR / entry["file"]
            if p.exists():
                images.append(Image.open(p).convert("RGB"))
                image_desc.append(f"img#{len(images)-1}: {role} t_ns={entry['t_ns']}")

    role_counts = {role: sum(1 for d in image_desc if f" {role} " in d) for _, role in TOPICS}
    print(f"[hero] {len(images)} hires frames loaded: {role_counts}")

    prompt_spec = {
        "system": SYSTEM_HERO,
        "cached_blocks": [],
        "user_template": (
            "Deep-dive this suspicious moment. Bag 0 end window, 3505-3530 s from bag start.\n"
            "You will receive {n} hi-res frames in role groups: {n_rear} rear, then {n_left} left, then {n_right} right, each group chronological.\n\n"
            "Prior automated analysis flagged TWO related findings (conf 0.9 each):\n"
            "  (a) rear-labeled frames contain an indoor lab/workshop (whiteboards, projector, shelving) while front cameras at synchronized timestamps show outdoor parking lot;\n"
            "  (b) left-labeled frames contain an indoor kitchen/doorway (red chair, broom, wall outlet) at the same synchronized timestamps.\n"
            "Right-labeled frames are expected to be consistently outdoor — use them as the spatial ground-truth anchor.\n\n"
            "## Frame Index\n{idx}\n\n"
            "Produce a structured forensic report with these fields EXACTLY:\n"
            '- anomaly_class: short taxonomy key (e.g. "topic_misrouting", "camera_role_swap", "stale_buffer", "wrong_camera_mapping", "data_integrity_failure").\n'
            "- confidence: 0-1.\n"
            "- what_is_seen: dense 4-6 sentence description across the 3 camera groups. Be explicit about which frames are indoor vs outdoor and at what approximate timestamps.\n"
            "- affected_cameras: subset of [rear, left, right].\n"
            "- onset_t_ns: earliest frame timestamp where anomaly is clearly visible.\n"
            "- recovery_t_ns: latest timestamp or null if persists through window end.\n"
            "- duration_s_est: seconds.\n"
            "- cross_view_consistency: does the right camera (your outdoor anchor) corroborate outdoor context throughout? Call out any mixed rear/left frames (if some rear frames ARE outdoor-looking that's important).\n"
            "- spatial_reasoning: can the indoor scenes be explained by ego vehicle being physically inside a building (garage, loading bay) with some cameras seeing interior walls? Or is the geometry impossible (e.g., rear says workshop while right says open lot 3 m away)? Reason explicitly.\n"
            "- root_cause_hypothesis: topic mis-mapping during recording, multiplexed stream with wrong demuxing, laptop/webcam accidentally included in recording, stale buffer re-publication, or other.\n"
            "- data_quality_recommendation: concrete action (trim, relabel, discard window, discard bag, or gate before training).\n"
            "- trim_t_start_ns / trim_t_stop_ns: exact timestamps bounding the segment that should be excluded from any downstream training or evaluation. Integers (ns) or null.\n"
            "- safety_impact: brief.\n\n"
            "JSON ONLY, no wrappers, no markdown:\n"
            "{{\n"
            '  "anomaly_class": "<str>", "confidence": <float>,\n'
            '  "what_is_seen": "<str>",\n'
            '  "affected_cameras": ["<role>", ...],\n'
            '  "onset_t_ns": <int>, "recovery_t_ns": <int|null>, "duration_s_est": <float>,\n'
            '  "cross_view_consistency": "<str>",\n'
            '  "spatial_reasoning": "<str>",\n'
            '  "root_cause_hypothesis": "<str>",\n'
            '  "data_quality_recommendation": "<str>",\n'
            '  "trim_t_start_ns": <int|null>, "trim_t_stop_ns": <int|null>,\n'
            '  "safety_impact": "<str>"\n'
            "}}"
        ),
        "schema": HeroReport,
        "name": "hero_bag0_indoor",
    }

    user_fields = {
        "n": len(images),
        "n_rear": role_counts["rear"],
        "n_left": role_counts["left"],
        "n_right": role_counts["right"],
        "idx": "\n".join(image_desc),
    }

    print("[hero] sending to Claude Opus 4.7 (hires)...", flush=True)
    t0 = time.time()
    report, cost = client_call(prompt_spec, images, user_fields)
    wall = time.time() - t0
    print(f"[hero] done wall={wall:.1f}s usd=${cost.usd_cost:.4f}")

    if cost.usd_cost > 1.0:
        print(f"[WARN] budget exceeded: ${cost.usd_cost:.4f}")

    for d in (OUT_DIR, CACHE_OUT):
        d.mkdir(parents=True, exist_ok=True)
        (d / "hero_report.json").write_text(report.model_dump_json(indent=2))
        (d / "cost.json").write_text(json.dumps({
            "usd": cost.usd_cost,
            "wall_s": wall,
            "tokens": {
                "cached": cost.cached_input_tokens,
                "uncached": cost.uncached_input_tokens,
                "output": cost.output_tokens,
            },
            "n_frames": len(images),
            "cameras": list(role_counts.keys()),
        }, indent=2))

    print("\n=== HERO REPORT (bag 0 indoor) ===")
    print(report.model_dump_json(indent=2))


def client_call(prompt_spec, images, user_fields):
    client = ClaudeClient()
    return client.analyze(
        prompt_spec=prompt_spec,
        images=images,
        user_fields=user_fields,
        resolution="hires",
        max_tokens=2500,
    )


if __name__ == "__main__":
    run()
