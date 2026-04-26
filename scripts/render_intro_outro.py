#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Render intro_card.mp4 + outro_card.mp4 with live cost from data/costs.jsonl.

Outputs land in video_assets/final_intro_outro/. Dark palette matches the
in-video UI capture aesthetic.
"""
from __future__ import annotations

import datetime as _dt
import json
import shutil
import subprocess
from pathlib import Path

OUT_DIR = Path("video_assets/final_intro_outro")
COSTS = Path("data/costs.jsonl")
FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_HOOK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

BG = "0x0e0f0a"
INK = "0xe8e3d4"
MUTED = "0x9a9786"
RULE = "0x3a3c30"

COST_FIELDS = ("usd_cost", "usd", "cost_usd", "total_usd", "usd_total")


def read_costs() -> tuple[int, float]:
    if not COSTS.exists():
        return (0, 0.0)
    n, total = 0, 0.0
    for line in COSTS.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        n += 1
        for k in COST_FIELDS:
            if k in r:
                try:
                    total += float(r[k] or 0)
                except (TypeError, ValueError):
                    pass
                break
    return (n, total)


def _ff(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def render() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    calls, usd = read_costs()
    today = _dt.date.today().isoformat()

    intro = OUT_DIR / "intro_card.mp4"
    outro = OUT_DIR / "outro_card.mp4"

    intro_vf = (
        f"drawbox=x=380:y=460:w=1160:h=2:color={RULE}:t=fill,"
        f"drawtext=fontfile={FONT_SERIF}:text='BlackBox':fontcolor={INK}:fontsize=140:x=(w-text_w)/2:y=300,"
        f"drawtext=fontfile={FONT_SANS}:text='Forensic copilot for robot failures':fontcolor={INK}:fontsize=44:x=(w-text_w)/2:y=510,"
        f"drawtext=fontfile={FONT_MONO}:text='video · telemetry · tools · memory · patch':fontcolor={MUTED}:fontsize=26:x=(w-text_w)/2:y=600,"
        f"fade=t=in:st=0:d=0.3,fade=t=out:st=3.6:d=0.3"
    )
    _ff([
        "-f", "lavfi", "-i", f"color=c={BG}:s=1920x1080:r=30:d=4",
        "-vf", intro_vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
        "-metadata", f"creation_time={today}T00:00:00Z",
        str(intro),
    ])

    outro_dir = OUT_DIR / "_text"
    outro_dir.mkdir(exist_ok=True)
    lines = {
        "o1": "Robot forensics in minutes, for cents.",
        "o2": "Open benchmark   ·   Reproducible runs   ·   Evidence-grounded",
        "o3": "github.com/LucasErcolano/BlackBox",
        "o4": f"bench: black-box-bench  ·  cost ledger: data/costs.jsonl  ({calls} calls, ${usd:.2f})",
        "o5": f"Built with Opus 4.7  ·  {today}",
    }
    for k, v in lines.items():
        (outro_dir / f"{k}.txt").write_text(v)

    outro_vf = (
        f"drawbox=x=380:y=270:w=1160:h=2:color={RULE}:t=fill,"
        f"drawbox=x=380:y=820:w=1160:h=2:color={RULE}:t=fill,"
        f"drawtext=fontfile={FONT_SERIF}:textfile={outro_dir}/o1.txt:expansion=none:fontcolor={INK}:fontsize=60:x=(w-text_w)/2:y=320,"
        f"drawtext=fontfile={FONT_SANS}:textfile={outro_dir}/o2.txt:expansion=none:fontcolor={INK}:fontsize=36:x=(w-text_w)/2:y=470,"
        f"drawtext=fontfile={FONT_MONO}:textfile={outro_dir}/o3.txt:expansion=none:fontcolor={INK}:fontsize=34:x=(w-text_w)/2:y=580,"
        f"drawtext=fontfile={FONT_MONO}:textfile={outro_dir}/o4.txt:expansion=none:fontcolor={MUTED}:fontsize=24:x=(w-text_w)/2:y=660,"
        f"drawtext=fontfile={FONT_MONO}:textfile={outro_dir}/o5.txt:expansion=none:fontcolor={MUTED}:fontsize=24:x=(w-text_w)/2:y=860,"
        f"fade=t=in:st=0:d=0.4,fade=t=out:st=5.5:d=0.5"
    )
    _ff([
        "-f", "lavfi", "-i", f"color=c={BG}:s=1920x1080:r=30:d=6",
        "-vf", outro_vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
        "-metadata", f"creation_time={today}T00:00:00Z",
        str(outro),
    ])

    for src, name in ((intro, "intro.png"), (outro, "outro.png")):
        _ff(["-ss", "1.5", "-i", str(src), "-frames:v", "1", str(OUT_DIR / name)])

    shutil.rmtree(outro_dir)
    print(f"intro+outro rendered. cost: {calls} calls, ${usd:.2f}. date: {today}")


if __name__ == "__main__":
    render()
