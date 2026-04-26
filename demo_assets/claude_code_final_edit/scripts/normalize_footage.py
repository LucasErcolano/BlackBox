"""Render each timeline segment to a normalized 1920x1080@30 yuv420p MP4."""
import json
import subprocess
from pathlib import Path

ROOT = Path("/home/hz/Desktop/BlackBox")
EDIT = ROOT / "demo_assets/claude_code_final_edit"
SEGS = EDIT / "segments"
SEGS.mkdir(parents=True, exist_ok=True)

VF_VIDEO = ("fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0b0d11,"
            "setsar=1,format=yuv420p")
VF_STILL = ("scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0b0d11,"
            "fps=30,setsar=1,format=yuv420p")


def render(seg, dst: Path):
    if seg["kind"] == "video":
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-ss", f'{seg["in_s"]}', "-t", f'{seg["duration_s"]}',
               "-i", seg["src"], "-vf", VF_VIDEO,
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
               "-pix_fmt", "yuv420p", "-r", "30", "-an", str(dst)]
    else:
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-loop", "1", "-t", f'{seg["duration_s"]}',
               "-i", seg["src"], "-vf", VF_STILL,
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
               "-pix_fmt", "yuv420p", "-r", "30", "-an", str(dst)]
    subprocess.run(cmd, check=True)


def main():
    tl = json.loads((EDIT / "output/timeline.json").read_text())
    files = []
    for i, seg in enumerate(tl["segments"]):
        dst = SEGS / f"{i:02d}_{seg['id']}.mp4"
        render(seg, dst)
        sz = dst.stat().st_size // 1024
        print(f"  {dst.name} {seg['duration_s']:.2f}s {sz}KB")
        files.append(dst)
    listf = SEGS / "concat.txt"
    listf.write_text("\n".join(f"file '{f.name}'" for f in files) + "\n")
    print(f"wrote {listf}")


if __name__ == "__main__":
    main()
