# SPDX-License-Identifier: MIT
"""Render block_sanfer_evidence: 70s, 1920x1080, 30fps.

Continuous Sanfer forensic story (no UI):
  A 0-10s   telemetry-anchored visual mining (5-cam grid + window strip)
  B 10-22s  operator tunnel hypothesis
  C 22-32s  refutation: numSV never collapses
  D 32-52s  real root cause — RTK carrier contrast + REL_POS_VALID flat zero
  E 52-70s  scoped patch/diff proposal (proposed for human review)
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
OUT = ROOT / "video_assets" / "block_sanfer_evidence"
OUT.mkdir(parents=True, exist_ok=True)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

W, H = 1920, 1080
FPS = 30
DUR = 70.0
N = int(DUR * FPS)

BG     = (10, 12, 16)
FG     = (230, 232, 236)
DIM    = (120, 128, 140)
PANEL  = (18, 20, 26)
BORDER = (60, 66, 78)
ACCENT = (255, 184, 64)
MUTED_AMBER = (196, 150, 72)
MUTED_RED = (170, 86, 86)
HEALTH = (186, 230, 170)
STRIKE = (90, 94, 100)

FRAMES_DIR = ROOT / "data/runs/sanfer_sanisidro__no_prompt/frames"
WINDOWS_JSON = ROOT / "data/runs/sanfer_sanisidro__no_prompt/windows.json"
RTK_CARRIER = ROOT / "docs/assets/rtk_carrier_contrast.png"
RTK_RELPOS  = ROOT / "docs/assets/rel_pos_valid.png"
RTK_NUMSV   = ROOT / "docs/assets/rtk_numsv.png"
DIFF_PNG    = ROOT / "demo_assets/diff_viewer/moving_base_rover.png"
ANALYSIS_JSON = ROOT / "black-box-bench/runs/sample/rtk_heading_break_01.json"

SEG_BOUNDS = [
    (0.0, 10.0),    # A — visual mining
    (10.0, 22.0),   # B — operator hypothesis
    (22.0, 32.0),   # C — refutation
    (32.0, 52.0),   # D — real cause
    (52.0, 70.0),   # E — diff
]
XFADE = 0.5


def font(p: str, s: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(p, s)


def ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def fade_alpha(local_t: float, dur: float, fade: float = 0.5) -> float:
    if local_t < 0 or local_t > dur:
        return 0.0
    return max(0.0, min(1.0, min(local_t / fade, (dur - local_t) / fade)))


def grid_bg(img: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=(18, 20, 26), width=1)
    for y in range(0, H, 80):
        d.line([(0, y), (W, y)], fill=(18, 20, 26), width=1)


def paste_alpha(base: Image.Image, overlay: Image.Image, pos, a: float) -> None:
    if a <= 0:
        return
    if overlay.mode != "RGBA":
        overlay = overlay.convert("RGBA")
    if a < 1.0:
        r, g, b, al = overlay.split()
        al = al.point(lambda v: int(v * a))
        overlay = Image.merge("RGBA", (r, g, b, al))
    base.alpha_composite(overlay, pos)


def shadow_for(w: int, h: int, pad: int = 18, alpha: int = 130, blur: int = 16) -> Image.Image:
    sh = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([(pad, pad), (w + pad, h + pad)], fill=(0, 0, 0, alpha))
    return sh.filter(ImageFilter.GaussianBlur(blur))


def draw_text_centered(d, xy, text, f, fill) -> None:
    bb = d.textbbox((0, 0), text, font=f)
    d.text((xy[0] - (bb[2] - bb[0]) // 2, xy[1] - (bb[3] - bb[1]) // 2), text, font=f, fill=fill)


def draw_beat_dots(d, active: int, label: str, accent=ACCENT) -> None:
    cx = W // 2
    y = H - 60
    gap = 28
    start = cx - 2 * gap
    fm = font(FONT_MONO, 16)
    for i in range(5):
        x = start + i * gap
        col = accent if i == active else (60, 64, 72)
        d.ellipse([(x - 6, y - 6), (x + 6, y + 6)], fill=col)
    bb = d.textbbox((0, 0), label, font=fm)
    d.text((cx - (bb[2] - bb[0]) // 2, y + 18), label, font=fm, fill=(90, 96, 108))


# ---------------------------------------------------------------------------
# Source data
# ---------------------------------------------------------------------------

WINDOWS = json.loads(WINDOWS_JSON.read_text())
ANALYSIS = json.loads(ANALYSIS_JSON.read_text())


def pick_cam_frame(cam: str, win_idx: int = 3, slot: int = 4) -> Path | None:
    prefix = f"w{win_idx:02d}___{cam}_image_raw_compressed_{slot:02d}_"
    for p in sorted(FRAMES_DIR.glob(prefix + "*.jpg")):
        if "_small" not in p.name:
            return p
    return None


# ---------------------------------------------------------------------------
# Beat A — visual mining: 5-cam grid + telemetry window strip
# ---------------------------------------------------------------------------

def make_beat_A(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 10.0, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 38)
    fs = font(FONT_REG, 22)
    fm = font(FONT_MONO, 18)
    fmb = font(FONT_MONO_BOLD, 20)

    d.text((80, 60), "Telemetry-anchored evidence selection", font=fb, fill=FG)
    d.text((80, 110), "session sanfer_sanisidro · 2_cam-lidar.bag · 3627.05 s · 5 cameras + lidar + GNSS", font=fs, fill=DIM)
    d.rectangle([(80, 148), (240, 150)], fill=ACCENT)

    # 5-cam grid
    cams = ["cam1", "cam2", "cam3", "cam4", "cam5"]
    # Grid: 3 cols top, 2 cols bottom, centered
    cell_w = 560
    cell_h = 315
    gap = 18
    top_row_w = 3 * cell_w + 2 * gap
    top_x = (W - top_row_w) // 2
    top_y = 200
    bot_row_w = 2 * cell_w + gap
    bot_x = (W - bot_row_w) // 2
    bot_y = top_y + cell_h + gap
    positions = [
        (top_x + 0 * (cell_w + gap), top_y),
        (top_x + 1 * (cell_w + gap), top_y),
        (top_x + 2 * (cell_w + gap), top_y),
        (bot_x + 0 * (cell_w + gap), bot_y),
        (bot_x + 1 * (cell_w + gap), bot_y),
    ]

    for i, cam in enumerate(cams):
        x, y = positions[i]
        p = pick_cam_frame(cam, win_idx=3, slot=4)
        if p is None:
            continue
        thumb = Image.open(p).convert("RGB").resize((cell_w, cell_h), Image.LANCZOS)
        sh = shadow_for(cell_w, cell_h)
        img.alpha_composite(sh, (x - 18, y - 18))
        img.paste(thumb, (x, y))
        # cam label
        cd = ImageDraw.Draw(img)
        cd.rectangle([(x, y), (x + 90, y + 28)], fill=(0, 0, 0))
        cd.text((x + 8, y + 4), cam, font=fmb, fill=ACCENT)

    # Telemetry window strip
    strip_y = bot_y + cell_h + 36
    strip_x0 = 120
    strip_x1 = W - 120
    sw = strip_x1 - strip_x0
    d.text((strip_x0, strip_y - 30), "session timeline · 0 s ─────────────────────────── 3627 s", font=fm, fill=DIM)
    d.rectangle([(strip_x0, strip_y), (strip_x1, strip_y + 14)], fill=PANEL, outline=BORDER, width=1)
    duration_s = 3627.05
    for w in WINDOWS:
        ws = w["center_ns"] / 1e9 - 1770136878.612968  # bag t0 approx; relative offset doesn't matter visually
        # use index of center within session — derive from priority and span
        # use direct mapping: place windows uniformly by their center_ns delta from earliest
    # Use known window centers relative to first center
    centers = [w["center_ns"] for w in WINDOWS]
    t0 = min(centers)
    for i, w in enumerate(WINDOWS):
        rel = (w["center_ns"] - t0) / 1e9
        frac = max(0.0, min(1.0, rel / duration_s))
        cx = strip_x0 + int(frac * sw)
        span_px = max(8, int(w["span_s"] / duration_s * sw))
        col = ACCENT if w["priority"] >= 0.9 else MUTED_AMBER
        d.rectangle([(cx - span_px // 2, strip_y - 6), (cx + span_px // 2, strip_y + 20)], fill=col)
    # legend
    d.text((strip_x0, strip_y + 30), "7 candidate windows · selected by RTK/GNSS flag transitions and stuck-state detectors",
           font=fm, fill=DIM)
    d.text((strip_x0, strip_y + 56), "frames densified inside windows only · uniform sampling avoided", font=fm, fill=DIM)

    draw_beat_dots(d, active=0, label="block · sanfer evidence  ·  beat A / 5")
    paste_alpha(img, layer, (0, 0), a)
    return img


# ---------------------------------------------------------------------------
# Beat B — operator hypothesis
# ---------------------------------------------------------------------------

def make_beat_B(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = fade_alpha(t, 12.0, 0.55)

    fb = font(FONT_BOLD, 40)
    fs = font(FONT_REG, 24)
    fm = font(FONT_MONO, 20)
    fmb = font(FONT_MONO_BOLD, 22)
    fquote = font(FONT_REG, 56)

    d.text((80, 60), "Operator hypothesis", font=fb, fill=FG)
    d.text((80, 110), "field log entry · pre-analysis · sanfer_sanisidro 2026-02-03", font=fs, fill=DIM)
    d.rectangle([(80, 148), (240, 150)], fill=MUTED_AMBER)

    # Quote card
    qx, qy, qw, qh = 140, 230, 1640, 280
    sh = shadow_for(qw, qh)
    img.alpha_composite(sh, (qx - 18, qy - 18))
    qcard = Image.new("RGBA", (qw, qh), PANEL + (255,))
    qd = ImageDraw.Draw(qcard)
    qd.rectangle([(0, 0), (qw - 1, qh - 1)], outline=BORDER, width=2)
    qd.rectangle([(0, 0), (8, qh)], fill=MUTED_AMBER)
    qd.text((48, 28), "operator note", font=fmb, fill=MUTED_AMBER)
    qd.text((48, 70), "“the GPS fails when we enter the tunnel.”", font=fquote, fill=FG)
    qd.text((48, 200), "implied class: GNSS outage during overhead occlusion", font=fm, fill=DIM)
    img.alpha_composite(qcard, (qx, qy))

    # Provisional triage card
    tx, ty, tw, th = 140, 560, 800, 360
    tcard = Image.new("RGBA", (tw, th), PANEL + (255,))
    td = ImageDraw.Draw(tcard)
    td.rectangle([(0, 0), (tw - 1, th - 1)], outline=BORDER, width=2)
    td.text((28, 22), "provisional triage", font=fmb, fill=DIM)
    td.text((28, 60), "looks like:  bug class #2 sensor timeout (GNSS).", font=fs, fill=FG)
    td.text((28, 100), "search:  windows where /vehicle/gps/fix degrades", font=fs, fill=DIM)
    td.text((28, 138), "and SVs collapse below 3D-fix threshold.", font=fs, fill=DIM)
    td.text((28, 200), "if true, the patch is trivial:", font=fs, fill=DIM)
    td.text((28, 234), "• gate consumers on fixType >= 3", font=fm, fill=FG)
    td.text((28, 266), "• fall back to IMU dead-reckoning during outage", font=fm, fill=FG)
    td.text((28, 298), "• log overhead-occlusion event", font=fm, fill=FG)
    sh2 = shadow_for(tw, th)
    img.alpha_composite(sh2, (tx - 18, ty - 18))
    img.alpha_composite(tcard, (tx, ty))

    # Question card right
    qqx, qqy, qqw, qqh = 980, 560, 800, 360
    qqcard = Image.new("RGBA", (qqw, qqh), PANEL + (255,))
    qqd = ImageDraw.Draw(qqcard)
    qqd.rectangle([(0, 0), (qqw - 1, qqh - 1)], outline=BORDER, width=2)
    qqd.text((28, 22), "what the data must show", font=fmb, fill=ACCENT)
    qqd.text((28, 70), "to confirm the tunnel theory:", font=fs, fill=DIM)
    qqd.text((28, 120), "✓  rover numSV collapses below 4", font=fs, fill=FG)
    qqd.text((28, 160), "✓  fixType drops from 3 to 0/1", font=fs, fill=FG)
    qqd.text((28, 200), "✓  hAcc spikes during occlusion", font=fs, fill=FG)
    qqd.text((28, 240), "✓  failure clusters in one window", font=fs, fill=FG)
    qqd.text((28, 290), "we check the bag.", font=fmb, fill=ACCENT)
    sh3 = shadow_for(qqw, qqh)
    img.alpha_composite(sh3, (qqx - 18, qqy - 18))
    img.alpha_composite(qqcard, (qqx, qqy))

    draw_beat_dots(d, active=1, label="block · sanfer evidence  ·  beat B / 5", accent=MUTED_AMBER)
    paste_alpha(img, layer, (0, 0), a)
    return img


# ---------------------------------------------------------------------------
# Beat C — refutation: numSV never collapses
# ---------------------------------------------------------------------------

def make_beat_C(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = fade_alpha(t, 10.0, 0.55)

    fb = font(FONT_BOLD, 40)
    fs = font(FONT_REG, 24)
    fm = font(FONT_MONO, 20)
    fmb = font(FONT_MONO_BOLD, 22)

    d.text((80, 60), "Tunnel theory · evidence check", font=fb, fill=FG)
    d.text((80, 110), "rover satellite count over the full 1-hour session", font=fs, fill=DIM)
    d.rectangle([(80, 148), (240, 150)], fill=MUTED_RED)

    # numSV plot — fit width
    plot = Image.open(RTK_NUMSV).convert("RGBA")
    pw_target = 1500
    ph_target = int(plot.size[1] * pw_target / plot.size[0])
    plot_r = plot.resize((pw_target, ph_target), Image.LANCZOS)
    px, py = (W - pw_target) // 2, 200
    sh = shadow_for(pw_target, ph_target)
    img.alpha_composite(sh, (px - 18, py - 18))
    img.alpha_composite(plot_r, (px, py))

    # verdict pill row
    vy = py + ph_target + 30
    items = [
        ("rover numSV median", "29", HEALTH),
        ("rover numSV min", "16", HEALTH),
        ("3D-fix threshold", "4", DIM),
        ("fixType = 3 (3D)", "100% of samples", HEALTH),
        ("hAcc max", "1.3 m", HEALTH),
    ]
    pill_x = 100
    for label, val, col in items:
        bb_l = d.textbbox((0, 0), label, font=fm)
        bb_v = d.textbbox((0, 0), val, font=fmb)
        pw = max(bb_l[2], bb_v[2]) + 36
        ph = 80
        d.rectangle([(pill_x, vy), (pill_x + pw, vy + ph)], fill=PANEL, outline=BORDER, width=2)
        d.text((pill_x + 18, vy + 8), label, font=fm, fill=DIM)
        d.text((pill_x + 18, vy + 40), val, font=fmb, fill=col)
        pill_x += pw + 18

    # Verdict strike-through over operator quote echo
    vy2 = vy + 110
    rejected_card = Image.new("RGBA", (1720, 84), PANEL + (255,))
    rd = ImageDraw.Draw(rejected_card)
    rd.rectangle([(0, 0), (1719, 83)], outline=(80, 40, 40), width=2)
    rd.text((24, 22), "operator hypothesis · GNSS outage during tunnel", font=fmb, fill=STRIKE)
    rd.line([(20, 38), (1100, 38)], fill=MUTED_RED, width=2)
    rd.line([(20, 50), (1100, 50)], fill=MUTED_RED, width=2)
    rd.rectangle([(1480, 18), (1700, 64)], outline=MUTED_RED, width=2)
    rd.text((1500, 26), "REFUTED", font=fmb, fill=MUTED_RED)
    img.alpha_composite(rejected_card, (100, vy2))

    draw_beat_dots(d, active=2, label="block · sanfer evidence  ·  beat C / 5", accent=MUTED_RED)
    paste_alpha(img, layer, (0, 0), a)
    return img


# ---------------------------------------------------------------------------
# Beat D — real root cause
# ---------------------------------------------------------------------------

def make_beat_D(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = fade_alpha(t, 20.0, 0.6)

    fb = font(FONT_BOLD, 40)
    fs = font(FONT_REG, 24)
    fm = font(FONT_MONO, 20)
    fmb = font(FONT_MONO_BOLD, 22)
    fbig = font(FONT_BOLD, 64)

    d.text((80, 50), "Real root cause", font=fb, fill=FG)
    d.text((80, 100), "moving-base→rover RTK link silent for the entire session", font=fs, fill=DIM)
    d.rectangle([(80, 138), (240, 140)], fill=ACCENT)

    # Carrier-phase contrast plot
    p1 = Image.open(RTK_CARRIER).convert("RGBA")
    pw1 = 1180
    ph1 = int(p1.size[1] * pw1 / p1.size[0])
    p1r = p1.resize((pw1, ph1), Image.LANCZOS)
    p1x, p1y = 80, 180
    sh1 = shadow_for(pw1, ph1)
    img.alpha_composite(sh1, (p1x - 18, p1y - 18))
    img.alpha_composite(p1r, (p1x, p1y))

    # REL_POS_VALID plot under it
    p2 = Image.open(RTK_RELPOS).convert("RGBA")
    pw2 = 1180
    ph2 = int(p2.size[1] * pw2 / p2.size[0])
    p2r = p2.resize((pw2, ph2), Image.LANCZOS)
    p2x, p2y = 80, p1y + ph1 + 30
    sh2 = shadow_for(pw2, ph2)
    img.alpha_composite(sh2, (p2x - 18, p2y - 18))
    img.alpha_composite(p2r, (p2x, p2y))

    # Right column: numbers + diagnosis
    col_x = 1300
    col_y = 200
    col_w = 540
    # Big stats stack
    stat_card = Image.new("RGBA", (col_w, 740), PANEL + (255,))
    sd = ImageDraw.Draw(stat_card)
    sd.rectangle([(0, 0), (col_w - 1, 739)], outline=BORDER, width=2)
    sd.rectangle([(0, 0), (col_w, 56)], fill=(28, 30, 36))
    sd.text((20, 14), "rtk_heading_break_01.json", font=fmb, fill=FG)

    sd.text((24, 80), "rover carrier-phase", font=fm, fill=DIM)
    sd.text((24, 110), "CARR_NONE", font=fbig, fill=MUTED_RED)
    sd.text((24, 184), "100.0 % of 18 133 samples", font=fmb, fill=FG)

    sd.text((24, 240), "moving-base carrier-phase", font=fm, fill=DIM)
    sd.text((24, 270), "FLOAT 63.6 % · FIXED 30.7 %", font=fmb, fill=HEALTH)
    sd.text((24, 304), "base sees usable signal — sky is fine.", font=fm, fill=DIM)

    sd.text((24, 360), "navrelposned.flags", font=fm, fill=DIM)
    sd.text((24, 390), "REL_POS_VALID  0.0 %", font=fmb, fill=MUTED_RED)
    sd.text((24, 422), "DIFF_SOLN      15.0 %", font=fmb, fill=MUTED_AMBER)
    sd.text((24, 454), "relPosLength / relPosHeading", font=fm, fill=DIM)
    sd.text((24, 482), "identically zero, full session.", font=fm, fill=DIM)

    sd.text((24, 540), "diagnosis", font=fm, fill=DIM)
    sd.text((24, 572), "moving-base RTCM uplink", font=fmb, fill=ACCENT)
    sd.text((24, 602), "to rover is misconfigured.", font=fmb, fill=ACCENT)
    sd.text((24, 644), "confidence  0.90", font=fm, fill=FG)
    sd.text((24, 670), "scope  session-global · 3627 s", font=fm, fill=DIM)
    sd.text((24, 696), "class  configuration / wiring", font=fm, fill=DIM)

    sh3 = shadow_for(col_w, 740)
    img.alpha_composite(sh3, (col_x - 18, col_y - 18))
    img.alpha_composite(stat_card, (col_x, col_y))

    draw_beat_dots(d, active=3, label="block · sanfer evidence  ·  beat D / 5")
    paste_alpha(img, layer, (0, 0), a)
    return img


# ---------------------------------------------------------------------------
# Beat E — scoped patch / diff proposal
# ---------------------------------------------------------------------------

_DIFF_CACHE: dict[str, Image.Image] = {}


def get_diff_panel() -> Image.Image:
    if "img" not in _DIFF_CACHE:
        im = Image.open(DIFF_PNG).convert("RGBA")
        # scale to fit ~860 height
        target_h = 860
        scale = target_h / im.size[1]
        target_w = int(im.size[0] * scale)
        _DIFF_CACHE["img"] = im.resize((target_w, target_h), Image.LANCZOS)
    return _DIFF_CACHE["img"]


def make_beat_E(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = fade_alpha(t, 18.0, 0.6)

    fb = font(FONT_BOLD, 40)
    fs = font(FONT_REG, 24)
    fm = font(FONT_MONO, 20)
    fmb = font(FONT_MONO_BOLD, 22)
    fmb_l = font(FONT_MONO_BOLD, 26)

    d.text((80, 50), "Scoped patch · proposed for human review", font=fb, fill=FG)
    d.text((80, 100), "3 files · driver config + prelaunch gate · no architectural rewrite", font=fs, fill=DIM)
    d.rectangle([(80, 138), (240, 140)], fill=ACCENT)

    # Diff panel — right side, scrolls slowly within the beat
    diff_im = get_diff_panel()
    dw, dh = diff_im.size
    dx = W - dw - 80
    dy = 180

    # Vertical pan: show top initially; pan down over time
    # Make sure full diff visible across beat: but image is wider than fits, so use crop
    # Use whole image; if dy + dh > H - 100, then add slow pan
    visible_h = 860
    pan_total = max(0, dh - visible_h)
    # Pan starts at 2s, ends at 14s, holds before/after
    pan_t = max(0.0, min(1.0, (t - 2.0) / 12.0))
    crop_y = int(pan_total * ease(pan_t))
    diff_crop = diff_im.crop((0, crop_y, dw, crop_y + visible_h))
    sh = shadow_for(dw, visible_h)
    img.alpha_composite(sh, (dx - 18, dy - 18))
    img.alpha_composite(diff_crop, (dx, dy))

    # Left column: concise patch summary + caveat
    col_x = 80
    col_y = 200
    col_w = 700
    col_h = 820
    card = Image.new("RGBA", (col_w, col_h), PANEL + (255,))
    cd = ImageDraw.Draw(card)
    cd.rectangle([(0, 0), (col_w - 1, col_h - 1)], outline=BORDER, width=2)
    cd.rectangle([(0, 0), (col_w, 60)], fill=(28, 30, 36))
    cd.text((20, 16), "patch_proposal", font=fmb_l, fill=ACCENT)

    y = 90
    cd.text((24, y), "1 / 3   moving_base.yaml", font=fmb, fill=FG); y += 32
    cd.text((24, y), "uart2.out_protocol  ubx → ubx+rtcm3", font=fm, fill=HEALTH); y += 28
    cd.text((24, y), "emit RTCM3 4072.0/4072.1, 1077, 1087,", font=fm, fill=DIM); y += 26
    cd.text((24, y), "1097, 1127, 1230 to the rover", font=fm, fill=DIM); y += 26
    cd.text((24, y), "tmode3  1 (survey-in) → 0 (disabled)", font=fm, fill=DIM); y += 40

    cd.text((24, y), "2 / 3   rover.yaml", font=fmb, fill=FG); y += 32
    cd.text((24, y), "uart2.in_protocol  ubx → rtcm3", font=fm, fill=HEALTH); y += 28
    cd.text((24, y), "CFG-UART2INPROT-RTCM3X = 1", font=fm, fill=DIM); y += 26
    cd.text((24, y), "baud 115200 → 460800 (matched)", font=fm, fill=DIM); y += 40

    cd.text((24, y), "3 / 3   prelaunch_watchdog.py", font=fmb, fill=FG); y += 32
    cd.text((24, y), "+ require carr_soln ∈ {FLOAT, FIXED}", font=fm, fill=HEALTH); y += 28
    cd.text((24, y), "+ require rel_pos_heading_valid", font=fm, fill=HEALTH); y += 28
    cd.text((24, y), "+ stable for ≥ 10 s before drive", font=fm, fill=HEALTH); y += 26
    cd.text((24, y), "fail-closed; same class of silent", font=fm, fill=DIM); y += 26
    cd.text((24, y), "failure caught on day one.", font=fm, fill=DIM); y += 50

    # Caveat box
    cd.rectangle([(20, y), (col_w - 20, y + 130)], outline=MUTED_AMBER, width=2)
    cd.text((34, y + 14), "human review required", font=fmb, fill=MUTED_AMBER)
    cd.text((34, y + 50), "patch is a proposal only.", font=fm, fill=FG)
    cd.text((34, y + 78), "no auto-apply.  no merge.", font=fm, fill=FG)
    cd.text((34, y + 104), "operator validates against rig before flash.", font=fm, fill=DIM)

    sh2 = shadow_for(col_w, col_h)
    img.alpha_composite(sh2, (col_x - 18, col_y - 18))
    img.alpha_composite(card, (col_x, col_y))

    draw_beat_dots(d, active=4, label="block · sanfer evidence  ·  beat E / 5")
    paste_alpha(img, layer, (0, 0), a)
    return img


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

def crossfade(a: Image.Image, b: Image.Image, u: float) -> Image.Image:
    return Image.blend(a, b, u)


def _seg(i: int, local_t: float) -> Image.Image:
    if i == 0: return make_beat_A(local_t)
    if i == 1: return make_beat_B(local_t)
    if i == 2: return make_beat_C(local_t)
    if i == 3: return make_beat_D(local_t)
    return make_beat_E(local_t)


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
    tmp = Path(tempfile.mkdtemp(prefix="block_sanfer_"))
    print(f"tmp: {tmp}", file=sys.stderr)

    # Cache static beat compositions and only redraw for fade-in/crossfade frames
    for k in range(N):
        t = k / FPS
        fr = render_at(t).convert("RGB")
        fr.save(tmp / f"f_{k:05d}.png", "PNG", optimize=False)
        if k % 60 == 0:
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

    # Preview frame: D beat, where data refutes the theory
    preview = render_at(42.0).convert("RGB")
    preview.save(OUT / "preview.png", "PNG", optimize=True)

    shutil.rmtree(tmp)
    print(f"wrote {out_mp4}")


if __name__ == "__main__":
    main()
