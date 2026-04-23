"""Telemetry-anchored vision densification for sanfer_sanisidro.

Reads the pre-camera analysis.json timeline, lifts the agent's own
suspicious timestamps into windows, then runs the generic frame sampler
in a single AnyReader pass. Replaces the old uniform-stride extractor.

Output:
- data/final_runs/sanfer_tunnel/bundle/frames/frame_XXXXs_(base|dense).jpg
- demo_assets/bag_footage/sanfer_tunnel/   (mirror)
- data/final_runs/sanfer_tunnel/bundle/frames_manifest.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from black_box.analysis.windows import from_timeline, merge_overlapping
from black_box.ingestion.session import discover_session_assets
from black_box.ingestion.frame_sampler import sample_frames


ANALYSIS = Path("data/final_runs/sanfer_tunnel/analysis.pre_cam.json")
OUT_BUNDLE = Path("data/final_runs/sanfer_tunnel/bundle/frames")
OUT_DEMO = Path("demo_assets/bag_footage/sanfer_tunnel")
SESSION_ROOT = Path("/mnt/hdd/sanfer_sanisidro")
TOPIC = "/cam1/image_raw/compressed"


def main() -> int:
    if not ANALYSIS.exists():
        print(f"missing analysis: {ANALYSIS}", file=sys.stderr)
        return 2

    # Wipe previous uniform-stride frames so the manifest reflects this pass.
    if OUT_BUNDLE.exists():
        for p in OUT_BUNDLE.glob("frame_*.jpg"):
            p.unlink()
    if OUT_DEMO.exists():
        for p in OUT_DEMO.glob("frame_*.jpg"):
            p.unlink()

    assets = discover_session_assets(SESSION_ROOT)
    print(assets.summary())
    cam_bags = [b for b in assets.bags if "cam-lidar" in b.name]
    if not cam_bags:
        print(f"no cam-lidar bag in session under {SESSION_ROOT}", file=sys.stderr)
        return 3

    analysis = json.loads(ANALYSIS.read_text())
    raw = from_timeline(analysis, default_span_s=30.0)
    windows = merge_overlapping(raw, merge_gap_s=10.0)
    print(f"windows: {len(windows)} (merged from {len(raw)})")
    for w in windows:
        print(f"  t={w.center_ns/1e9:7.2f}s span={w.span_s:4.1f}s :: {w.label[:90]}")

    manifest = sample_frames(
        bags=cam_bags,
        topic=TOPIC,
        windows=windows,
        out_dir=OUT_BUNDLE,
        dense_stride_s=5.0,
        baseline_n=8,
        jpeg_quality=88,
        mirror_to=OUT_DEMO,
        log=print,
    )

    mani_path = OUT_BUNDLE.parent / "frames_manifest.json"
    mani_path.write_text(json.dumps({
        "source_bag": str(cam_bags[0]),
        "topic": TOPIC,
        "dense_stride_s": 5.0,
        "baseline_n": 8,
        "windows": [w.to_dict() for w in windows],
        "frames": manifest,
    }, indent=2))
    print(f"manifest -> {mani_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
