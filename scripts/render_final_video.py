"""Assemble the final 2:50–3:00 demo video.

Inputs are the clean mezzanines produced by ``trim_freezes.py`` and the
layout-safe panels produced by ``build_layout_safe_panels.py``. Every
segment is normalized again (defence in depth: identical SAR, fps, pix
fmt, codec) before being chained through the ffmpeg ``xfade`` filter at
0.35 s. No concat demuxer.

Outputs:
  demo_assets/final_demo_pack/final_video_v2/
    blackbox_demo_final_v2.mp4
    blackbox_demo_final_v2_no_audio.mp4
    timeline.json
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "demo_assets/final_demo_pack"
TRIM = PACK / "trimmed_clips"
PANELS = PACK / "panels"
OUT_DIR = PACK / "final_video_v2"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TMP = OUT_DIR / "_segments"
TMP.mkdir(parents=True, exist_ok=True)

XFADE_S = 0.35
TARGET_W, TARGET_H = 1920, 1080
TARGET_FPS = 30
PANEL_DURATION_S = 17.0  # static title-card hold for each rebuilt panel

VF_NORMAL = (
    f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
    f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color=#0a0c10,"
    f"fps={TARGET_FPS},format=yuv420p,setsar=1"
)


@dataclass
class Segment:
    index: int
    kind: str            # "clip" | "still"
    asset: Path
    duration: float
    beat: str
    intentional_static: bool = False
    out_path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.out_path = TMP / f"{self.index:02d}.mp4"


def ffprobe_dur(p: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(p),
    ])
    return float(out.decode().strip())


def encode_clip(seg: Segment) -> None:
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(seg.asset), "-an",
        "-t", f"{seg.duration:.3f}",
        "-vf", VF_NORMAL,
        "-vsync", "cfr",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(seg.out_path),
    ]
    subprocess.run(cmd, check=True)


def encode_still(seg: Segment) -> None:
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-t", f"{seg.duration:.3f}", "-i", str(seg.asset),
        "-vf", VF_NORMAL, "-r", str(TARGET_FPS),
        "-vsync", "cfr",
        "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage",
        "-crf", "20", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(seg.out_path),
    ]
    subprocess.run(cmd, check=True)


def build_segments() -> list[Segment]:
    segs: list[Segment] = []

    def clip(beat: str, name: str, intentional: bool = False) -> Segment:
        p = TRIM / name
        if not p.exists():
            raise FileNotFoundError(p)
        d = ffprobe_dur(p)
        s = Segment(index=len(segs) + 1, kind="clip", asset=p,
                    duration=d, beat=beat,
                    intentional_static=intentional)
        segs.append(s)
        return s

    def still(beat: str, name: str, dur: float = PANEL_DURATION_S) -> Segment:
        p = PANELS / name
        if not p.exists():
            raise FileNotFoundError(p)
        s = Segment(index=len(segs) + 1, kind="still", asset=p,
                    duration=dur, beat=beat, intentional_static=True)
        segs.append(s)
        return s

    clip("hook", "block_01_hook.mp4")
    clip("problem", "block_02_problem.mp4")
    clip("setup", "block_03_setup.mp4")
    clip("live_managed_agent", "block_04_analysis_live_v2.mp4")
    clip("first_moment", "block_05_first_moment.mp4")
    clip("second_moment_evidence", "block_06_second_moment.mp4")
    still("refutation_climax", "operator_vs_blackbox.png")
    clip("patch_diff_human_gate", "block_08_money_shot.mp4")
    still("opus47_delta", "opus47_delta_panel.png")
    still("generalization", "breadth_montage.png")
    clip("grounding_gate_abstention", "block_07_grounding.mp4")
    clip("cost_and_repo", "block_09_punchline.mp4")
    clip("outro", "block_10_outro.mp4", intentional=True)
    return segs


def encode_segments(segs: list[Segment]) -> None:
    for s in segs:
        if s.kind == "clip":
            encode_clip(s)
        else:
            encode_still(s)


def xfade_pair(left: Path, right: Path, left_dur: float, out: Path) -> None:
    """Crossfade ``left`` (running ``left_dur`` s) with ``right``."""
    offset = max(0.0, left_dur - XFADE_S)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(left), "-i", str(right),
        "-filter_complex",
        f"[0:v][1:v]xfade=transition=fade:duration={XFADE_S}:offset={offset:.4f}[v]",
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out),
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    if not shutil.which("ffmpeg"):
        print("ffmpeg required", file=sys.stderr)
        return 2
    segs = build_segments()
    encode_segments(segs)

    out_noaud = OUT_DIR / "blackbox_demo_final_v2_no_audio.mp4"
    out_full = OUT_DIR / "blackbox_demo_final_v2.mp4"

    # Pairwise xfade keeps memory bounded (13 inputs through one filter
    # graph hits OOM on this box).
    cur = segs[0].out_path
    cur_dur = segs[0].duration
    for k in range(1, len(segs)):
        nxt = segs[k].out_path
        merged = TMP / f"_merged_{k:02d}.mp4"
        xfade_pair(cur, nxt, cur_dur, merged)
        cur = merged
        cur_dur = cur_dur + segs[k].duration - XFADE_S
    # Final pass: copy/transcode to the destination with faststart.
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(cur), "-an",
        "-c:v", "copy", "-movflags", "+faststart",
        str(out_noaud),
    ], check=True)

    total = sum(s.duration for s in segs) - XFADE_S * (len(segs) - 1)
    cmd2 = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(out_noaud),
        "-f", "lavfi", "-t", f"{total:.3f}",
        "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(out_full),
    ]
    subprocess.run(cmd2, check=True)

    timeline = {
        "schema": "blackbox_demo_timeline/2.0",
        "resolution": [TARGET_W, TARGET_H],
        "fps": TARGET_FPS,
        "video_codec": "libx264",
        "pix_fmt": "yuv420p",
        "audio_codec": "aac",
        "xfade_seconds": XFADE_S,
        "target_runtime_s": round(total, 3),
        "segments": [],
    }
    cum = 0.0
    for k, s in enumerate(segs):
        # cumulative offset of this segment's *visible* start
        if k == 0:
            seg_in = 0.0
        else:
            seg_in = cum - XFADE_S * k
        seg_out = seg_in + s.duration if k == 0 else seg_in + s.duration
        cum += s.duration
        timeline["segments"].append({
            "i": s.index,
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
    print(f"  duration={actual:.2f}s ({actual/60:.0f}:{actual%60:05.2f})")
    print(f"  segments={len(segs)}  xfade={XFADE_S}s")
    if not (170.0 <= actual <= 180.0):
        print(f"FAIL: duration {actual:.2f}s outside 2:50–3:00 envelope",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
