"""Generic two-pass frame extractor.

Any case with a prior telemetry-only analysis.json can use this:

    python scripts/extract_session_frames.py \
        --session-root /mnt/hdd/<case>/ \
        --analysis data/final_runs/<case>/analysis.pre_cam.json \
        --topic /cam1/image_raw/compressed \
        --out data/final_runs/<case>/bundle/frames \
        --mirror demo_assets/bag_footage/<case>/

Loads the analysis timeline, merges overlapping windows, runs one
AnyReader pass, writes baseline + dense frames + manifest. Use on
sanfer_tunnel, car_*, boat_* alike.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from black_box.analysis.windows import from_timeline, merge_overlapping
from black_box.ingestion.session import discover_session_assets
from black_box.ingestion.frame_sampler import sample_frames


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--session-root", type=Path, required=True,
                   help="Folder (or single bag) holding the session.")
    p.add_argument("--analysis", type=Path, required=True,
                   help="Prior analysis.json whose timeline seeds windows.")
    p.add_argument("--topic", type=str, required=True,
                   help="Camera topic, e.g. /cam1/image_raw/compressed")
    p.add_argument("--out", type=Path, required=True,
                   help="Output bundle/frames/ directory.")
    p.add_argument("--mirror", type=Path, default=None,
                   help="Optional mirror dir (demo_assets/...).")
    p.add_argument("--dense-stride", type=float, default=5.0,
                   help="Dense inside windows, seconds.")
    p.add_argument("--baseline-n", type=int, default=8,
                   help="Uniform baseline frames across bag.")
    p.add_argument("--default-span", type=float, default=30.0,
                   help="Span assigned to timeline entries without span_s.")
    p.add_argument("--merge-gap", type=float, default=10.0,
                   help="Merge windows whose gap <= this (seconds).")
    p.add_argument("--bag-substring", type=str, default=None,
                   help="Only bags whose name contains this substring. "
                        "Defaults to picking the bag containing the image topic.")
    p.add_argument("--session-key", type=str, default=None,
                   help="Force session prefix (e.g. '2').")
    args = p.parse_args(argv)

    if not args.analysis.exists():
        print(f"missing analysis: {args.analysis}", file=sys.stderr)
        return 2

    assets = discover_session_assets(args.session_root, session_key=args.session_key)
    print(assets.summary())
    if not assets.bags:
        print("no bags in session", file=sys.stderr)
        return 3

    bags = assets.bags
    if args.bag_substring:
        bags = [b for b in bags if args.bag_substring in b.name]
        if not bags:
            print(f"no bag matches substring {args.bag_substring!r}", file=sys.stderr)
            return 4

    analysis = json.loads(args.analysis.read_text())
    raw = from_timeline(analysis, default_span_s=args.default_span)
    windows = merge_overlapping(raw, merge_gap_s=args.merge_gap)
    print(f"windows: {len(windows)} (merged from {len(raw)})")
    for w in windows:
        print(f"  t={w.center_ns/1e9:7.2f}s span={w.span_s:4.1f}s :: {w.label[:90]}")

    args.out.mkdir(parents=True, exist_ok=True)
    manifest = sample_frames(
        bags=bags,
        topic=args.topic,
        windows=windows,
        out_dir=args.out,
        dense_stride_s=args.dense_stride,
        baseline_n=args.baseline_n,
        mirror_to=args.mirror,
        log=print,
    )
    mani_path = args.out.parent / "frames_manifest.json"
    mani_path.write_text(json.dumps({
        "session_root": str(args.session_root),
        "topic": args.topic,
        "dense_stride_s": args.dense_stride,
        "baseline_n": args.baseline_n,
        "windows": [w.to_dict() for w in windows],
        "frames": manifest,
    }, indent=2))
    print(f"manifest -> {mani_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
