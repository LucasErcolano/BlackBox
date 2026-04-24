# SPDX-License-Identifier: MIT
"""Render block_10_outro: 9.5s, 1920x1080, 30fps.

Narration (optional): "Open benchmark. Open repo. Real forensic workflow."
Must also work as a silent outro.

Quietest block of the film. Single composition, layered reveal, locked
final frame. No investigation energy, no new evidence, no diff hero.

Beats:
  A 0.0-2.0   brand fade-in: "Black Box — forensic copilot"
  B 2.0-4.5   repo + benchmark references reveal
  C 4.5-7.5   core tagline "real forensic workflow" with ACCENT underline
  D 7.5-9.5   locked hold, beat-dot indicator dims out

Ground: repo path github.com/LucasErcolano/BlackBox (from README badge);
benchmark subdir black-box-bench/ (separate MIT pkg, ../black-box-bench).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "video_assets" / "block_10_outro"
OUT.mkdir(parents=True, exist_ok=True)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

W, H = 1920, 1080
FPS = 30
DUR = 9.5
N = int(DUR * FPS)

BG = (10, 12, 16)
FG = (230, 232, 236)
DIM = (120, 128, 140)
ACCENT = (255, 184, 64)
MUTED_AMBER = (196, 150, 72)
PANEL = (18, 20, 26)
BORDER = (60, 66, 78)


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def grid_bg(img: Image.Image, alpha: float = 1.0) -> None:
    col = tuple(int(c * alpha + 10 * (1 - alpha)) for c in (18, 20, 26))
    d = ImageDraw.Draw(img)
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=col, width=1)
    for y in range(0, H, 80):
        d.line([(0, y), (W, y)], fill=col, width=1)


def draw_text_centered(d: ImageDraw.ImageDraw, xy, text, f, fill) -> None:
    bbox = d.textbbox((0, 0), text, font=f)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    d.text((xy[0] - w // 2, xy[1] - h // 2 - bbox[1]), text, font=f, fill=fill)


def text_width(f: ImageFont.FreeTypeFont, s: str) -> int:
    bbox = f.getbbox(s)
    return bbox[2] - bbox[0]


def paste_alpha(base: Image.Image, overlay: Image.Image, a: float) -> None:
    if a <= 0:
        return
    if a < 1.0:
        r, g, b, al = overlay.split()
        al = al.point(lambda v: int(v * a))
        overlay = Image.merge("RGBA", (r, g, b, al))
    base.alpha_composite(overlay, (0, 0))


def draw_beat_dots(d: ImageDraw.ImageDraw, a: float) -> None:
    if a <= 0:
        return
    cx = W // 2
    y = H - 60
    gap = 28
    total = 4 * gap
    start = cx - total // 2
    fm = font(FONT_MONO, 16)
    for i in range(4):
        x = start + i * gap
        base_col = (255, 184, 64) if i == 3 else (60, 64, 72)
        col = tuple(int(c * a + 10 * (1 - a)) for c in base_col)
        d.ellipse([(x - 6, y - 6), (x + 6, y + 6)], fill=col)
    lbl_col = tuple(int(c * a + 10 * (1 - a)) for c in (90, 96, 108))
    d.text((cx - 120, y + 18), "block 10 · outro", font=fm, fill=lbl_col)


# reveal timings (global t from 0.0):
T_BRAND = 0.2
T_WORDMARK = 1.1
T_REPO = 2.1
T_BENCH = 2.9
T_LICENSE = 3.7
T_TAGLINE = 4.7
T_ACCENT = 5.2
T_SUBT = 5.9
T_DOTS_OUT = 8.5


def reveal(t: float, t0: float, dur: float = 0.7) -> float:
    return ease((t - t0) / dur)


def render_at(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    # subtle grid, slightly dimmer than other blocks to feel quieter
    grid_bg(img, alpha=0.55)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb_hero = font(FONT_BOLD, 104)
    fb_mid = font(FONT_BOLD, 56)
    fs_sub = font(FONT_REG, 26)
    fm_path = font(FONT_MONO_BOLD, 34)
    fm_lbl = font(FONT_MONO, 20)
    fm_small = font(FONT_MONO, 18)

    # --- Hero brand ----------------------------------------------------------
    a_brand = reveal(t, T_BRAND, 0.9)
    a_wmark = reveal(t, T_WORDMARK, 0.7)

    brand_y = 240
    if a_brand > 0:
        tb_col = tuple(int(c * a_brand + 10 * (1 - a_brand)) for c in FG)
        draw_text_centered(d, (W // 2, brand_y), "Black Box", fb_hero, tb_col)

    if a_wmark > 0:
        wmark_col = tuple(int(c * a_wmark + 10 * (1 - a_wmark)) for c in DIM)
        draw_text_centered(d, (W // 2, brand_y + 90),
                           "forensic copilot for robots", fs_sub, wmark_col)

    # amber hairline under brand (reveals slowly from center)
    hl = reveal(t, T_WORDMARK + 0.1, 0.6)
    if hl > 0:
        hw = int(180 * hl)
        hl_col = tuple(int(c * hl + 10 * (1 - hl)) for c in ACCENT)
        d.rectangle([(W // 2 - hw, brand_y + 140), (W // 2 + hw, brand_y + 142)],
                    fill=hl_col)

    # --- Repo + benchmark row -----------------------------------------------
    row_y = 540
    col_gap = 60
    # two blocks side by side, centered
    repo_label = "repo"
    repo_path = "github.com/LucasErcolano/BlackBox"
    bench_label = "benchmark"
    bench_path = "black-box-bench/ · MIT"

    # measure for alignment
    repo_pw = text_width(fm_path, repo_path)
    bench_pw = text_width(fm_path, bench_path)
    col_w = max(repo_pw, bench_pw) + 80
    total_w = col_w * 2 + col_gap
    x0 = (W - total_w) // 2

    def draw_ref_col(cx_left: int, label: str, path_text: str, appear: float):
        if appear <= 0:
            return
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        # label eyebrow
        lbl_box_y = row_y
        ld.rectangle([(cx_left, lbl_box_y), (cx_left + 6, lbl_box_y + 28)],
                     fill=MUTED_AMBER)
        ld.text((cx_left + 18, lbl_box_y + 3), label,
                font=fm_lbl, fill=MUTED_AMBER)
        # path (big mono bold)
        ld.text((cx_left, lbl_box_y + 50), path_text, font=fm_path, fill=FG)
        # thin border under for groundedness
        pw = text_width(fm_path, path_text)
        ld.rectangle([(cx_left, lbl_box_y + 100), (cx_left + pw, lbl_box_y + 101)],
                     fill=BORDER)
        # fade in
        r, g, b, al = lay.split()
        al = al.point(lambda v: int(v * appear))
        lay = Image.merge("RGBA", (r, g, b, al))
        layer.alpha_composite(lay, (0, 0))

    draw_ref_col(x0, repo_label, repo_path, reveal(t, T_REPO, 0.7))
    draw_ref_col(x0 + col_w + col_gap, bench_label, bench_path,
                 reveal(t, T_BENCH, 0.7))

    # license / inspectability mini-line
    a_lic = reveal(t, T_LICENSE, 0.6)
    if a_lic > 0:
        lic_col = tuple(int(c * a_lic + 10 * (1 - a_lic)) for c in (90, 96, 108))
        draw_text_centered(d, (W // 2, row_y + 142),
                           "public · inspectable · MIT",
                           fm_small, lic_col)

    # --- Tagline -------------------------------------------------------------
    tagline_y = 820
    a_tag = reveal(t, T_TAGLINE, 0.7)
    if a_tag > 0:
        tg_col = tuple(int(c * a_tag + 10 * (1 - a_tag)) for c in FG)
        draw_text_centered(d, (W // 2, tagline_y),
                           "real forensic workflow", fb_mid, tg_col)

    a_acc = reveal(t, T_ACCENT, 0.6)
    if a_acc > 0:
        acc_w = int(240 * a_acc)
        ac_col = tuple(int(c * a_acc + 10 * (1 - a_acc)) for c in ACCENT)
        d.rectangle([(W // 2 - acc_w, tagline_y + 44),
                     (W // 2 + acc_w, tagline_y + 47)], fill=ac_col)

    a_sub = reveal(t, T_SUBT, 0.7)
    if a_sub > 0:
        sb_col = tuple(int(c * a_sub + 10 * (1 - a_sub)) for c in DIM)
        draw_text_centered(d, (W // 2, tagline_y + 82),
                           "open benchmark  ·  open repo  ·  grounded in real bags",
                           fs_sub, sb_col)

    # --- Beat dots (fade out near the end) -----------------------------------
    dots_alpha = 1.0
    if t >= T_DOTS_OUT:
        dots_alpha = 1.0 - min(1.0, (t - T_DOTS_OUT) / 0.8)
    # dots come in with brand
    dots_in = reveal(t, T_BRAND + 0.2, 0.6)
    dots_alpha *= dots_in
    draw_beat_dots(d, dots_alpha)

    # master fade-in from black over first 0.4s, no fade-out (locked frame)
    master = min(1.0, t / 0.4)
    paste_alpha(img, layer, master)

    # ambient vignette for quiet / final-card feel
    vig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vig)
    for i in range(6):
        a = int(14 - i * 2)
        vd.rectangle([(0, 0), (W, i * 6)], fill=(0, 0, 0, a))
        vd.rectangle([(0, H - i * 6), (W, H)], fill=(0, 0, 0, a))
    img.alpha_composite(vig)

    return img


def main() -> None:
    # repo-groundedness asserts
    assert (ROOT / "README.md").exists(), "README.md missing"
    assert (ROOT / "black-box-bench").is_dir(), "black-box-bench/ missing"

    tmp = Path(tempfile.mkdtemp(prefix="block10_"))
    print(f"tmp: {tmp}", file=sys.stderr)

    for k in range(N):
        t = k / FPS
        fr = render_at(t).convert("RGB")
        fr.save(tmp / f"f_{k:05d}.png", "PNG", optimize=False)
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

    # preview = the locked final frame
    render_at(DUR - 0.1).convert("RGB").save(OUT / "preview.png", "PNG", optimize=True)

    shutil.rmtree(tmp)
    print(f"wrote {out_mp4}")


if __name__ == "__main__":
    main()
