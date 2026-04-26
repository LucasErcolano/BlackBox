"""Concat normalized segments, write SRT/ASS captions, burn into final MP4."""
import json
import subprocess
from pathlib import Path

ROOT = Path("/home/hz/Desktop/BlackBox")
EDIT = ROOT / "demo_assets/claude_code_final_edit"
SEGS = EDIT / "segments"
OUT = EDIT / "output"
OUT.mkdir(parents=True, exist_ok=True)

FINAL = OUT / "blackbox_demo_claude_edit_v1.mp4"
NOAUDIO = OUT / "blackbox_demo_claude_edit_v1_no_audio.mp4"
SRT = OUT / "blackbox_demo_claude_edit_v1_captions.srt"
ASS = OUT / "blackbox_demo_claude_edit_v1_captions.ass"


def fmt_srt(t: float) -> str:
    h = int(t // 3600); m = int(t % 3600 // 60); s = t - h*3600 - m*60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int((s-int(s))*1000):03d}"


def fmt_ass(t: float) -> str:
    h = int(t // 3600); m = int(t % 3600 // 60); s = t - h*3600 - m*60
    return f"{h:01d}:{m:02d}:{s:05.2f}"


def write_srt(captions, p: Path):
    lines = []
    for i, c in enumerate(captions, 1):
        lines.append(str(i))
        lines.append(f"{fmt_srt(c['start_s'])} --> {fmt_srt(c['end_s'])}")
        lines.append(c["text"])
        lines.append("")
    p.write_text("\n".join(lines))


def write_ass(captions, p: Path):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Inter,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,3,2,1,2,80,80,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    body = []
    for c in captions:
        text = c["text"].replace(",", "\\,")
        body.append(f"Dialogue: 0,{fmt_ass(c['start_s'])},{fmt_ass(c['end_s'])},Cap,,0,0,0,,{text}")
    p.write_text(header + "\n".join(body) + "\n")


def main():
    tl = json.loads((EDIT / "output/timeline.json").read_text())
    write_srt(tl["captions"], SRT)
    write_ass(tl["captions"], ASS)
    print(f"wrote {SRT.name} {ASS.name}")

    # 1) concat normalized segments -> intermediate
    listf = SEGS / "concat.txt"
    inter = SEGS / "_concat.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", str(listf),
                    "-c", "copy", str(inter)], check=True)
    print(f"concat -> {inter} ({inter.stat().st_size//1024}KB)")

    # 2) burn captions, final encode (silent)
    ass_path = str(ASS).replace(":", "\\:")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(inter),
                    "-vf", f"subtitles='{ass_path}'",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-r", "30",
                    "-movflags", "+faststart", "-an", str(NOAUDIO)], check=True)
    print(f"no-audio -> {NOAUDIO} ({NOAUDIO.stat().st_size//1024}KB)")

    # 3) final = no-audio + silent stereo track (matches "blackbox_demo..." spec)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(NOAUDIO),
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-shortest", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart", str(FINAL)], check=True)
    print(f"final -> {FINAL} ({FINAL.stat().st_size//1024}KB)")


if __name__ == "__main__":
    main()
