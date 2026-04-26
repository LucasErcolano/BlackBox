"""Normalize every input clip to the demo's canonical mezzanine.

Output: 1920x1080, constant 30 fps, yuv420p, libx264, square pixels (SAR=1),
silent. We intentionally letterbox/pad with the demo BG color (#0a0c10) so
incoming clips with mismatched aspect ratios don't get stretched.

Inputs:  demo_assets/final_demo_pack/clips/block_*.mp4
Outputs: demo_assets/final_demo_pack/normalized_clips/<name>.mp4
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "demo_assets/final_demo_pack"
SRC = PACK / "clips"
DST = PACK / "normalized_clips"
DST.mkdir(parents=True, exist_ok=True)

VF = (
    "scale=1920:1080:force_original_aspect_ratio=decrease,"
    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0a0c10,"
    "fps=30,format=yuv420p,setsar=1"
)


def ffprobe_meta(p: Path) -> dict:
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,codec_name,pix_fmt,sample_aspect_ratio",
        "-show_entries", "format=duration",
        "-of", "json", str(p)
    ])
    return json.loads(out)


def normalize(src: Path, dst: Path) -> dict:
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src), "-an",
        "-vf", VF,
        "-vsync", "cfr",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(dst),
    ]
    subprocess.run(cmd, check=True)
    return ffprobe_meta(dst)


def main() -> int:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("ffmpeg/ffprobe required", file=sys.stderr)
        return 2

    sources = sorted(SRC.glob("block_*.mp4"))
    if not sources:
        print("no inputs in", SRC, file=sys.stderr)
        return 2

    report: list[dict] = []
    for src in sources:
        dst = DST / src.name
        meta = normalize(src, dst)
        v = meta["streams"][0]
        dur = float(meta["format"]["duration"])
        report.append({
            "src": str(src.relative_to(ROOT)),
            "dst": str(dst.relative_to(ROOT)),
            "width": v["width"], "height": v["height"],
            "r_frame_rate": v["r_frame_rate"],
            "pix_fmt": v["pix_fmt"], "codec": v["codec_name"],
            "sar": v.get("sample_aspect_ratio"),
            "duration_s": round(dur, 3),
        })
        print(f"normalized {src.name}: {v['width']}x{v['height']} "
              f"{v['r_frame_rate']} {v['pix_fmt']} dur={dur:.2f}s")

    # Hard assert: every output is identical-shape mezzanine.
    failures: list[str] = []
    for r in report:
        if (r["width"], r["height"]) != (1920, 1080):
            failures.append(f"{r['dst']} size {r['width']}x{r['height']}")
        if r["r_frame_rate"] != "30/1":
            failures.append(f"{r['dst']} fps {r['r_frame_rate']}")
        if r["pix_fmt"] != "yuv420p":
            failures.append(f"{r['dst']} pix_fmt {r['pix_fmt']}")
        if r["codec"] != "h264":
            failures.append(f"{r['dst']} codec {r['codec']}")

    out_json = DST / "normalize_report.json"
    out_json.write_text(json.dumps(report, indent=2))
    if failures:
        print("FAIL:", file=sys.stderr)
        for f in failures:
            print(" -", f, file=sys.stderr)
        return 1
    print(f"OK: {len(report)} clips normalized → {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
