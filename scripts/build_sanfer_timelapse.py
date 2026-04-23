"""Annotated timelapse from real sanfer_tunnel cam1 frames."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

FRAMES_DIR = Path("demo_assets/bag_footage/sanfer_tunnel")
STAGING = FRAMES_DIR / "_annotated"
OUT_PLAIN = FRAMES_DIR / "timelapse_cam1.mp4"
OUT_ANN = FRAMES_DIR / "timelapse_cam1_annotated.mp4"
FPS = 2
W, H = 1920, 1080


def load_font(size: int) -> ImageFont.ImageFont:
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def render(src: Path, out: Path, t_s: int, idx: int, total: int,
           annotate_overlay: bool) -> None:
    img = Image.open(src).convert("RGB")
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    s = min(W / img.width, H / img.height)
    nw, nh = int(img.width * s), int(img.height * s)
    canvas.paste(img.resize((nw, nh), Image.LANCZOS),
                 ((W - nw) // 2, (H - nh) // 2))

    if not annotate_overlay:
        canvas.save(out, "PNG")
        return

    d = ImageDraw.Draw(canvas, "RGBA")
    ft_top = load_font(38)
    ft_bot = load_font(28)

    top = "sanfer_tunnel — /cam1/image_raw/compressed  (real .bag footage, 2_cam-lidar.bag)"
    bot = (f"frame {idx}/{total}   t = {t_s}s of 3627s session   "
           f"sampled every 125s   RTK carr=NONE 100% (root cause)")

    def box(text: str, xy: tuple[int, int], font):
        bb = d.textbbox(xy, text, font=font)
        pad = 10
        d.rectangle((bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad),
                    fill=(0, 0, 0, 180))
        d.text(xy, text, font=font, fill=(255, 255, 255))

    box(top, (30, 30), ft_top)
    box(bot, (30, H - 55), ft_bot)

    d.rectangle((0, 0, W, H), outline=(200, 60, 60, 255), width=6)
    box("RTK HEADING INVALID — whole session (ublox rover REL_POS_VALID never set)",
        (W - 920, 30), ft_bot)

    canvas.save(out, "PNG")


def encode(staging_glob: str, out: Path) -> int:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-framerate", str(FPS),
        "-i", staging_glob,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "18", "-preset", "slow",
        "-movflags", "+faststart",
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-1500:])
    return r.returncode


def main() -> int:
    STAGING.mkdir(parents=True, exist_ok=True)
    frames = sorted(FRAMES_DIR.glob("frame_*.jpg"))
    total = len(frames)
    if not total:
        print("no frames"); return 2

    for p in STAGING.glob("*.png"):
        p.unlink()
    for i, src in enumerate(frames):
        m = re.search(r"frame_(\d+)s", src.name)
        t = int(m.group(1)) if m else 0
        render(src, STAGING / f"p_{i:04d}.png", t, i + 1, total, False)
    if encode(str(STAGING / "p_%04d.png"), OUT_PLAIN) != 0:
        return 1
    print(f"wrote {OUT_PLAIN} ({OUT_PLAIN.stat().st_size/1024:.0f} KB)")

    for p in STAGING.glob("*.png"):
        p.unlink()
    for i, src in enumerate(frames):
        m = re.search(r"frame_(\d+)s", src.name)
        t = int(m.group(1)) if m else 0
        render(src, STAGING / f"a_{i:04d}.png", t, i + 1, total, True)
    if encode(str(STAGING / "a_%04d.png"), OUT_ANN) != 0:
        return 1
    print(f"wrote {OUT_ANN} ({OUT_ANN.stat().st_size/1024:.0f} KB)")

    for p in STAGING.glob("*.png"):
        p.unlink()
    STAGING.rmdir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
