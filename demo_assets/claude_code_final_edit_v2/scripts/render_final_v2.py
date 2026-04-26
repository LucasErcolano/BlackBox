"""V2 render: 27 normalized segments chained with concat + 4 strategic 0.25s xfades.
Captions written from the shifted timeline (xfades reduce total by 4*0.25=1.0s)
and burned via subtitles=ASS at final encode."""
import json
import subprocess
from pathlib import Path

ROOT = Path("/home/hz/Desktop/BlackBox")
EDIT = ROOT / "demo_assets/claude_code_final_edit_v2"
SEGS = EDIT / "segments"
OUT = EDIT / "output"
OUT.mkdir(parents=True, exist_ok=True)

FINAL = OUT / "blackbox_demo_claude_edit_v2.mp4"
NOAUDIO = OUT / "blackbox_demo_claude_edit_v2_no_audio.mp4"
SRT = OUT / "blackbox_demo_claude_edit_v2_captions.srt"
ASS = OUT / "blackbox_demo_claude_edit_v2_captions.ass"


def fmt_srt(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t - h*3600 - m*60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int((s-int(s))*1000):03d}"


def fmt_ass(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t - h*3600 - m*60
    return f"{h:01d}:{m:02d}:{s:05.2f}"


def write_srt(captions, p):
    L = []
    for i, c in enumerate(captions, 1):
        L += [str(i), f"{fmt_srt(c['start_s'])} --> {fmt_srt(c['end_s'])}", c["text"], ""]
    p.write_text("\n".join(L))


def write_ass(captions, p):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter,42,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,3,2.4,1,2,100,100,72,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    body = []
    for c in captions:
        text = c["text"].replace(",", "\\,")
        body.append(f"Dialogue: 0,{fmt_ass(c['start_s'])},{fmt_ass(c['end_s'])},Cap,,0,0,0,,{text}")
    p.write_text(header + "\n".join(body) + "\n")


def main():
    tl = json.loads((EDIT / "output/timeline_v2.json").read_text())
    segs = tl["segments"]
    xfade_ids = set(tl["xfade_at_segment_ids"])
    XFD = float(tl["xfade_dur"])

    # Compute new (post-xfade) start times for each segment
    new_starts = [0.0]
    for i in range(1, len(segs)):
        prev = new_starts[-1] + segs[i-1]["duration_s"]
        if segs[i]["id"] in xfade_ids:
            prev -= XFD
        new_starts.append(prev)
    final_total = new_starts[-1] + segs[-1]["duration_s"]

    # Shift captions to post-xfade timeline
    shifted = []
    seg_by_id = {s["id"]: i for i, s in enumerate(segs)}
    for c in tl["captions"]:
        si = seg_by_id[c["seg_id"]]
        offset_in_seg = c["start_s"] - segs[si]["start_s"]
        new_start = new_starts[si] + offset_in_seg
        new_end = new_start + (c["end_s"] - c["start_s"])
        shifted.append({"start_s": new_start, "end_s": new_end, "text": c["text"]})

    write_srt(shifted, SRT)
    write_ass(shifted, ASS)
    print(f"wrote {SRT.name} {ASS.name} (final_total={final_total:.2f}s)")

    # Per-pair xfade blends: at each xfade boundary, blend seg[i-1]+seg[i] into one mp4.
    seg_files = [SEGS / f"{i:02d}_{s['id']}.mp4" for i, s in enumerate(segs)]
    blends = {}  # i -> blended_path replacing seg[i-1] AND seg[i]
    for i, s in enumerate(segs):
        if s["id"] in xfade_ids and i > 0:
            a = seg_files[i-1]; b = seg_files[i]
            dur_a = segs[i-1]["duration_s"]
            blended = SEGS / f"_blend_{i:02d}.mp4"
            fc = (
                f"[0:v]fps=30,format=yuv420p,settb=1/30,setpts=PTS-STARTPTS[a];"
                f"[1:v]fps=30,format=yuv420p,settb=1/30,setpts=PTS-STARTPTS[b];"
                f"[a][b]xfade=transition=fade:duration={XFD}:offset={dur_a-XFD:.4f},"
                f"format=yuv420p[v]"
            )
            cmd = ["ffmpeg", "-y", "-loglevel", "error",
                   "-i", str(a), "-i", str(b),
                   "-filter_complex", fc, "-map", "[v]",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                   "-pix_fmt", "yuv420p", "-r", "30", "-an", str(blended)]
            subprocess.run(cmd, check=True)
            print(f"  xfade blend {a.name} + {b.name} -> {blended.name}")
            blends[i] = blended

    # Build concat list: substitute (seg[i-1], seg[i]) with blends[i]
    concat_files = []
    skip_next = False
    for i, f in enumerate(seg_files):
        if skip_next:
            skip_next = False
            continue
        # if seg[i+1] is a blend target, replace this pair with blend
        if (i + 1) < len(seg_files) and (i + 1) in blends:
            concat_files.append(blends[i + 1])
            skip_next = True
        else:
            concat_files.append(f)

    listf = SEGS / "concat_v2.txt"
    listf.write_text("\n".join(f"file '{f.name}'" for f in concat_files) + "\n")
    inter = SEGS / "_concat_v2.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", str(listf),
                    "-c", "copy", str(inter)], check=True)
    print(f"intermediate -> {inter} ({inter.stat().st_size//1024}KB)")

    # Burn captions
    ass_path = str(ASS).replace(":", "\\:")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(inter),
                    "-vf", f"subtitles='{ass_path}'",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-r", "30",
                    "-movflags", "+faststart", "-an", str(NOAUDIO)], check=True)
    print(f"no-audio -> {NOAUDIO} ({NOAUDIO.stat().st_size//1024}KB)")

    # Mux silent AAC for player compat
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(NOAUDIO),
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-shortest", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart", str(FINAL)], check=True)
    print(f"final -> {FINAL} ({FINAL.stat().st_size//1024}KB)")


if __name__ == "__main__":
    main()
