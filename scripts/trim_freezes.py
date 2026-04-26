"""Detect and trim trailing freeze frames from each normalized clip.

We run ``ffmpeg -vf freezedetect`` over every clip in
``normalized_clips/``, parse freeze segments from the lavfi metadata,
and trim the clip if the **last** freeze ends within ``TAIL_WINDOW``
seconds of the source duration. The trimmed copy is written to
``trimmed_clips/<name>.mp4`` with full re-encode (so timestamps are
clean for downstream xfade).

Threshold defaults: noise -50 dB, min freeze 0.4 s. Tunable below.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "demo_assets/final_demo_pack"
SRC = PACK / "normalized_clips"
DST = PACK / "trimmed_clips"
DST.mkdir(parents=True, exist_ok=True)

NOISE_DB = "-50dB"
MIN_FREEZE_S = 0.4
TAIL_WINDOW_S = 1.6   # any freeze whose end lands inside the final 1.6s is "near-end"
KEEP_AFTER_MS = 80    # keep this many ms after the last motion frame
MIN_OUT_S = 6.5       # never trim a clip below this duration

# Clips whose final hold is intentionally a static title card and must not
# be trimmed. Their freezes are exempt from QA freezedetect too.
INTENTIONAL_STATIC = {"block_10_outro.mp4"}

VF_NORMALIZE = (
    "scale=1920:1080:force_original_aspect_ratio=decrease,"
    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0a0c10,"
    "fps=30,format=yuv420p,setsar=1"
)


def ffprobe_duration(p: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(p),
    ])
    return float(out.decode().strip())


def detect_freezes(p: Path) -> list[dict]:
    proc = subprocess.run([
        "ffmpeg", "-hide_banner", "-i", str(p),
        "-vf", f"freezedetect=n={NOISE_DB}:d={MIN_FREEZE_S}",
        "-map", "0:v:0", "-f", "null", "-",
    ], stderr=subprocess.PIPE, stdout=subprocess.DEVNULL)
    text = proc.stderr.decode("utf-8", "replace")

    starts = [float(m.group(1)) for m in re.finditer(r"freeze_start: ([\d.]+)", text)]
    ends = [float(m.group(1)) for m in re.finditer(r"freeze_end: ([\d.]+)", text)]
    durs = [float(m.group(1)) for m in re.finditer(r"freeze_duration: ([\d.]+)", text)]

    freezes: list[dict] = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        dur = durs[i] if i < len(durs) else (e - s if e is not None else None)
        freezes.append({"start": s, "end": e, "duration": dur})
    return freezes


def trim(src: Path, dst: Path, end_t: float) -> None:
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src), "-an",
        "-t", f"{end_t:.3f}",
        "-vf", VF_NORMALIZE,
        "-vsync", "cfr",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def passthrough(src: Path, dst: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src), "-an",
        "-vf", VF_NORMALIZE,
        "-vsync", "cfr",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    sources = sorted(SRC.glob("*.mp4"))
    if not sources:
        print("no normalized clips found; run normalize_clips.py first", file=sys.stderr)
        return 2

    report: list[dict] = []
    for p in sources:
        in_dur = ffprobe_duration(p)
        dst = DST / p.name

        if p.name in INTENTIONAL_STATIC:
            passthrough(p, dst)
            out_dur = ffprobe_duration(dst)
            report.append({
                "clip": p.name,
                "input_duration_s": round(in_dur, 3),
                "decision": "intentional_static",
                "passes": [],
                "output_duration_s": round(out_dur, 3),
            })
            print(f"{p.name}: intentional_static  in={in_dur:.2f}s  out={out_dur:.2f}s")
            continue

        # Find the earliest freeze whose end lies inside the clip's final
        # TAIL_WINDOW_S (or whose end is None — runs to EOF). That's the
        # *first* of a chain of "we've already gone static" freezes. Trim
        # the clip to that freeze's start + KEEP_AFTER_MS so the last frame
        # of the kept clip is still motion.
        freezes = detect_freezes(p)
        cur_dur = in_dur
        candidate_starts: list[float] = []
        for f in freezes:
            f_dur = f["duration"] if f["duration"] is not None else (
                (f["end"] if f["end"] is not None else cur_dur) - f["start"]
            )
            if f_dur < MIN_FREEZE_S:
                continue
            ends_at = f["end"] if f["end"] is not None else cur_dur
            if f["end"] is None or ends_at >= cur_dur - TAIL_WINDOW_S:
                candidate_starts.append(f["start"])
        decision = "passthrough"
        end_t = cur_dur
        if candidate_starts:
            new_end = max(MIN_OUT_S, min(candidate_starts) + KEEP_AFTER_MS / 1000.0)
            if new_end < cur_dur - 0.05:
                end_t = new_end
                decision = "trimmed"

        if decision == "trimmed":
            trim(p, dst, end_t)
        else:
            passthrough(p, dst)

        out_dur = ffprobe_duration(dst)
        report.append({
            "clip": p.name,
            "input_duration_s": round(in_dur, 3),
            "decision": decision,
            "freezes": freezes,
            "trim_to_s": round(end_t, 3) if decision == "trimmed" else None,
            "output_duration_s": round(out_dur, 3),
        })
        print(f"{p.name}: {decision}  in={in_dur:.2f}s  out={out_dur:.2f}s")

    (DST / "trim_report.json").write_text(json.dumps(report, indent=2))
    print(f"OK: {len(report)} clips → {DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
