# SPDX-License-Identifier: MIT
"""Render block_06_second_moment: 17.5s, 1920x1080, 30fps.

Narration: "Here. Autonomous vehicle session. Operator blamed the tunnel.
But evidence converges across four artifacts in the first second — RTK
was already dead forty-three minutes before tunnel entry. The tunnel
could not cause a state that already existed."

Visual identity preserved from block_01 / block_02 / block_05 / block_07 /
block_08. Same palette, fonts, grid, 4-dot indicator, shadow recipe.

Second-finding treatment vs block_05:
  - narrative center is *contradiction*, not asymmetry
  - operator theory introduced first, then temporally refuted
  - convergence shown as 4 unified artifact cards in the first second
  - final beat is a horizontal timeline showing the 43-minute gap
    between the earliest bad state (0.24s) and tunnel entry (~2606s)
  - lockup phrase: "could not cause a state that already existed."

Beats:
  A 0.0-3.0    AV session + operator theory "tunnel"
  B 3.0-7.0    earliest bad state at t=0.24s (refutation planted)
  C 7.0-12.0   four-artifact convergence in the first second
  D 12.0-17.5  timeline contradiction + lockup

Source: data/final_runs/sanfer_tunnel/report.md (real post-mortem,
sensor_timeout 0.60 root, hypothesis #5 REFUTED operator tunnel narrative
at confidence 0.05).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "video_assets" / "block_06_second_moment"
OUT.mkdir(parents=True, exist_ok=True)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

W, H = 1920, 1080
FPS = 30
DUR = 17.5
N = int(DUR * FPS)

BG = (10, 12, 16)
FG = (230, 232, 236)
DIM = (120, 128, 140)
PANEL = (18, 20, 26)
BORDER = (60, 66, 78)

ACCENT = (255, 184, 64)
MUTED_AMBER = (196, 150, 72)
MUTED_RED = (170, 86, 86)
DEAD_BG = (38, 18, 20)
DEAD_FG = (210, 140, 140)
HEALTH_FG = (186, 220, 170)
STRIKE = (90, 94, 100)

SEG_BOUNDS = [(0.0, 3.0), (3.0, 7.0), (7.0, 12.0), (12.0, 17.5)]
XFADE = 0.45


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
    d.text((cx - 160, y + 18), "  block 06 · second finding", font=fm, fill=(90, 96, 108))


def shadow_for(w: int, h: int, pad: int = 20, alpha: int = 140, blur: int = 18) -> Image.Image:
    sh = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([(pad, pad), (w + pad, h + pad)], fill=(0, 0, 0, alpha))
    return sh.filter(ImageFilter.GaussianBlur(blur))


# -----------------------------------------------------------------------------
# Beat A — AV session + operator theory
# -----------------------------------------------------------------------------


def make_theory_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 3.0, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 72)
    fs = font(FONT_REG, 26)
    fm = font(FONT_MONO, 22)
    fm_b = font(FONT_MONO_BOLD, 22)

    # eyebrow
    d.text((260, 200), "SECOND FINDING", font=fm, fill=ACCENT)
    d.rectangle([(260, 240), (460, 242)], fill=ACCENT)

    # title
    d.text((260, 270), "AV session", font=fb, fill=FG)
    d.text((260, 380), "3626.70 s", font=fb, fill=ACCENT)
    d.text((260, 470), "post-mortem · ROS 2 · autonomous vehicle (manual drive throughout)", font=fs, fill=DIM)

    # source
    src_y = 580
    d.text((260, src_y), "case", font=fm, fill=DIM)
    d.text((260, src_y + 32), "sanfer_tunnel", font=fm_b, fill=FG)
    d.text((260, src_y + 80), "report  data/final_runs/sanfer_tunnel/report.md", font=fm, fill=DIM)

    # right: operator theory card
    card_x, card_y, card_w, card_h = 1120, 260, 620, 380
    card = Image.new("RGBA", (card_w, card_h), PANEL + (255,))
    cd = ImageDraw.Draw(card)
    cd.rectangle([(0, 0), (card_w - 1, card_h - 1)], outline=BORDER, width=2)
    cd.rectangle([(0, 0), (card_w, 52)], fill=(28, 30, 36))
    cd.text((20, 14), "operator theory", font=fm_b, fill=DIM)

    fb_mid = font(FONT_BOLD, 90)
    draw_text_centered(cd, (card_w // 2, 180), "\"tunnel\"", fb_mid, FG)
    draw_text_centered(cd, (card_w // 2, 270),
                       "GPS anomaly at tunnel entry", fs, DIM)
    draw_text_centered(cd, (card_w // 2, 310),
                       "caused behavior degradation", fs, DIM)

    sh = shadow_for(card_w, card_h)
    img.alpha_composite(sh, (card_x - 20, card_y - 20))
    paste_alpha(img, card, (card_x, card_y), 1.0)

    draw_beat_dots(d, active=0)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat B — earliest bad state at t=0.24s
# -----------------------------------------------------------------------------


def make_earliest_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 4.0, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 44)
    fs = font(FONT_REG, 26)
    fm = font(FONT_MONO, 22)
    fm_b = font(FONT_MONO_BOLD, 24)

    d.text((260, 70), "But the data disagrees.", font=fb, fill=FG)
    d.text((260, 126),
           "first RTK state, pre-drive, open sky", font=fs, fill=DIM)
    d.rectangle([(260, 168), (420, 170)], fill=ACCENT)

    # Hero timestamp card
    card_w, card_h = 1400, 620
    cx = (W - card_w) // 2
    cy = 240
    card = Image.new("RGBA", (card_w, card_h), PANEL + (255,))
    cd = ImageDraw.Draw(card)
    cd.rectangle([(0, 0), (card_w - 1, card_h - 1)], outline=MUTED_RED, width=3)
    cd.rectangle([(0, 0), (card_w, 60)], fill=DEAD_BG)
    cd.text((24, 16), "ublox_rover_navrelposned.csv", font=fm_b, fill=FG)
    tag = "FIRST MESSAGE"
    tag_bbox = cd.textbbox((0, 0), tag, font=fm_b)
    tag_w = tag_bbox[2] - tag_bbox[0]
    cd.text((card_w - tag_w - 24, 16), tag, font=fm_b, fill=MUTED_RED)

    # huge timestamp
    fb_huge = font(FONT_BOLD, 200)
    draw_text_centered(cd, (card_w // 2, 200), "t = 0.24 s", fb_huge, ACCENT)
    draw_text_centered(cd, (card_w // 2, 320),
                       "before the vehicle first moved (17.54 s)", fs, DIM)

    # three parallel status rows
    row_a = min(1.0, max(0.0, (t - 0.6) / 0.5))
    row_b = min(1.0, max(0.0, (t - 1.0) / 0.5))
    row_c = min(1.0, max(0.0, (t - 1.4) / 0.5))
    rows = [
        ("carr_soln",              "none",  MUTED_RED, row_a),
        ("rel_pos_valid",          "0",     MUTED_RED, row_b),
        ("rel_pos_heading_valid",  "0",     MUTED_RED, row_c),
    ]
    ry = 390
    fm_k = font(FONT_MONO, 28)
    fm_v = font(FONT_MONO_BOLD, 36)
    for label, value, col, alpha in rows:
        ov = Image.new("RGBA", (card_w, 60), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.rectangle([(80, 0), (card_w - 80, 2)], fill=BORDER)
        od.text((120, 14), label, font=fm_k, fill=DIM)
        od.text((720, 10), "=", font=fm_k, fill=DIM)
        od.text((780, 8), value, font=fm_v, fill=col)
        paste_alpha(card, ov, (0, ry), alpha)
        ry += 68

    sh = shadow_for(card_w, card_h)
    img.alpha_composite(sh, (cx - 20, cy - 20))
    paste_alpha(img, card, (cx, cy), 1.0)

    draw_beat_dots(d, active=1)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat C — four-artifact convergence in first second
# -----------------------------------------------------------------------------


def render_artifact_card(
    t_stamp: str,
    source: str,
    kind: str,
    snippet: str,
    width: int = 680,
    height: int = 280,
) -> Image.Image:
    card = Image.new("RGBA", (width, height), PANEL + (255,))
    d = ImageDraw.Draw(card)
    d.rectangle([(0, 0), (width - 1, height - 1)], outline=BORDER, width=2)
    d.rectangle([(0, 0), (width, 56)], fill=(28, 30, 36))

    fm_b = font(FONT_MONO_BOLD, 22)
    fm = font(FONT_MONO, 20)
    fs = font(FONT_REG, 22)
    fb_ts = font(FONT_BOLD, 42)

    d.text((20, 16), kind, font=fm_b, fill=MUTED_AMBER)
    # right: timestamp
    ts_bbox = d.textbbox((0, 0), t_stamp, font=fb_ts)
    ts_w = ts_bbox[2] - ts_bbox[0]
    d.text((width - ts_w - 20, 70), t_stamp, font=fb_ts, fill=ACCENT)

    d.text((20, 80), source, font=fm, fill=DIM)
    d.rectangle([(20, 130), (width - 20, 132)], fill=BORDER)

    # snippet — wrap simple
    words = snippet.split()
    lines: list[str] = []
    cur = ""
    maxw = width - 50
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textbbox((0, 0), trial, font=fs)[2] > maxw and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    y = 150
    for ln in lines[:4]:
        d.text((24, y), ln, font=fs, fill=FG)
        y += 30

    return card


def make_convergence_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 5.0, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 44)
    fs = font(FONT_REG, 26)
    fm_b = font(FONT_MONO_BOLD, 22)

    d.text((260, 60), "Four artifacts · first second", font=fb, fill=FG)
    d.text((260, 116),
           "independent sources, same conclusion — before the vehicle moved",
           font=fs, fill=DIM)
    d.rectangle([(260, 158), (460, 160)], fill=ACCENT)

    artifacts = [
        ("0.24 s", "ublox_rover_navrelposned.csv", "telemetry",
         "carr_soln=none · rel_pos_valid=0 · rel_pos_heading_valid=0 — the state it will hold for all 3626 s"),
        ("0.40 s", "diagnostics_nonzero_unique.csv", "diagnostics",
         "ekf_se_map /odometry/filtered — 'No events recorded' (ERROR) — filter never publishes"),
        ("0.49 s", "rosout_warnings.csv", "rosout",
         "ntrip_client — first RTCM CRC-24Q checksum mismatch (before motion)"),
        ("0.52 s", "diagnostics_nonzero_unique.csv", "diagnostics",
         "ublox_rover + ublox_moving_base — 'TMODE3: Not configured' (no RTK-role preset at boot)"),
    ]

    card_w, card_h = 680, 280
    gap_x = 40
    gap_y = 40
    total_w = card_w * 2 + gap_x
    start_x = (W - total_w) // 2
    start_y = 210

    positions = [
        (start_x,                     start_y),
        (start_x + card_w + gap_x,    start_y),
        (start_x,                     start_y + card_h + gap_y),
        (start_x + card_w + gap_x,    start_y + card_h + gap_y),
    ]

    sh = shadow_for(card_w, card_h)
    for i, ((ts, src, kind, snip), pos) in enumerate(zip(artifacts, positions)):
        # stagger reveal
        card_a = min(1.0, max(0.0, (t - (0.3 + i * 0.45)) / 0.5))
        if card_a <= 0:
            continue
        card = render_artifact_card(ts, src, kind, snip, card_w, card_h)
        img.alpha_composite(sh, (pos[0] - 20, pos[1] - 20))
        paste_alpha(img, card, pos, card_a)

    # convergence connector: centered verdict pill (after all 4)
    verdict_a = min(1.0, max(0.0, (t - 2.8) / 0.7))
    if verdict_a > 0:
        vy = start_y + card_h * 2 + gap_y + 80
        vx = W // 2
        ftext = font(FONT_BOLD, 38)
        text = "RTK already dead · before vehicle moved"
        bbox = d.textbbox((0, 0), text, font=ftext)
        tw = bbox[2] - bbox[0]
        pad = 28
        ov = Image.new("RGBA", (tw + pad * 2, 80), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.rectangle([(0, 0), (tw + pad * 2 - 1, 79)], fill=(28, 30, 36), outline=ACCENT, width=2)
        od.text((pad, 20), text, font=ftext, fill=ACCENT)
        paste_alpha(img, ov, (vx - (tw + pad * 2) // 2, vy), verdict_a)

    draw_beat_dots(d, active=2)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat D — timeline contradiction + lockup
# -----------------------------------------------------------------------------


def make_lockup_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 5.5, 0.6)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 40)
    fb_big = font(FONT_BOLD, 76)
    fs = font(FONT_REG, 26)
    fm = font(FONT_MONO, 22)
    fm_b = font(FONT_MONO_BOLD, 24)

    d.text((260, 60), "Temporal ordering", font=fb, fill=FG)
    d.text((260, 112), "the tunnel entered the story 43 minutes after RTK died", font=fs, fill=DIM)
    d.rectangle([(260, 154), (420, 156)], fill=ACCENT)

    # horizontal timeline
    tl_x0 = 200
    tl_x1 = W - 200
    tl_y = 330
    # axis
    d.rectangle([(tl_x0, tl_y), (tl_x1, tl_y + 4)], fill=BORDER)

    # x-scale: 0..3626.7 s maps to tl_x0..tl_x1
    def tx(sec: float) -> int:
        return int(tl_x0 + (sec / 3626.7) * (tl_x1 - tl_x0))

    # ticks
    fm_tick = font(FONT_MONO, 18)
    for sec, label in [(0, "0 s"), (900, "15 min"), (1800, "30 min"),
                       (2700, "45 min"), (3626.7, "60:26")]:
        x = tx(sec)
        d.rectangle([(x - 1, tl_y), (x + 1, tl_y + 16)], fill=DIM)
        lb_bbox = d.textbbox((0, 0), label, font=fm_tick)
        lb_w = lb_bbox[2] - lb_bbox[0]
        d.text((x - lb_w // 2, tl_y + 22), label, font=fm_tick, fill=DIM)

    # persistence band: 0.24 -> 3626 -- paint across entire axis
    band_a = min(1.0, max(0.0, (t - 0.3) / 0.6))
    if band_a > 0:
        bx0 = tx(0.24)
        bx1 = tx(3626.7)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.rectangle([(bx0, tl_y - 28), (bx1, tl_y - 4)], fill=(*MUTED_RED, 180))
        od.text(((bx0 + bx1) // 2 - 170, tl_y - 68),
                "carr_soln = none · 3626 s", font=fm_b, fill=MUTED_RED)
        paste_alpha(img, ov, (0, 0), band_a)

    # marker 1: bad state at 0.24s (far left)
    mark1_a = min(1.0, max(0.0, (t - 0.9) / 0.5))
    if mark1_a > 0:
        mx = tx(0.24)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.line([(mx, tl_y - 80), (mx, tl_y + 80)], fill=ACCENT, width=3)
        od.ellipse([(mx - 10, tl_y - 10), (mx + 10, tl_y + 10)], fill=ACCENT)
        od.text((mx + 20, tl_y + 60), "t = 0.24 s", font=fm_b, fill=ACCENT)
        od.text((mx + 20, tl_y + 92), "first bad RTK state", font=fm, fill=FG)
        paste_alpha(img, ov, (0, 0), mark1_a)

    # marker 2: tunnel entry ~2606s
    mark2_a = min(1.0, max(0.0, (t - 1.5) / 0.5))
    if mark2_a > 0:
        mx = tx(2606.5)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.line([(mx, tl_y - 80), (mx, tl_y + 80)], fill=FG, width=3)
        od.ellipse([(mx - 10, tl_y - 10), (mx + 10, tl_y + 10)], fill=FG)
        od.text((mx - 110, tl_y + 60), "t ≈ 43:26", font=fm_b, fill=FG)
        od.text((mx - 110, tl_y + 92), "tunnel entry (dense frames)", font=fm, fill=DIM)
        paste_alpha(img, ov, (0, 0), mark2_a)

    # gap annotation
    gap_a = min(1.0, max(0.0, (t - 2.2) / 0.5))
    if gap_a > 0:
        x1 = tx(0.24)
        x2 = tx(2606.5)
        mid = (x1 + x2) // 2
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.line([(x1 + 20, tl_y - 150), (x2 - 20, tl_y - 150)], fill=ACCENT, width=2)
        od.line([(x1 + 20, tl_y - 160), (x1 + 20, tl_y - 140)], fill=ACCENT, width=2)
        od.line([(x2 - 20, tl_y - 160), (x2 - 20, tl_y - 140)], fill=ACCENT, width=2)
        od.text((mid - 110, tl_y - 200), "43 minutes", font=font(FONT_BOLD, 32), fill=ACCENT)
        paste_alpha(img, ov, (0, 0), gap_a)

    # final hero lockup
    hero_a = min(1.0, max(0.0, (t - 3.0) / 0.6))
    if hero_a > 0:
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        draw_text_centered(od, (W // 2, 680),
                           "could not cause a state", fb_big, FG)
        draw_text_centered(od, (W // 2, 770),
                           "that already existed.", fb_big, ACCENT)

        # pill row
        pill_y = 880
        items = [
            ("verdict", "operator theory refuted"),
            ("root cause", "session-wide RTK pipeline"),
            ("confidence", "0.95  ·  0.05"),
        ]
        fm_r = font(FONT_MONO, 20)
        fm_bb = font(FONT_MONO_BOLD, 22)
        padding = 18
        gap = 24
        widths = []
        for label, value in items:
            lb_w = od.textbbox((0, 0), label, font=fm_r)[2]
            v_w = od.textbbox((0, 0), value, font=fm_bb)[2]
            widths.append(lb_w + 10 + v_w + padding * 2)
        total = sum(widths) + gap * (len(items) - 1)
        x = (W - total) // 2
        for (label, value), w in zip(items, widths):
            od.rectangle([(x, pill_y), (x + w, pill_y + 52)],
                         fill=(28, 30, 36), outline=BORDER, width=1)
            od.text((x + padding, pill_y + 14), label, font=fm_r, fill=DIM)
            lb_w = od.textbbox((0, 0), label, font=fm_r)[2]
            fill = ACCENT if "refuted" in value or "session" in value else FG
            od.text((x + padding + lb_w + 10, pill_y + 12), value, font=fm_bb, fill=fill)
            x += w + gap

        paste_alpha(img, ov, (0, 0), hero_a)

    draw_beat_dots(d, active=3)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Render
# -----------------------------------------------------------------------------


def crossfade(a: Image.Image, b: Image.Image, u: float) -> Image.Image:
    return Image.blend(a, b, u)


def _seg(i: int, local_t: float) -> Image.Image:
    if i == 0:
        return make_theory_beat(local_t)
    if i == 1:
        return make_earliest_beat(local_t)
    if i == 2:
        return make_convergence_beat(local_t)
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
    tmp = Path(tempfile.mkdtemp(prefix="block06_"))
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

    # preview: beat D with lockup visible
    preview = render_at(15.5).convert("RGB")
    preview.save(OUT / "preview.png", "PNG", optimize=True)

    shutil.rmtree(tmp)
    print(f"wrote {out_mp4}")


if __name__ == "__main__":
    main()
