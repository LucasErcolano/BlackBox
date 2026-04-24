# SPDX-License-Identifier: MIT
"""v2 analysis: per-window cheap summary → filter → deep visual mining.

Two-stage:
1. window_summary_prompt at 400x300 → ~$0.15-0.25 per window
2. visual_mining_prompt at 800x600 only on interesting windows → ~$0.50-1 per window

Prompts are now platform-agnostic (prompts_generic). The 5-camera topic
list is supplied as a Manifest so the model sees exactly which channels
exist for this session instead of a hardcoded AV layout. An optional
operator hypothesis (`--prompt "..."` or `BB_USER_PROMPT=...`) is passed
through verbatim as a hypothesis to confirm or reject.
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

from PIL import Image
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from black_box.analysis import ClaudeClient  # noqa: E402
from black_box.analysis.prompts_generic import (  # noqa: E402
    visual_mining_prompt,
    window_summary_prompt,
)
from black_box.ingestion.manifest import Manifest, TopicInfo  # noqa: E402
from black_box.reporting import build_report  # noqa: E402


CAM_ORDER = [
    "/cam1/image_raw/compressed",
    "/cam5/image_raw/compressed",
    "/cam6/image_raw/compressed",
    "/cam4/image_raw/compressed",
    "/cam3/image_raw/compressed",
]
ROLE = {
    "/cam1/image_raw/compressed": "front_left",
    "/cam5/image_raw/compressed": "front_right",
    "/cam6/image_raw/compressed": "right",
    "/cam4/image_raw/compressed": "rear",
    "/cam3/image_raw/compressed": "left",
}


def build_frames_index(saved: dict, use_small: bool) -> tuple[list[str], str]:
    """Return (file_paths_in_order, index_text)."""
    lines = []
    files = []
    order_idx = 0
    for topic in CAM_ORDER:
        role = ROLE[topic]
        frames = saved.get(topic, [])
        lines.append(f"  {role} ({topic}): {len(frames)} frames starting at img#{order_idx}:")
        for f in frames:
            lines.append(f"    img#{order_idx}: t_ns={f['t_ns']}")
            files.append(f["file_small"] if use_small else f["file_big"])
            order_idx += 1
    return files, "\n".join(lines)


def _build_adhoc_manifest(bag_path: str, duration_s: float) -> Manifest:
    """Synthesize a Manifest from the pre-extracted camera topic list.

    The script receives already-sampled frames (no bag re-scan), so we
    build a lightweight manifest with just the camera channels that were
    extracted. Downstream topics (telemetry/gnss/odom) would normally
    come from a full scan via `build_manifest`; for this script the
    cameras-only view is sufficient to ground the prompt.
    """
    cams = [TopicInfo(topic=t, msgtype="sensor_msgs/CompressedImage", count=0, kind="camera")
            for t in CAM_ORDER]
    return Manifest(
        root=Path(bag_path).parent if bag_path else Path("."),
        session_key=None,
        bags=[Path(bag_path)] if bag_path else [],
        duration_s=duration_s,
        t_start_ns=None,
        t_end_ns=None,
        cameras=cams,
    )


def run_summary(client: ClaudeClient, frames_dir: Path, win_name: str, win_meta: dict,
                manifest: Manifest, user_prompt: str | None) -> tuple[dict, float]:
    spec = window_summary_prompt(manifest=manifest, user_prompt=user_prompt)
    files, idx_text = build_frames_index(win_meta["saved"], use_small=True)
    # Subsample heavily for summary: 4 frames per cam (every 5th) to keep tokens low
    sampled_files = []
    sampled_lines = []
    order = 0
    for topic in CAM_ORDER:
        role = ROLE[topic]
        frames = win_meta["saved"].get(topic, [])
        step = max(1, len(frames) // 4)
        chosen = frames[::step][:4]
        sampled_lines.append(f"  {role}: {len(chosen)} frames at img#{order}:")
        for f in chosen:
            sampled_lines.append(f"    img#{order}: t_ns={f['t_ns']}")
            sampled_files.append(f["file_small"])
            order += 1
    images = [Image.open(frames_dir / p).convert("RGB") for p in sampled_files]
    user_fields = {
        "window_len_s": (win_meta["stop_ns"] - win_meta["start_ns"]) / 1e9,
        "frames_index": "\n".join(sampled_lines),
    }
    print(f"[summary] {win_name}: {len(images)} imgs @ 400x300 → Claude...", flush=True)
    result, cost = client.analyze(
        prompt_spec=spec,
        images=images,
        user_fields=user_fields,
        resolution="thumb",  # client will resize to 800; but source is 400x300
        max_tokens=800,
    )
    return result.model_dump(), cost.usd_cost


def run_deep(client: ClaudeClient, frames_dir: Path, win_name: str, win_meta: dict,
             manifest: Manifest, user_prompt: str | None) -> tuple[dict, float]:
    spec = visual_mining_prompt(manifest=manifest, user_prompt=user_prompt)
    files, idx_text = build_frames_index(win_meta["saved"], use_small=False)
    images = [Image.open(frames_dir / p).convert("RGB") for p in files]
    user_fields = {
        "n_images": len(images),
        "frames_index": idx_text,
        "window_info": (
            f"window={win_name}, start_ns={win_meta['start_ns']}, stop_ns={win_meta['stop_ns']}, "
            f"duration_s={(win_meta['stop_ns']-win_meta['start_ns'])/1e9:.1f}"
        ),
    }
    print(f"[deep] {win_name}: {len(images)} imgs @ 800x600 → Claude...", flush=True)
    result, cost = client.analyze(
        prompt_spec=spec,
        images=images,
        user_fields=user_fields,
        resolution="thumb",
        max_tokens=3000,
    )
    return result.model_dump(), cost.usd_cost


def run(bag_id: str, frames_dir: Path, out_dir: Path, force_deep: bool = False,
        user_prompt: str | None = None):
    t0 = time.time()
    out_dir.mkdir(parents=True, exist_ok=True)
    wm = json.loads((frames_dir / "windows_manifest.json").read_text())
    client = ClaudeClient()
    manifest = _build_adhoc_manifest(wm.get("bag", ""), float(wm.get("duration_s", 0.0)))

    total_cost = 0.0
    per_window = {}
    all_moments = []

    for win_name, win_meta in wm["windows"].items():
        # Stage 1: cheap summary
        try:
            summary, c1 = run_summary(client, frames_dir, win_name, win_meta, manifest, user_prompt)
        except Exception as e:
            print(f"[summary] {win_name} FAILED: {e}", flush=True)
            summary = {"per_channel": {}, "overall": f"summary failed: {e}", "interesting": True, "reason": "fallback to deep"}
            c1 = 0.0
        total_cost += c1
        print(f"[summary] {win_name}: interesting={summary.get('interesting')}  cost=${c1:.4f}  reason={summary.get('reason', '')[:100]}", flush=True)
        per_window[win_name] = {"summary": summary, "summary_cost": c1}

        # Stage 2: deep if flagged
        do_deep = bool(summary.get("interesting")) or force_deep
        if do_deep:
            try:
                deep, c2 = run_deep(client, frames_dir, win_name, win_meta, manifest, user_prompt)
            except Exception as e:
                print(f"[deep] {win_name} FAILED: {e}", flush=True)
                deep = {"moments": [], "rationale": f"deep failed: {e}"}
                c2 = 0.0
            total_cost += c2
            per_window[win_name]["deep"] = deep
            per_window[win_name]["deep_cost"] = c2
            for m in deep.get("moments", []):
                m2 = dict(m)
                m2["window"] = win_name
                all_moments.append(m2)
            print(f"[deep] {win_name}: moments={len(deep.get('moments', []))}  cost=${c2:.4f}", flush=True)
        else:
            per_window[win_name]["deep"] = None
            per_window[win_name]["deep_cost"] = 0.0

    wall = time.time() - t0
    out = {
        "bag_id": bag_id,
        "total_cost_usd": total_cost,
        "wall_s": wall,
        "windows": per_window,
        "all_moments": all_moments,
    }
    (out_dir / "mining_v2.json").write_text(json.dumps(out, indent=2, default=str))
    (out_dir / "prompt_used_summary.txt").write_text(
        json.dumps(window_summary_prompt(manifest=manifest, user_prompt=user_prompt), default=str, indent=2)[:5000]
    )
    (out_dir / "prompt_used_deep.txt").write_text(
        json.dumps(visual_mining_prompt(manifest=manifest, user_prompt=user_prompt), default=str, indent=2)[:5000]
    )

    # Build PDF
    timeline = []
    for m in all_moments:
        timeline.append({
            "t_ns": int(m["t_ns"]),
            "label": f"[{m['window']}] {m['label']}",
            "cross_view": len(m.get("cameras", {}).get("shows", [])) >= 2,
        })
    if all_moments:
        # Pick highest-confidence moment as the synth hypothesis
        top = max(all_moments, key=lambda m: m.get("confidence", 0.0))
        hyps = [{
            "bug_class": "other",
            "confidence": float(top.get("confidence", 0.5)),
            "summary": f"{len(all_moments)} visual moments of interest flagged across windows: {', '.join(set(m['window'] for m in all_moments))}.",
            "evidence": [
                {"source": e.get("source", "camera"),
                 "topic_or_file": e.get("channel", e.get("camera", "?")),
                 "t_ns": e.get("t_ns"),
                 "snippet": e.get("snippet", "")[:200]}
                for m in all_moments for e in m.get("evidence", [])
            ][:20],
            "patch_hint": "Review flagged moments manually; prioritize by confidence and safety impact.",
        }]
    else:
        hyps = [{
            "bug_class": "other",
            "confidence": 0.0,
            "summary": "No anomalies detected in any window.",
            "evidence": [],
            "patch_hint": "None. Nominal operation.",
        }]

    pdf_dict = {
        "timeline": timeline,
        "hypotheses": hyps,
        "root_cause_idx": 0,
        "patch_proposal": "\n".join(f"[{w}] {pw['summary'].get('overall', '')}" for w, pw in per_window.items()),
    }
    preview_imgs = []
    for w_name in wm["windows"]:
        pp = frames_dir / f"{w_name}__preview_5up.png"
        if pp.exists():
            preview_imgs.append(Image.open(pp).convert("RGB"))

    out_pdf = out_dir / "mining_report_v2.pdf"
    build_report(
        report_json=pdf_dict,
        artifacts={"frames": [], "plots": preview_imgs, "code_diff": ""},
        out_pdf=out_pdf,
        case_meta={
            "case_key": bag_id,
            "bag_path": wm["bag"],
            "duration_s": float(wm["duration_s"]),
            "mode": "scenario_mining_v2_vision_only",
        },
    )

    total_spent = client.total_spent_usd()
    print(f"[done] {bag_id}  moments={len(all_moments)}  cost=${total_cost:.4f}  wall={wall:.1f}s  pdf={out_pdf}", flush=True)
    print(f"[done] total spent across session: ${total_spent:.4f}", flush=True)
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("bag_id")
    ap.add_argument("frames_dir", type=Path)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--force", action="store_true", help="Run deep stage on all windows regardless of summary verdict")
    ap.add_argument("--prompt", type=str, default=None,
                    help="Optional operator hypothesis (free text). Passed to the model verbatim.")
    args = ap.parse_args()
    user_prompt = args.prompt or os.environ.get("BB_USER_PROMPT")
    run(args.bag_id, args.frames_dir, args.out_dir, args.force, user_prompt)
