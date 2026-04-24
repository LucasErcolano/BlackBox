# SPDX-License-Identifier: MIT
"""Run scenario mining over an extracted bag window.

Reads frames_manifest.json + PNG thumbnails from cache, builds Claude prompt,
sends 5 cams × N frames, saves response JSON + PDF report.
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

from PIL import Image
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from black_box.analysis import ClaudeClient, scenario_mining_prompt  # noqa: E402
from black_box.reporting import build_report  # noqa: E402


ROLE = {
    "/cam1/image_raw/compressed": "front_left",
    "/cam5/image_raw/compressed": "front_right",
    "/cam6/image_raw/compressed": "right",
    "/cam4/image_raw/compressed": "rear",
    "/cam3/image_raw/compressed": "left",
}


def build_frames_description(manifest: dict) -> str:
    lines = ["5 cameras, sampled evenly over the window. Images provided in the following order:"]
    order_idx = 0
    for topic in ["/cam1/image_raw/compressed", "/cam5/image_raw/compressed", "/cam6/image_raw/compressed", "/cam4/image_raw/compressed", "/cam3/image_raw/compressed"]:
        frames = manifest["saved"].get(topic, [])
        role = ROLE[topic]
        lines.append(f"  {role} ({topic}): {len(frames)} frames starting at image index {order_idx}:")
        for i, f in enumerate(frames):
            lines.append(f"    img#{order_idx}: t_ns={f['t_ns']}")
            order_idx += 1
    lines.append(f"Window: {manifest['window_start_s']}s → {manifest['window_start_s']+manifest['window_len_s']}s from bag start.")
    return "\n".join(lines)


def load_images_in_order(frames_dir: Path, manifest: dict) -> list[Image.Image]:
    images = []
    for topic in ["/cam1/image_raw/compressed", "/cam5/image_raw/compressed", "/cam6/image_raw/compressed", "/cam4/image_raw/compressed", "/cam3/image_raw/compressed"]:
        for f in manifest["saved"].get(topic, []):
            images.append(Image.open(frames_dir / f["file"]).convert("RGB"))
    return images


def run(bag_id: str, frames_dir: Path, out_dir: Path, bag_summary: str) -> dict:
    manifest = json.loads((frames_dir / "frames_manifest.json").read_text())
    images = load_images_in_order(frames_dir, manifest)
    synced_desc = build_frames_description(manifest)

    spec = scenario_mining_prompt()
    user_fields = {
        "bag_summary": bag_summary,
        "synced_frames_description": synced_desc,
    }

    print(f"[analyze] {bag_id}: {len(images)} images → Claude Opus 4.7 (scenario_mining)", flush=True)
    t0 = time.time()
    client = ClaudeClient()
    report, cost = client.analyze(
        prompt_spec=spec,
        images=images,
        user_fields=user_fields,
        resolution="thumb",
        max_tokens=4000,
    )
    wall = time.time() - t0
    print(f"[analyze] done in {wall:.1f}s  cost=${cost.usd_cost:.4f}  tokens cached/uncached/out={cost.cached_input_tokens}/{cost.uncached_input_tokens}/{cost.output_tokens}", flush=True)

    # Save raw response + parsed
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "mining_analysis_v1.json").write_text(report.model_dump_json(indent=2))
    (out_dir / "prompt_used.txt").write_text(f"SYSTEM:\n{spec['system']}\n\nUSER:\n{spec['user_template'].format(**user_fields)}")
    (out_dir / "cost.json").write_text(json.dumps({
        "cached_input_tokens": cost.cached_input_tokens,
        "uncached_input_tokens": cost.uncached_input_tokens,
        "cache_creation_tokens": cost.cache_creation_tokens,
        "output_tokens": cost.output_tokens,
        "usd_cost": cost.usd_cost,
        "wall_s": wall,
    }, indent=2))

    # Build a PDF report (shaped for post-mortem template; scenario mining moments become timeline)
    timeline = [{"t_ns": m.t_ns, "label": m.label, "cross_view": any(e.source == "camera" for e in m.evidence)} for m in report.moments]
    # Fabricate a single top-level "hypothesis" summarizing what was found
    if report.moments:
        synth_hyp = {
            "bug_class": "other",
            "confidence": 0.5,
            "summary": f"{len(report.moments)} moments of interest flagged during scenario mining.",
            "evidence": [e.model_dump() for m in report.moments for e in m.evidence][:10],
            "patch_hint": report.rationale,
        }
    else:
        synth_hyp = {
            "bug_class": "other",
            "confidence": 0.0,
            "summary": "No anomalies detected during scenario mining.",
            "evidence": [],
            "patch_hint": report.rationale,
        }
    pdf_dict = {
        "timeline": timeline,
        "hypotheses": [synth_hyp],
        "root_cause_idx": 0,
        "patch_proposal": report.rationale or "(no anomalies — nominal run)",
    }

    # Load a preview image for PDF
    preview_path = frames_dir / "preview_5up.png"
    plots = []
    if preview_path.exists():
        plots.append(Image.open(preview_path).convert("RGB"))

    out_pdf = out_dir / "mining_report_v1.pdf"
    build_report(
        report_json=pdf_dict,
        artifacts={"frames": [], "plots": plots, "code_diff": ""},
        out_pdf=out_pdf,
        case_meta={
            "case_key": bag_id,
            "bag_path": bag_summary.split("\n")[0] if bag_summary else "",
            "duration_s": manifest["window_len_s"],
            "mode": "scenario_mining",
        },
    )
    print(f"[analyze] PDF: {out_pdf} ({out_pdf.stat().st_size} bytes)", flush=True)
    return {
        "bag_id": bag_id,
        "n_moments": len(report.moments),
        "cost_usd": cost.usd_cost,
        "pdf": str(out_pdf),
        "wall_s": wall,
    }


if __name__ == "__main__":
    bag_id = sys.argv[1]
    frames_dir = Path(sys.argv[2])
    out_dir = Path(sys.argv[3])
    bag_summary = sys.argv[4] if len(sys.argv) > 4 else f"Bag {bag_id}"
    res = run(bag_id, frames_dir, out_dir, bag_summary)
    print(json.dumps(res, indent=2))
