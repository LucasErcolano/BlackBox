# SPDX-License-Identifier: MIT
"""Render block_01_hook: 11s, 1920x1080, 30fps.

Narration: "When a robot fails, the recorder tells you what happened.
Black Box tells you why — and gives you the diff."

Beats:
  A 0.0-2.6  title card over dark bg
  B 2.6-5.2  raw bag frame ("what happened" / evidence)
  C 5.2-7.8  RTK plot ("why")
  D 7.8-11.0 diff panel ("the diff")

Uses real repo artifacts only. No fake UI.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "video_assets" / "block_01_hook"
OUT.mkdir(parents=True, exist_ok=True)

FRAME = ROOT / "demo_assets/bag_footage/sanfer_tunnel/frame_00133.4s_dense.jpg"
PLOT = ROOT / "demo_assets/diff_viewer/moving_base_rover.png"
PATCH = ROOT / "data/patches/054061f2c1f9.json"

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

W, H = 1920, 1080
FPS = 30
DUR = 11.0
N = int(DUR * FPS)

BG = (10, 12, 16)
FG = (230, 232, 236)
DIM = (120, 128, 140)
ACCENT = (255, 184, 64)
GREEN = (110, 200, 120)
RED = (220, 90, 90)


def ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def fade_alpha(local_t: float, dur: float, fade: float = 0.35) -> float:
    if local_t < 0 or local_t > dur:
        return 0.0
    in_a = min(1.0, local_t / fade)
    out_a = min(1.0, (dur - local_t) / fade)
    return max(0.0, min(1.0, min(in_a, out_a)))


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def paste_with_alpha(base: Image.Image, overlay: Image.Image, pos: tuple[int, int], a: float) -> None:
    if a <= 0:
        return
    if overlay.mode != "RGBA":
        overlay = overlay.convert("RGBA")
    if a < 1.0:
        r, g, b, al = overlay.split()
        al = al.point(lambda v: int(v * a))
        overlay = Image.merge("RGBA", (r, g, b, al))
    base.alpha_composite(overlay, pos)


def draw_text_centered(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((xy[0] - w // 2, xy[1] - h // 2), text, font=font, fill=fill)


def make_title_frame(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    # dim grid backdrop
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=(18, 20, 26), width=1)
    for y in range(0, H, 80):
        d.line([(0, y), (W, y)], fill=(18, 20, 26), width=1)

    a = fade_alpha(t, 2.6, 0.4)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)

    fb = load_font(FONT_BOLD, 84)
    fs = load_font(FONT_REG, 34)
    fm = load_font(FONT_MONO, 26)

    draw_text_centered(ld, (W // 2, H // 2 - 60), "When a robot fails,", fb, FG)
    draw_text_centered(ld, (W // 2, H // 2 + 40), "the recorder tells you what happened.", fs, DIM)

    ld.rectangle([(W // 2 - 180, H // 2 + 130), (W // 2 + 180, H // 2 + 134)], fill=ACCENT)

    draw_text_centered(ld, (W // 2, H - 90), "BLACK  BOX  —  forensic copilot", fm, (90, 96, 108))

    paste_with_alpha(img, layer, (0, 0), a)
    return img


def fit_cover(src: Image.Image, tw: int, th: int) -> Image.Image:
    sw, sh = src.size
    rs = max(tw / sw, th / sh)
    nw, nh = int(sw * rs), int(sh * rs)
    r = src.resize((nw, nh), Image.LANCZOS)
    x = (nw - tw) // 2
    y = (nh - th) // 2
    return r.crop((x, y, x + tw, y + th))


def fit_contain(src: Image.Image, tw: int, th: int) -> Image.Image:
    sw, sh = src.size
    rs = min(tw / sw, th / sh)
    nw, nh = int(sw * rs), int(sh * rs)
    return src.resize((nw, nh), Image.LANCZOS)


def make_frame_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)

    src = Image.open(FRAME).convert("RGBA")
    # gentle ken-burns
    u = t / 2.6
    zoom = 1.05 + 0.08 * ease(min(1.0, u))
    fw, fh = int(W * 0.72 * zoom), int(H * 0.78 * zoom)
    bg = fit_cover(src, fw, fh)
    # crop to target panel size
    pw, ph = int(W * 0.72), int(H * 0.78)
    ox = (bg.size[0] - pw) // 2
    oy = (bg.size[1] - ph) // 2
    panel = bg.crop((ox, oy, ox + pw, oy + ph))

    px, py = int(W * 0.06), int(H * 0.12)
    # shadow
    shadow = Image.new("RGBA", (pw + 40, ph + 40), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([(20, 20), (pw + 20, ph + 20)], fill=(0, 0, 0, 160))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    img.alpha_composite(shadow, (px - 20, py - 20))
    img.alpha_composite(panel, (px, py))

    # border
    ImageDraw.Draw(img).rectangle([(px, py), (px + pw, py + ph)], outline=(60, 66, 78), width=2)

    # side labels
    a = fade_alpha(t, 2.6, 0.35)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    fb = load_font(FONT_BOLD, 44)
    fs = load_font(FONT_REG, 24)
    fm = load_font(FONT_MONO, 20)

    rx = px + pw + 60
    ld.text((rx, py + 20), "RAW EVIDENCE", font=fb, fill=ACCENT)
    ld.text((rx, py + 80), "rosbag frame", font=fs, fill=FG)
    ld.text((rx, py + 120), "sanfer_tunnel / t=133.4s", font=fm, fill=DIM)

    # corner timecode on panel
    ld.rectangle([(px + 16, py + ph - 48), (px + 240, py + ph - 16)], fill=(0, 0, 0, 160))
    ld.text((px + 28, py + ph - 42), "cam0  133.4s", font=fm, fill=FG)

    # footer progress dots
    draw_beat_dots(ld, active=1)

    paste_with_alpha(img, layer, (0, 0), a)
    return img


def draw_beat_dots(ld: ImageDraw.ImageDraw, active: int) -> None:
    cx = W // 2
    y = H - 60
    gap = 28
    labels = ["title", "evidence", "why", "diff"]
    total = len(labels) * gap
    start = cx - total // 2
    fm = load_font(FONT_MONO, 16)
    for i, lab in enumerate(labels):
        x = start + i * gap
        col = ACCENT if i == active else (60, 64, 72)
        ld.ellipse([(x - 6, y - 6), (x + 6, y + 6)], fill=col)
    ld.text((cx - 80, y + 18), f"  block 01 · hook", font=fm, fill=(90, 96, 108))


def make_plot_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    src = Image.open(PLOT).convert("RGBA")
    pw, ph = int(W * 0.70), int(H * 0.74)
    fitted = fit_contain(src, pw, ph)
    fw, fh = fitted.size
    px = (W - fw) // 2 - 120
    py = (H - fh) // 2 - 30

    shadow = Image.new("RGBA", (fw + 40, fh + 40), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([(20, 20), (fw + 20, fh + 20)], fill=(0, 0, 0, 160))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    img.alpha_composite(shadow, (px - 20, py - 20))

    # white plate under plot (png may have transparency)
    plate = Image.new("RGBA", (fw, fh), (250, 250, 250, 255))
    img.alpha_composite(plate, (px, py))
    img.alpha_composite(fitted, (px, py))

    # wipe-in reveal
    u = min(1.0, t / 1.1)
    if u < 1.0:
        cover_w = int(fw * (1.0 - ease(u)))
        cover = Image.new("RGBA", (cover_w, fh), BG + (255,))
        img.alpha_composite(cover, (px + fw - cover_w, py))

    a = fade_alpha(t, 2.6, 0.35)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    fb = load_font(FONT_BOLD, 44)
    fs = load_font(FONT_REG, 24)
    fm = load_font(FONT_MONO, 20)

    rx = px + fw + 60
    ld.text((rx, py + 20), "BLACK BOX", font=fb, fill=ACCENT)
    ld.text((rx, py + 72), "tells you why.", font=fb, fill=FG)
    ld.text((rx, py + 140), "RTK heading gone.", font=fs, fill=FG)
    ld.text((rx, py + 176), "carrSoln = NONE  100%", font=fm, fill=DIM)
    ld.text((rx, py + 206), "relPosValid never set", font=fm, fill=DIM)

    draw_beat_dots(ld, active=2)
    paste_with_alpha(img, layer, (0, 0), a)
    return img


def render_diff_panel() -> Image.Image:
    data = json.loads(PATCH.read_text())
    old_lines = data["old"].splitlines()
    new_lines = data["new"].splitlines()

    fm_code = load_font(FONT_MONO, 22)
    fm_hdr = load_font(FONT_BOLD, 22)

    col_w = 780
    line_h = 30
    n_rows = max(len(old_lines), len(new_lines)) + 2
    pw = col_w * 2 + 40
    ph = line_h * n_rows + 80

    panel = Image.new("RGBA", (pw, ph), (18, 20, 26, 255))
    pd = ImageDraw.Draw(panel)

    # headers
    pd.rectangle([(0, 0), (col_w, 44)], fill=(28, 30, 36))
    pd.rectangle([(col_w + 40, 0), (pw, 44)], fill=(28, 30, 36))
    pd.text((16, 10), "before  pid_controller.cpp", font=fm_hdr, fill=(200, 150, 150))
    pd.text((col_w + 56, 10), "after   pid_controller.cpp", font=fm_hdr, fill=(150, 210, 160))

    # compute simple diff: mark new lines that are not in old
    old_set = set(l.strip() for l in old_lines)
    new_set = set(l.strip() for l in new_lines)

    y = 64
    for i, line in enumerate(old_lines):
        bg_col = (40, 20, 22) if line.strip() and line.strip() not in new_set else None
        if bg_col:
            pd.rectangle([(0, y - 4), (col_w, y + line_h - 4)], fill=bg_col)
            pd.text((6, y), "-", font=fm_code, fill=RED)
        pd.text((28, y), line, font=fm_code, fill=FG)
        y += line_h

    y = 64
    for i, line in enumerate(new_lines):
        bg_col = (20, 38, 24) if line.strip() and line.strip() not in old_set else None
        if bg_col:
            pd.rectangle([(col_w + 40, y - 4), (pw, y + line_h - 4)], fill=bg_col)
            pd.text((col_w + 46, y), "+", font=fm_code, fill=GREEN)
        pd.text((col_w + 68, y), line, font=fm_code, fill=FG)
        y += line_h

    # outer border
    pd.rectangle([(0, 0), (pw - 1, ph - 1)], outline=(60, 66, 78), width=2)
    # split gutter
    pd.rectangle([(col_w, 0), (col_w + 40, ph)], fill=(10, 12, 16))
    return panel


def make_diff_beat(t: float, diff_panel: Image.Image) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    pw, ph = diff_panel.size
    scale = min((W - 240) / pw, (H - 260) / ph)
    nw, nh = int(pw * scale), int(ph * scale)
    scaled = diff_panel.resize((nw, nh), Image.LANCZOS)
    px = (W - nw) // 2
    py = (H - nh) // 2 - 10

    shadow = Image.new("RGBA", (nw + 40, nh + 40), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([(20, 20), (nw + 20, nh + 20)], fill=(0, 0, 0, 180))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    img.alpha_composite(shadow, (px - 20, py - 20))
    img.alpha_composite(scaled, (px, py))

    # top label
    a = fade_alpha(t, 3.2, 0.35)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    fb = load_font(FONT_BOLD, 54)
    fs = load_font(FONT_REG, 26)
    draw_text_centered(ld, (W // 2, 70), "…and gives you the diff.", fb, FG)
    draw_text_centered(ld, (W // 2, 118), "scoped patch · data/patches/054061f2c1f9.json", fs, DIM)

    # spotlight sweep on the clamp lines (highlight between y=py+84 and py+84+2*line)
    u = min(1.0, max(0.0, (t - 0.4) / 1.4))
    if u > 0:
        hl = Image.new("RGBA", (nw, int(64 * scale)), (255, 184, 64, int(60 * ease(u))))
        hl_y = py + int((44 + 30 * 2) * scale)  # around integral clamp line
        img.alpha_composite(hl, (px, hl_y))

    draw_beat_dots(ld, active=3)
    paste_with_alpha(img, layer, (0, 0), a)
    return img


def crossfade(a: Image.Image, b: Image.Image, u: float) -> Image.Image:
    return Image.blend(a, b, u)


def main() -> None:
    diff_panel = render_diff_panel()

    tmp = Path(tempfile.mkdtemp(prefix="block01_"))
    print(f"tmp: {tmp}", file=sys.stderr)

    seg_bounds = [(0.0, 2.6), (2.6, 5.2), (5.2, 7.8), (7.8, 11.0)]
    xfade = 0.35

    def render_at(t_abs: float) -> Image.Image:
        # find which segment(s)
        for i, (s, e) in enumerate(seg_bounds):
            if s <= t_abs < e:
                local = t_abs - s
                base = _render_seg(i, local, diff_panel)
                # crossfade into next segment near boundary
                if i + 1 < len(seg_bounds) and (e - t_abs) < xfade:
                    u = 1.0 - (e - t_abs) / xfade
                    nxt = _render_seg(i + 1, t_abs - seg_bounds[i + 1][0], diff_panel)
                    return crossfade(base, nxt, ease(u))
                return base
        return _render_seg(len(seg_bounds) - 1, t_abs - seg_bounds[-1][0], diff_panel)

    for k in range(N):
        t = k / FPS
        frame = render_at(t).convert("RGB")
        frame.save(tmp / f"f_{k:05d}.png", "PNG", optimize=False)
        if k % 30 == 0:
            print(f"frame {k}/{N}", file=sys.stderr)

    out_mp4 = OUT / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-framerate", str(FPS),
            "-i", str(tmp / "f_%05d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "medium", "-crf", "18",
            "-movflags", "+faststart",
            str(out_mp4),
        ],
        check=True,
    )

    # preview = hero still of diff beat
    preview = render_at(9.2).convert("RGB")
    preview.save(OUT / "preview.png", "PNG", optimize=True)

    shutil.rmtree(tmp)
    print(f"wrote {out_mp4}")


def _render_seg(i: int, local_t: float, diff_panel: Image.Image) -> Image.Image:
    if i == 0:
        return make_title_frame(local_t)
    if i == 1:
        return make_frame_beat(local_t)
    if i == 2:
        return make_plot_beat(local_t)
    return make_diff_beat(local_t, diff_panel)


if __name__ == "__main__":
    main()
