# SPDX-License-Identifier: MIT
"""Render block_03_setup: 14.5s, 1920x1080, 30fps.

Narration: "I give Black Box one session it has never seen before. No labels.
No handcrafted rubric. Just raw evidence. Its job is simple: find what matters,
reject what doesn't, and return a grounded hypothesis."

Intake beat. Single real session -> raw evidence -> negate labels/rubric ->
final "find what matters" lockup.

Visual identity continuous with blocks 01/02/07/08:
  - same BG/FG/DIM palette, DejaVu fonts, 80px grid, drop-shadow, 4-dot dots
  - ACCENT amber (255,184,64) used with restraint (between 02's energy and 07's austerity)
  - XFADE 0.38 — between block_02 (0.35) and block_07 (0.45)
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
MUTED_RED = (170, 86, 86)
STRIKE = (90, 94, 100)

SESSION_ROOT = "data/final_runs/sanfer_tunnel/"
SUMMARY_PATH = ROOT / "data/final_runs/sanfer_tunnel/bundle/summary.json"
FRAMES_DIR = ROOT / "data/final_runs/sanfer_tunnel/bundle/frames"

SEG_BOUNDS = [(0.0, 3.2), (3.2, 6.8), (6.8, 10.8), (10.8, 14.5)]
XFADE = 0.38


def ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def fade_alpha(local_t: float, dur: float, fade: float = 0.5) -> float:
    if local_t < 0 or local_t > dur:
        return 0.0
    in_a = min(1.0, local_t / fade)
    out_a = min(1.0, (dur - local_t) / fade)
    return max(0.0, min(1.0, min(in_a, out_a)))


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def grid_bg(img: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=(18, 20, 26), width=1)
    for y in range(0, H, 80):
        d.line([(0, y), (W, y)], fill=(18, 20, 26), width=1)


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
    d.text((xy[0] - w // 2, xy[1] - h // 2), text, font=f, fill=fill)


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

assert SUMMARY_PATH.exists(), f"missing real session summary: {SUMMARY_PATH}"
SUMMARY = json.loads(SUMMARY_PATH.read_text())
CASE = SUMMARY["case"]
DURATION_S = SUMMARY["session_duration_s"]
PLATFORM = SUMMARY["vehicle_platform"]
ARTIFACTS = SUMMARY["artifacts"]

FRAME_PICKS = [
    "frame_00000.0s_dense.jpg",
    "frame_00518.2s_base.jpg",
    "frame_01036.3s_base.jpg",
    "frame_02072.5s_base.jpg",
]
CSV_PICKS = [
    ("ublox_rover_navrelposned.csv", "RTK rel-pos"),
    ("diagnostics_nonzero_unique.csv", "diagnostics"),
    ("rosout_warnings.csv", "rosout warnings"),
    ("imu_1hz.csv", "IMU"),
    ("twist_20hz.csv", "twist"),
    ("steering_20hz.csv", "steering"),
]


# ---- Beat A: session folder surfaces --------------------------------------


def make_folder_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 3.2, 0.45)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 42)
    fs = font(FONT_REG, 24)
    fm = font(FONT_MONO, 22)
    fm_b = font(FONT_MONO_BOLD, 24)

    d.text((260, 80), "Session handed in", font=fb, fill=FG)
    d.text((260, 136), "one real recording · not previously analyzed", font=fs, fill=DIM)
    d.rectangle([(260, 180), (420, 182)], fill=ACCENT)

    # terminal-like listing card
    card_w = 1200
    card_h = 560
    cx = (W - card_w) // 2
    cy = 230
    card = Image.new("RGBA", (card_w, card_h), PANEL + (255,))
    cd = ImageDraw.Draw(card)
    cd.rectangle([(0, 0), (card_w - 1, card_h - 1)], outline=BORDER, width=2)
    cd.rectangle([(0, 0), (card_w, 52)], fill=(28, 30, 36))
    cd.text((20, 14), f"$ ls {SESSION_ROOT}bundle/", font=fm_b, fill=FG)

    # staggered reveal of listing
    reveal_n = min(14, max(0, int((t - 0.6) / 0.12)))
    entries: list[tuple[str, tuple[int, int, int]]] = [
        ("drwxr-xr-x  frames/                  184 files", FG),
        ("-rw-r--r--  ublox_rover_navrelposned.csv", FG),
        ("-rw-r--r--  ublox_rover_navpvt.csv", FG),
        ("-rw-r--r--  ublox_rover_navstatus.csv", FG),
        ("-rw-r--r--  ublox_moving_base_navpvt.csv", FG),
        ("-rw-r--r--  ublox_moving_base_navstatus.csv", FG),
        ("-rw-r--r--  diagnostics_nonzero_unique.csv", FG),
        ("-rw-r--r--  rosout_warnings.csv", FG),
        ("-rw-r--r--  gps_fix.csv", FG),
        ("-rw-r--r--  imu_1hz.csv", FG),
        ("-rw-r--r--  twist_20hz.csv", FG),
        ("-rw-r--r--  steering_20hz.csv", FG),
        ("-rw-r--r--  throttle_20hz.csv", FG),
        ("-rw-r--r--  brake_20hz.csv", FG),
    ]
    y = 86
    for i, (text, col) in enumerate(entries):
        if i >= reveal_n:
            break
        cd.text((32, y), text, font=fm, fill=col)
        y += 32

    # right-side badge
    badge_w, badge_h = 300, 84
    bx = card_w - badge_w - 28
    by = 72
    cd.rectangle([(bx, by), (bx + badge_w, by + badge_h)], outline=ACCENT, width=2)
    cd.text((bx + 18, by + 10), "UNSEEN", font=fm_b, fill=ACCENT)
    cd.text((bx + 18, by + 44), "no prior analysis", font=fm, fill=DIM)

    sh = shadow_for(card_w, card_h)
    img.alpha_composite(sh, (cx - 20, cy - 20))
    paste_alpha(img, card, (cx, cy), 1.0)

    draw_beat_dots(d, active=0)
    paste_alpha(img, layer, (0, 0), a)
    return img


# ---- Beat B: single case lockup -------------------------------------------


def make_single_case_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 3.6, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 42)
    fs = font(FONT_REG, 24)
    fm = font(FONT_MONO, 26)
    fm_b = font(FONT_MONO_BOLD, 30)
    fl = font(FONT_BOLD, 64)

    d.text((260, 80), "Single case in", font=fb, fill=FG)
    d.text((260, 136), "isolated from the rest of the fleet", font=fs, fill=DIM)
    d.rectangle([(260, 180), (420, 182)], fill=ACCENT)

    # hero case card
    card_w = 1200
    card_h = 460
    cx = (W - card_w) // 2
    cy = 260
    card = Image.new("RGBA", (card_w, card_h), PANEL + (255,))
    cd = ImageDraw.Draw(card)
    cd.rectangle([(0, 0), (card_w - 1, card_h - 1)], outline=BORDER, width=2)
    cd.rectangle([(0, 0), (card_w, 56)], fill=(28, 30, 36))
    cd.text((20, 14), "case_manifest.json", font=fm_b, fill=FG)

    # big case id
    cd.text((44, 90), "case", font=fm, fill=DIM)
    cd.text((44, 126), CASE, font=fl, fill=FG)
    cd.rectangle([(44, 200), (200, 202)], fill=ACCENT)

    # key facts
    mins = int(DURATION_S // 60)
    secs = int(DURATION_S - mins * 60)
    rows = [
        ("duration", f"{mins}m {secs:02d}s  ({DURATION_S:.1f}s)"),
        ("platform", PLATFORM),
        ("artifacts", f"{len(ARTIFACTS)} files (CSV telemetry + JPEG frames)"),
        ("prior labels", "none"),
        ("prior rubric", "none"),
    ]
    y = 230
    for k, v in rows:
        cd.text((44, y), k, font=fm, fill=DIM)
        cd.text((260, y), v, font=fm, fill=FG)
        y += 42

    sh = shadow_for(card_w, card_h)
    img.alpha_composite(sh, (cx - 20, cy - 20))
    paste_alpha(img, card, (cx, cy), 1.0)

    draw_beat_dots(d, active=1)
    paste_alpha(img, layer, (0, 0), a)
    return img


# ---- Beat C: raw evidence modalities --------------------------------------

_FRAME_CACHE: dict[str, Image.Image] = {}


def load_frame(name: str, size: tuple[int, int]) -> Image.Image:
    key = f"{name}:{size[0]}x{size[1]}"
    if key in _FRAME_CACHE:
        return _FRAME_CACHE[key]
    p = FRAMES_DIR / name
    im = Image.open(p).convert("RGB")
    im.thumbnail((size[0] * 2, size[1] * 2))
    im = im.resize(size, Image.LANCZOS)
    _FRAME_CACHE[key] = im
    return im


def make_evidence_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 4.0, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 42)
    fs = font(FONT_REG, 24)
    fm = font(FONT_MONO, 20)
    fm_b = font(FONT_MONO_BOLD, 22)

    d.text((260, 80), "Raw evidence", font=fb, fill=FG)
    d.text((260, 136), "no curation · no pre-sorting · same case only",
           font=fs, fill=DIM)
    d.rectangle([(260, 180), (420, 182)], fill=ACCENT)

    # 4 frame tiles across top
    tile_w, tile_h = 340, 192
    gap = 36
    row_w = 4 * tile_w + 3 * gap
    start_x = (W - row_w) // 2
    top_y = 240
    for i, fname in enumerate(FRAME_PICKS):
        reveal_t = 0.25 + i * 0.18
        ta = fade_alpha(t - reveal_t, 4.0 - reveal_t, 0.35)
        if ta <= 0:
            continue
        frame = load_frame(fname, (tile_w, tile_h))
        tile = Image.new("RGBA", (tile_w, tile_h + 48), PANEL + (255,))
        td = ImageDraw.Draw(tile)
        tile.paste(frame, (0, 0))
        td.rectangle([(0, 0), (tile_w - 1, tile_h + 47)], outline=BORDER, width=2)
        td.text((12, tile_h + 14), fname, font=fm, fill=DIM)
        x = start_x + i * (tile_w + gap)
        sh = shadow_for(tile_w, tile_h + 48, alpha=120, blur=14)
        img.alpha_composite(sh, (x - 20, top_y - 20))
        paste_alpha(img, tile, (x, top_y), ta)

    # CSV pills row below
    pill_row_y = top_y + tile_h + 48 + 56
    d.text((start_x, pill_row_y - 42), "telemetry streams", font=fm_b, fill=DIM)
    pill_x = start_x
    for i, (name, label) in enumerate(CSV_PICKS):
        reveal_t = 1.0 + i * 0.12
        ta = fade_alpha(t - reveal_t, 4.0 - reveal_t, 0.3)
        if ta <= 0:
            pill_x += 0
            continue
        pw = 40 + 14 + 8 * len(name)
        pw = max(260, min(360, pw))
        ph = 64
        pill = Image.new("RGBA", (pw, ph), PANEL + (255,))
        pd = ImageDraw.Draw(pill)
        pd.rectangle([(0, 0), (pw - 1, ph - 1)], outline=BORDER, width=2)
        pd.rectangle([(0, 0), (6, ph)], fill=ACCENT)
        pd.text((20, 8), label, font=fm_b, fill=FG)
        pd.text((20, 34), name, font=fm, fill=DIM)
        paste_alpha(img, pill, (pill_x, pill_row_y), ta)
        pill_x += pw + 14
        if pill_x + 260 > start_x + row_w:
            pill_x = start_x
            pill_row_y += ph + 14

    # right-side case tag
    tag_fm = font(FONT_MONO_BOLD, 22)
    d.text((start_x, H - 180), f"all artifacts · one case · {CASE}", font=tag_fm, fill=DIM)

    draw_beat_dots(d, active=2)
    paste_alpha(img, layer, (0, 0), a)
    return img


# ---- Beat D: negation + final lockup --------------------------------------


def make_lockup_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 3.7, 0.55)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb_big = font(FONT_BOLD, 96)
    fm_neg = font(FONT_MONO_BOLD, 34)
    fs = font(FONT_REG, 28)
    fm = font(FONT_MONO, 22)

    # sub-beat: first show two "no X" lines with strike, then dissolve into find-what-matters
    phase_swap = 1.9
    if t < phase_swap:
        neg_a = fade_alpha(t, phase_swap, 0.4)
        neg_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        nd = ImageDraw.Draw(neg_layer)

        lines = [
            ("no labels", H // 2 - 90),
            ("no handcrafted rubric", H // 2 + 20),
        ]
        for i, (text, y) in enumerate(lines):
            col = STRIKE if i < 2 else FG
            draw_text_centered(nd, (W // 2, y), text, fm_neg, col)
            bbox = nd.textbbox((0, 0), text, font=fm_neg)
            tw = bbox[2] - bbox[0]
            appear_t = 0.2 + i * 0.35
            if t >= appear_t + 0.25:
                sy = y
                nd.line(
                    [(W // 2 - tw // 2 - 10, sy), (W // 2 + tw // 2 + 10, sy)],
                    fill=MUTED_RED,
                    width=3,
                )

        draw_text_centered(nd, (W // 2, H // 2 + 160),
                           "the system starts from raw evidence", fs, DIM)

        paste_alpha(layer, neg_layer, (0, 0), neg_a)
    else:
        u = min(1.0, (t - phase_swap) / 0.5)
        u = ease(u)
        # final lockup
        draw_text_centered(d, (W // 2, H // 2 - 40), "find what matters.", fb_big, FG)
        d.rectangle(
            [(W // 2 - 160, H // 2 + 60), (W // 2 + 160, H // 2 + 62)],
            fill=ACCENT,
        )
        draw_text_centered(d, (W // 2, H // 2 + 110),
                           "reject what doesn't · return a grounded hypothesis",
                           fs, DIM)
        # apply fade-in by using alpha u on top of base a
        paste_alpha(img, layer, (0, 0), a * u)
        # brand
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
        return make_folder_beat(local_t)
    if i == 1:
        return make_single_case_beat(local_t)
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
