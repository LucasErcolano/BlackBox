# SPDX-License-Identifier: MIT
"""Annotated timelapse from real car_1 bag frames.

PIL bakes overlays into PNGs, then imageio-ffmpeg binary (no drawtext)
stitches to mp4.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

FRAMES_DIR = Path("demo_assets/bag_footage/car_1")
STAGING = FRAMES_DIR / "_annotated"
OUT = FRAMES_DIR / "timelapse_cam1_annotated.mp4"
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


def annotate(src: Path, out: Path, t_s: int, idx: int, total: int) -> None:
    img = Image.open(src).convert("RGB")
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    sx = W / img.width
    sy = H / img.height
    s = min(sx, sy)
    nw, nh = int(img.width * s), int(img.height * s)
    resized = img.resize((nw, nh), Image.LANCZOS)
    canvas.paste(resized, ((W - nw) // 2, (H - nh) // 2))

    d = ImageDraw.Draw(canvas, "RGBA")
    ft_top = load_font(42)
    ft_bot = load_font(30)

    top = "car_1 — /cam1/image_raw/compressed  (real .bag footage)"
    bot = f"frame {idx}/{total}   t = {t_s}s of 970s real time   sampled every 30s"

    def draw_box(text: str, xy: tuple[int, int], font):
        bb = d.textbbox(xy, text, font=font)
        pad = 10
        d.rectangle((bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad),
                    fill=(0, 0, 0, 180))
        d.text(xy, text, font=font, fill=(255, 255, 255))

    draw_box(top, (30, 30), ft_top)
    draw_box(bot, (30, H - 60), ft_bot)

    if 45 <= t_s <= 135:
        d.rectangle((0, 0, W, H), outline=(200, 60, 60, 255), width=6)
        draw_box("DWELL — ego stationary (flagged by analysis)",
                 (W - 720, 30), ft_bot)

    canvas.save(out, "PNG")


def main() -> int:
    STAGING.mkdir(parents=True, exist_ok=True)
    for p in STAGING.glob("*.png"):
        p.unlink()

    frames = sorted(FRAMES_DIR.glob("frame_*.jpg"))
    total = len(frames)
    for i, src in enumerate(frames):
        m = re.search(r"frame_(\d+)s", src.name)
        t = int(m.group(1)) if m else 0
        annotate(src, STAGING / f"a_{i:04d}.png", t, i + 1, total)

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-framerate", str(FPS),
        "-i", str(STAGING / "a_%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "18", "-preset", "slow",
        "-movflags", "+faststart",
        str(OUT),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-1500:])
        return r.returncode
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    for p in STAGING.glob("*.png"):
        p.unlink()
    STAGING.rmdir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
