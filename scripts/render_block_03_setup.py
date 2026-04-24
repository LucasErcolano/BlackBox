# SPDX-License-Identifier: MIT
"""Render block_03_setup: 14.5s, 1920x1080, 30fps.

Narration: "I give Black Box sessions it has never seen. No labels. No
handcrafted rubric. Just raw evidence. Its job is simple: find what matters,
reject what doesn't, and return a grounded hypothesis."

Intake beat. Multi-session: two real sessions (boat_lidar + sanfer_tunnel)
enter the workflow -> raw evidence modalities per session -> negate
labels/rubric -> final "find what matters" lockup.

Bridges block_02_problem (evidence overload) into blocks_05/_06 (findings).
Narrower and more controlled than 02; anticipatory, does not reveal findings.

Visual identity continuous with blocks 01/02/05/06/07/08/09/10:
  - same BG/FG/DIM palette, DejaVu fonts, 80px grid, drop-shadow, 4-dot dots
  - ACCENT amber used only on hairlines, eyebrows, strike dissolves, lockup
  - XFADE 0.40 between beats (between block_02's 0.35 and block_07's 0.45)
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
OUT = ROOT / "video_assets" / "block_03_setup"
OUT.mkdir(parents=True, exist_ok=True)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

W, H = 1920, 1080
FPS = 30
DUR = 14.5
N = int(DUR * FPS)

BG = (10, 12, 16)
FG = (230, 232, 236)
DIM = (120, 128, 140)
PANEL = (18, 20, 26)
BORDER = (60, 66, 78)
ACCENT = (255, 184, 64)
MUTED_AMBER = (196, 150, 72)
MUTED_RED = (170, 86, 86)
STRIKE = (90, 94, 100)

BOAT_SUMMARY = ROOT / "data/final_runs/boat_lidar/bundle/summary.json"
SANFER_SUMMARY = ROOT / "data/final_runs/sanfer_tunnel/bundle/summary.json"
SANFER_FRAMES = ROOT / "data/final_runs/sanfer_tunnel/bundle/frames"

SEG_BOUNDS = [(0.0, 3.0), (3.0, 6.4), (6.4, 10.4), (10.4, 14.5)]
XFADE = 0.40


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def fade_alpha(local_t: float, dur: float, fade: float = 0.5) -> float:
    if local_t < 0 or local_t > dur:
        return 0.0
    in_a = min(1.0, local_t / fade)
    out_a = min(1.0, (dur - local_t) / fade)
    return max(0.0, min(1.0, min(in_a, out_a)))


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def grid_bg(img: Image.Image, alpha: float = 1.0) -> None:
    col = tuple(int(c * alpha + 10 * (1 - alpha)) for c in (18, 20, 26))
    d = ImageDraw.Draw(img)
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=col, width=1)
    for y in range(0, H, 80):
        d.line([(0, y), (W, y)], fill=col, width=1)


def paste_alpha(base: Image.Image, overlay: Image.Image, pos: tuple[int, int], a: float) -> None:
    if a <= 0:
        return
    if overlay.mode != "RGBA":
        overlay = overlay.convert("RGBA")
    if a < 1.0:
        r, g, b, al = overlay.split()
        al = al.point(lambda v: int(v * a))
        overlay = Image.merge("RGBA", (r, g, b, al))
    base.alpha_composite(overlay, pos)


def draw_text_centered(d: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, f, fill) -> None:
    bbox = d.textbbox((0, 0), text, font=f)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    d.text((xy[0] - w // 2, xy[1] - h // 2 - bbox[1]), text, font=f, fill=fill)


def text_width(f: ImageFont.FreeTypeFont, s: str) -> int:
    bbox = f.getbbox(s)
    return bbox[2] - bbox[0]


def draw_beat_dots(d: ImageDraw.ImageDraw, active: int) -> None:
    cx = W // 2
    y = H - 60
    gap = 28
    total = 4 * gap
    start = cx - total // 2
    fm = font(FONT_MONO, 16)
    for i in range(4):
        x = start + i * gap
        col = ACCENT if i == active else (60, 64, 72)
        d.ellipse([(x - 6, y - 6), (x + 6, y + 6)], fill=col)
    d.text((cx - 110, y + 18), "  block 03 · setup", font=fm, fill=(90, 96, 108))


def shadow_for(w: int, h: int, pad: int = 20, alpha: int = 140, blur: int = 18) -> Image.Image:
    sh = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([(pad, pad), (w + pad, h + pad)], fill=(0, 0, 0, alpha))
    return sh.filter(ImageFilter.GaussianBlur(blur))


# ---- Load real session data ----------------------------------------------

assert BOAT_SUMMARY.exists(), f"missing: {BOAT_SUMMARY}"
assert SANFER_SUMMARY.exists(), f"missing: {SANFER_SUMMARY}"
BOAT = json.loads(BOAT_SUMMARY.read_text())
SANFER = json.loads(SANFER_SUMMARY.read_text())

BOAT_DUR = BOAT["duration_s"]
SANFER_DUR = SANFER["session_duration_s"]

SANFER_FRAME_PICKS = [
    "frame_00000.0s_dense.jpg",
    "frame_01036.3s_base.jpg",
    "frame_02072.5s_base.jpg",
]


# ---- Beat A: unseen sessions (directory listing) --------------------------


def make_intake_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 3.0, 0.45)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 42)
    fs = font(FONT_REG, 24)
    fm = font(FONT_MONO, 24)
    fm_b = font(FONT_MONO_BOLD, 26)

    d.text((260, 80), "Unseen sessions", font=fb, fill=FG)
    d.text((260, 136), "real recordings handed in · not previously analyzed",
           font=fs, fill=DIM)
    d.rectangle([(260, 180), (420, 182)], fill=ACCENT)

    card_w = 1200
    card_h = 520
    cx = (W - card_w) // 2
    cy = 260
    card = Image.new("RGBA", (card_w, card_h), PANEL + (255,))
    cd = ImageDraw.Draw(card)
    cd.rectangle([(0, 0), (card_w - 1, card_h - 1)], outline=BORDER, width=2)
    cd.rectangle([(0, 0), (card_w, 54)], fill=(28, 30, 36))
    cd.text((20, 14), "$ ls data/final_runs/", font=fm_b, fill=FG)

    # two real intake directories, revealed in order
    entries = [
        ("boat_lidar/", "USV · LIDAR-only · 7m", 0.7),
        ("sanfer_tunnel/", "Lincoln MKZ · RTK · 60m", 1.2),
    ]
    y = 100
    for i, (name, desc, tr) in enumerate(entries):
        ea = fade_alpha(t - tr, 3.0 - tr, 0.35)
        if ea <= 0:
            continue
        row = Image.new("RGBA", (card_w, 140), (0, 0, 0, 0))
        rd = ImageDraw.Draw(row)
        # folder line
        rd.rectangle([(28, 18), (34, 118)], fill=ACCENT)
        rd.text((60, 20), f"drwxr-xr-x  {name}", font=fm_b, fill=FG)
        rd.text((60, 60), desc, font=fm, fill=DIM)
        rd.rectangle([(60, 100), (60 + 520, 102)], fill=BORDER)
        paste_alpha(card, row, (0, y), ea)
        y += 150

    # UNSEEN tag
    tag_w, tag_h = 300, 70
    tx = card_w - tag_w - 28
    ty = card_h - tag_h - 28
    cd.rectangle([(tx, ty), (tx + tag_w, ty + tag_h)], outline=ACCENT, width=2)
    cd.text((tx + 16, ty + 10), "UNSEEN", font=fm_b, fill=ACCENT)
    cd.text((tx + 16, ty + 40), "no prior labels", font=fm, fill=DIM)

    sh = shadow_for(card_w, card_h)
    img.alpha_composite(sh, (cx - 20, cy - 20))
    paste_alpha(img, card, (cx, cy), 1.0)

    draw_beat_dots(d, active=0)
    paste_alpha(img, layer, (0, 0), a)
    return img


# ---- Beat B: isolate the two sessions (side by side) ----------------------


def _session_card(title: str, subtitle: str, rows: list[tuple[str, str]],
                  w: int, h: int, accent_col: tuple[int, int, int]) -> Image.Image:
    card = Image.new("RGBA", (w, h), PANEL + (255,))
    cd = ImageDraw.Draw(card)
    cd.rectangle([(0, 0), (w - 1, h - 1)], outline=BORDER, width=2)
    cd.rectangle([(0, 0), (w, 56)], fill=(28, 30, 36))
    fm_b = font(FONT_MONO_BOLD, 24)
    fl = font(FONT_BOLD, 44)
    fm = font(FONT_MONO, 22)
    cd.text((20, 14), "session_manifest.json", font=fm_b, fill=FG)
    cd.text((28, 86), "case", font=fm, fill=DIM)
    cd.text((28, 120), title, font=fl, fill=FG)
    cd.rectangle([(28, 178), (160, 180)], fill=accent_col)
    cd.text((28, 196), subtitle, font=fm, fill=DIM)
    y = 258
    for k, v in rows:
        cd.text((28, y), k, font=fm, fill=DIM)
        cd.text((190, y), v, font=fm, fill=FG)
        y += 36
    return card


def make_sessions_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 3.4, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 42)
    fs = font(FONT_REG, 24)

    d.text((260, 80), "Two sessions in", font=fb, fill=FG)
    d.text((260, 136), "different platforms · different sensors · same intake",
           font=fs, fill=DIM)
    d.rectangle([(260, 180), (420, 182)], fill=ACCENT)

    card_w, card_h = 760, 560
    gap = 80
    total = card_w * 2 + gap
    x0 = (W - total) // 2
    cy = 240

    boat_mins = int(BOAT_DUR // 60)
    boat_secs = int(BOAT_DUR - boat_mins * 60)
    sanfer_mins = int(SANFER_DUR // 60)
    sanfer_secs = int(SANFER_DUR - sanfer_mins * 60)

    boat_rows = [
        ("duration", f"{boat_mins}m {boat_secs:02d}s"),
        ("platform", "USV · LIDAR-only"),
        ("sensors", "/lidar_points · /lidar_imu"),
        ("prior labels", "none"),
        ("prior rubric", "none"),
    ]
    sanfer_rows = [
        ("duration", f"{sanfer_mins}m {sanfer_secs:02d}s"),
        ("platform", "Lincoln MKZ · RTK"),
        ("sensors", "u-blox · IMU · cameras"),
        ("prior labels", "none"),
        ("prior rubric", "none"),
    ]
    boat_card = _session_card("boat_lidar", "unmanned surface vessel",
                              boat_rows, card_w, card_h, ACCENT)
    sanfer_card = _session_card("sanfer_tunnel", "autonomous vehicle · dual-antenna RTK",
                                sanfer_rows, card_w, card_h, ACCENT)

    a1 = fade_alpha(t - 0.15, 3.4 - 0.15, 0.35)
    a2 = fade_alpha(t - 0.55, 3.4 - 0.55, 0.35)
    sh = shadow_for(card_w, card_h)
    img.alpha_composite(sh, (x0 - 20, cy - 20))
    img.alpha_composite(sh, (x0 + card_w + gap - 20, cy - 20))
    paste_alpha(img, boat_card, (x0, cy), a1)
    paste_alpha(img, sanfer_card, (x0 + card_w + gap, cy), a2)

    # connective eyebrow
    a3 = fade_alpha(t - 1.2, 3.4 - 1.2, 0.3)
    if a3 > 0:
        tag_l = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        td = ImageDraw.Draw(tag_l)
        fm_b = font(FONT_MONO_BOLD, 22)
        draw_text_centered(td, (W // 2, cy + card_h + 48),
                           "two cases · unseen · no prior analysis", fm_b, MUTED_AMBER)
        paste_alpha(img, tag_l, (0, 0), a3)

    draw_beat_dots(d, active=1)
    paste_alpha(img, layer, (0, 0), a)
    return img


# ---- Beat C: raw evidence modalities per session --------------------------

_FRAME_CACHE: dict[str, Image.Image] = {}


def load_frame(name: str, size: tuple[int, int]) -> Image.Image:
    key = f"{name}:{size[0]}x{size[1]}"
    if key in _FRAME_CACHE:
        return _FRAME_CACHE[key]
    p = SANFER_FRAMES / name
    im = Image.open(p).convert("RGB")
    im.thumbnail((size[0] * 2, size[1] * 2))
    im = im.resize(size, Image.LANCZOS)
    _FRAME_CACHE[key] = im
    return im


def _pill(label: str, name: str, w: int = 340, h: int = 64,
          strip: tuple[int, int, int] = MUTED_AMBER) -> Image.Image:
    fm_b = font(FONT_MONO_BOLD, 20)
    fm = font(FONT_MONO, 18)
    p = Image.new("RGBA", (w, h), PANEL + (255,))
    pd = ImageDraw.Draw(p)
    pd.rectangle([(0, 0), (w - 1, h - 1)], outline=BORDER, width=2)
    pd.rectangle([(0, 0), (6, h)], fill=strip)
    pd.text((18, 8), label, font=fm_b, fill=FG)
    pd.text((18, 34), name, font=fm, fill=DIM)
    return p


def make_evidence_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 4.0, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 42)
    fs = font(FONT_REG, 24)
    fm_b = font(FONT_MONO_BOLD, 22)
    fm = font(FONT_MONO, 20)

    d.text((260, 80), "Raw evidence", font=fb, fill=FG)
    d.text((260, 136), "no curation · no pre-sorting · only what the sessions carry",
           font=fs, fill=DIM)
    d.rectangle([(260, 180), (420, 182)], fill=ACCENT)

    # two columns, one per session
    col_w = 780
    gap = 80
    total = col_w * 2 + gap
    x0 = (W - total) // 2
    top_y = 240

    # column headers
    d.text((x0, top_y), "boat_lidar", font=fm_b, fill=MUTED_AMBER)
    d.text((x0 + 200, top_y + 2), "LIDAR-only · metadata recovery", font=fm, fill=DIM)
    d.text((x0 + col_w + gap, top_y), "sanfer_tunnel", font=fm_b, fill=MUTED_AMBER)
    d.text((x0 + col_w + gap + 210, top_y + 2), "RTK · IMU · cameras", font=fm, fill=DIM)
    d.rectangle([(x0, top_y + 34), (x0 + col_w, top_y + 35)], fill=BORDER)
    d.rectangle([(x0 + col_w + gap, top_y + 34), (x0 + col_w + gap + col_w, top_y + 35)], fill=BORDER)

    # -- boat column: pills only (no frames — lidar-only session)
    boat_pills = [
        ("metadata.yaml", "topics · counts · recovery"),
        ("/lidar_points", "4168 msgs · 10 Hz"),
        ("/lidar_imu", "0 msgs · silent stream"),
        ("bag_recovery_note", "sqlite3 malformed · reason from metadata"),
    ]
    py = top_y + 70
    for i, (label, name) in enumerate(boat_pills):
        tr = 0.25 + i * 0.18
        pa = fade_alpha(t - tr, 4.0 - tr, 0.3)
        if pa <= 0:
            continue
        strip = MUTED_RED if i == 2 else MUTED_AMBER  # IMU silence gets red strip
        pill = _pill(label, name, w=col_w - 40, h=72, strip=strip)
        paste_alpha(img, pill, (x0 + 20, py), pa)
        py += 82

    # -- sanfer column: 3 frame tiles + pills
    sx = x0 + col_w + gap + 20
    sy = top_y + 70
    tile_w = (col_w - 40 - 32) // 3
    tile_h = 124
    for i, fname in enumerate(SANFER_FRAME_PICKS):
        tr = 0.35 + i * 0.15
        ta = fade_alpha(t - tr, 4.0 - tr, 0.3)
        if ta <= 0:
            continue
        fr = load_frame(fname, (tile_w, tile_h))
        tile = Image.new("RGBA", (tile_w, tile_h + 2), PANEL + (255,))
        td = ImageDraw.Draw(tile)
        tile.paste(fr, (0, 0))
        td.rectangle([(0, 0), (tile_w - 1, tile_h + 1)], outline=BORDER, width=2)
        paste_alpha(img, tile, (sx + i * (tile_w + 16), sy), ta)

    # sanfer pills below frames
    sanfer_pills = [
        ("ublox_rover_navrelposned.csv", "RTK rel-pos · 18,133 rows"),
        ("ublox_rover_navpvt.csv", "fix_type history"),
        ("diagnostics_nonzero_unique.csv", "non-OK diagnostics"),
    ]
    py2 = sy + tile_h + 28
    for i, (label, name) in enumerate(sanfer_pills):
        tr = 0.95 + i * 0.14
        pa = fade_alpha(t - tr, 4.0 - tr, 0.28)
        if pa <= 0:
            continue
        pill = _pill(label, name, w=col_w - 40, h=66, strip=MUTED_AMBER)
        paste_alpha(img, pill, (sx, py2), pa)
        py2 += 76

    # footer
    fa = fade_alpha(t - 1.8, 4.0 - 1.8, 0.3)
    if fa > 0:
        ftr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fd = ImageDraw.Draw(ftr)
        draw_text_centered(fd, (W // 2, H - 160),
                           "raw artifacts · per session · nothing merged, nothing curated",
                           fm, DIM)
        paste_alpha(img, ftr, (0, 0), fa)

    draw_beat_dots(d, active=2)
    paste_alpha(img, layer, (0, 0), a)
    return img


# ---- Beat D: negation + final lockup --------------------------------------


def make_lockup_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 4.1, 0.55)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb_big = font(FONT_BOLD, 96)
    fm_neg = font(FONT_MONO_BOLD, 38)
    fs = font(FONT_REG, 28)
    fm = font(FONT_MONO, 22)

    phase_swap = 2.1
    if t < phase_swap:
        neg_a = fade_alpha(t, phase_swap, 0.4)
        neg_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        nd = ImageDraw.Draw(neg_layer)

        lines = [
            ("no labels", H // 2 - 100),
            ("no handcrafted rubric", H // 2 + 10),
        ]
        for i, (text, y) in enumerate(lines):
            draw_text_centered(nd, (W // 2, y), text, fm_neg, STRIKE)
            tw = text_width(fm_neg, text)
            appear_t = 0.2 + i * 0.4
            if t >= appear_t + 0.25:
                nd.line(
                    [(W // 2 - tw // 2 - 14, y), (W // 2 + tw // 2 + 14, y)],
                    fill=MUTED_RED,
                    width=3,
                )

        draw_text_centered(nd, (W // 2, H // 2 + 180),
                           "the system starts from raw evidence", fs, DIM)
        paste_alpha(layer, neg_layer, (0, 0), neg_a)
    else:
        u = ease(min(1.0, (t - phase_swap) / 0.5))
        draw_text_centered(d, (W // 2, H // 2 - 60), "find what matters.", fb_big, FG)
        d.rectangle(
            [(W // 2 - 180, H // 2 + 40), (W // 2 + 180, H // 2 + 43)],
            fill=ACCENT,
        )
        draw_text_centered(d, (W // 2, H // 2 + 100),
                           "reject what doesn't · return a grounded hypothesis",
                           fs, DIM)
        paste_alpha(img, layer, (0, 0), a * u)
        brand_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bd = ImageDraw.Draw(brand_layer)
        draw_text_centered(bd, (W // 2, H - 120),
                           "BLACK  BOX  —  forensic copilot", fm, (90, 96, 108))
        draw_beat_dots(bd, active=3)
        paste_alpha(img, brand_layer, (0, 0), a * u)
        return img

    draw_beat_dots(d, active=3)
    paste_alpha(img, layer, (0, 0), a)
    return img


# ---- Render ---------------------------------------------------------------


def crossfade(a: Image.Image, b: Image.Image, u: float) -> Image.Image:
    return Image.blend(a, b, u)


def _seg(i: int, local_t: float) -> Image.Image:
    if i == 0:
        return make_intake_beat(local_t)
    if i == 1:
        return make_sessions_beat(local_t)
    if i == 2:
        return make_evidence_beat(local_t)
    return make_lockup_beat(local_t)


def render_at(t: float) -> Image.Image:
    for i, (s, e) in enumerate(SEG_BOUNDS):
        if s <= t < e:
            base = _seg(i, t - s)
            if i + 1 < len(SEG_BOUNDS) and (e - t) < XFADE:
                u = 1.0 - (e - t) / XFADE
                nxt = _seg(i + 1, t - SEG_BOUNDS[i + 1][0])
                return crossfade(base, nxt, ease(u))
            return base
    return _seg(len(SEG_BOUNDS) - 1, t - SEG_BOUNDS[-1][0])


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="block03_"))
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

    preview = render_at(8.2).convert("RGB")
    preview.save(OUT / "preview.png", "PNG", optimize=True)

    shutil.rmtree(tmp)
    print(f"wrote {out_mp4}")


if __name__ == "__main__":
    main()
