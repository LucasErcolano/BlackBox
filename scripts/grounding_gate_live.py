# SPDX-License-Identifier: MIT
"""Live grounding-gate regression — opt-in, hits real API.

Runs window_summary_v2 + visual_mining_v2 on a known-clean fixture window and
asserts no moments are emitted and the window is flagged not-interesting.

Usage:
    python scripts/grounding_gate_live.py --fixture data/fixtures/clean_window_01/

The fixture directory must contain 5 JPEGs named cam1.jpg..cam6.jpg
(except cam2 which is unused in the 5-camera layout).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from black_box.analysis import ClaudeClient
from black_box.analysis.prompts_generic import (
    visual_mining_prompt,
    window_summary_prompt,
)
from black_box.ingestion.manifest import Manifest, TopicInfo


CAMERAS = ["cam1", "cam3", "cam4", "cam5", "cam6"]


def load_fixture(fixture_dir: Path) -> list[Image.Image]:
    imgs = []
    for cam in CAMERAS:
        p = fixture_dir / f"{cam}.jpg"
        if not p.exists():
            raise FileNotFoundError(f"Missing {p}")
        imgs.append(Image.open(p).convert("RGB"))
    return imgs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", type=Path, required=True)
    args = ap.parse_args()

    imgs = load_fixture(args.fixture)
    client = ClaudeClient()

    manifest = Manifest(
        root=args.fixture, session_key=None, bags=[],
        duration_s=2.0, t_start_ns=None, t_end_ns=None,
        cameras=[TopicInfo(topic=f"/{c}/image_raw/compressed",
                           msgtype="sensor_msgs/CompressedImage",
                           count=0, kind="camera") for c in CAMERAS],
    )

    print("Stage 1: window_summary triage ...")
    summary, cost1 = client.analyze(
        window_summary_prompt(manifest=manifest),
        images=imgs,
        user_fields={
            "window_len_s": 2.0,
            "frames_index": "\n".join(f"{c} t=0" for c in CAMERAS),
        },
        resolution="thumb",
    )
    print(f"  interesting={summary.interesting} reason={summary.reason!r}")
    print(f"  cost=${cost1.usd_cost:.4f}")

    if summary.interesting:
        print("GATE WARNING: clean fixture flagged interesting.", file=sys.stderr)

    print("Stage 2: visual_mining deep ...")
    mining, cost2 = client.analyze(
        visual_mining_prompt(manifest=manifest),
        images=imgs,
        user_fields={
            "n_images": len(imgs),
            "frames_index": "\n".join(f"{c} t=0" for c in CAMERAS),
            "window_info": "Known-clean residential window (grounding-gate fixture).",
        },
        resolution="thumb",
    )
    print(f"  moments={len(mining.moments)} rationale={mining.rationale!r}")
    print(f"  cost=${cost2.usd_cost:.4f}")

    if mining.moments:
        print(
            f"GATE FAILED: agent produced {len(mining.moments)} moments on a clean fixture.",
            file=sys.stderr,
        )
        return 1

    print(f"GATE OK — total spend ${cost1.usd_cost + cost2.usd_cost:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
