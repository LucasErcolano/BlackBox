"""Render the hybrid demo cut: v2 backbone with two real-UI swaps.

Swap A: block_08_money_shot (designed)  → 06_patch_diff_ui.mp4 (real /report)
Swap B: breadth_montage panel (designed) → 07_cases_archive_ui.mp4 (real /cases)

Pipeline mirrors scripts/render_final_video.py: re-normalize each segment
to 1920x1080 30fps yuv420p, then pairwise xfade at 0.35s. Silent AAC track
muxed in at the end.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path("/home/hz/Desktop/BlackBox")
PACK = ROOT / "demo_assets/final_demo_pack"
TRIM = PACK / "trimmed_clips"
PANELS = PACK / "panels"
RAW = ROOT / "demo_assets/editor_raw_footage_pack/clips"
OUT_DIR = ROOT / "demo_assets/final_video_competition/20260426_2058/drafts/hybrid"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TMP = OUT_DIR / "_segments"
TMP.mkdir(parents=True, exist_ok=True)

XFADE_S = 0.35
W, H, FPS = 1920, 1080, 30
VF = (
    f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
    f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=#0a0c10,"
    f"fps={FPS},format=yuv420p,setsar=1"
)


@dataclass
class Seg:
    i: int
    kind: str  # clip | still
    asset: Path
    duration: float
    beat: str
    intentional_static: bool = False
    out_path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.out_path = TMP / f"{self.i:02d}.mp4"


def ffprobe_dur(p: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(p),
    ])
    return float(out.decode().strip())


def encode_clip(s: Seg) -> None:
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(s.asset), "-an", "-t", f"{s.duration:.3f}",
        "-vf", VF, "-vsync", "cfr",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(s.out_path),
    ], check=True)


def encode_still(s: Seg) -> None:
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-t", f"{s.duration:.3f}", "-i", str(s.asset),
        "-vf", VF, "-r", str(FPS), "-vsync", "cfr",
        "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage",
        "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(s.out_path),
    ], check=True)


def xfade_pair(left: Path, right: Path, left_dur: float, out: Path) -> None:
    offset = max(0.0, left_dur - XFADE_S)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(left), "-i", str(right),
        "-filter_complex",
        f"[0:v][1:v]xfade=transition=fade:duration={XFADE_S}:offset={offset:.4f}[v]",
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out),
    ], check=True)


def build() -> list[Seg]:
    segs: list[Seg] = []

    def add_clip(asset: Path, beat: str, dur: float | None = None,
                 intentional: bool = False) -> None:
        d = dur if dur is not None else ffprobe_dur(asset)
        segs.append(Seg(i=len(segs) + 1, kind="clip", asset=asset,
                        duration=d, beat=beat,
                        intentional_static=intentional))

    def add_still(asset: Path, beat: str, dur: float) -> None:
        segs.append(Seg(i=len(segs) + 1, kind="still", asset=asset,
                        duration=dur, beat=beat,
                        intentional_static=True))

    add_clip(TRIM / "block_01_hook.mp4", "hook")
    add_clip(TRIM / "block_02_problem.mp4", "problem")
    add_clip(TRIM / "block_03_setup.mp4", "setup")
    add_clip(TRIM / "block_04_analysis_live_v2.mp4", "live_managed_agent")
    add_clip(TRIM / "block_05_first_moment.mp4", "first_moment")
    add_clip(TRIM / "block_06_second_moment.mp4", "second_moment_evidence")
    add_still(PANELS / "operator_vs_blackbox.png", "refutation_climax", 17.0)
    # SWAP A: real /report diff UI
    add_clip(RAW / "06_patch_diff_ui.mp4", "patch_diff_human_gate")
    add_still(PANELS / "opus47_delta_panel.png", "opus47_delta", 17.0)
    # SWAP B: real /cases archive UI
    add_clip(RAW / "07_cases_archive_ui.mp4", "generalization")
    add_clip(TRIM / "block_07_grounding.mp4", "grounding_gate_abstention")
    add_clip(TRIM / "block_09_punchline.mp4", "cost_and_repo")
    add_clip(TRIM / "block_10_outro.mp4", "outro", intentional=True)
    return segs


def main() -> int:
    if not shutil.which("ffmpeg"):
        print("ffmpeg required", file=sys.stderr)
        return 2
    segs = build()
    for s in segs:
        (encode_clip if s.kind == "clip" else encode_still)(s)

    out_noaud = OUT_DIR / "blackbox_demo_hybrid_no_audio.mp4"
    out_full = OUT_DIR / "blackbox_demo_hybrid.mp4"

    cur = segs[0].out_path
    cur_dur = segs[0].duration
    for k in range(1, len(segs)):
        merged = TMP / f"_merged_{k:02d}.mp4"
        xfade_pair(cur, segs[k].out_path, cur_dur, merged)
        cur = merged
        cur_dur = cur_dur + segs[k].duration - XFADE_S

    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(cur), "-an", "-c:v", "copy",
        "-movflags", "+faststart", str(out_noaud),
    ], check=True)

    total = sum(s.duration for s in segs) - XFADE_S * (len(segs) - 1)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(out_noaud),
        "-f", "lavfi", "-t", f"{total:.3f}",
        "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart", str(out_full),
    ], check=True)

    timeline = {
        "schema": "blackbox_demo_timeline/2.1-hybrid",
        "resolution": [W, H], "fps": FPS,
        "video_codec": "libx264", "pix_fmt": "yuv420p",
        "audio_codec": "aac", "xfade_seconds": XFADE_S,
        "target_runtime_s": round(total, 3),
        "segments": [],
    }
    cum = 0.0
    for k, s in enumerate(segs):
        seg_in = 0.0 if k == 0 else cum - XFADE_S * k
        seg_out = seg_in + s.duration
        cum += s.duration
        timeline["segments"].append({
            "i": s.i,
            "in_s": round(max(0.0, seg_in - (0 if k == 0 else XFADE_S)), 3),
            "out_s": round(seg_out, 3),
            "duration_s": round(s.duration, 3),
            "kind": s.kind,
            "asset": str(s.asset.relative_to(ROOT)),
            "beat": s.beat,
            "intentional_static": bool(s.intentional_static),
        })
    (OUT_DIR / "timeline.json").write_text(json.dumps(timeline, indent=2))

    actual = ffprobe_dur(out_full)
    print(f"final: {out_full}")
    print(f"  duration={actual:.2f}s ({int(actual//60)}:{actual%60:05.2f})")
    print(f"  segments={len(segs)}  xfade={XFADE_S}s")
    if not (170.0 <= actual <= 180.0):
        print(f"FAIL: {actual:.2f}s outside window", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
