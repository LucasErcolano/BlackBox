# SPDX-License-Identifier: MIT
"""Render block_09_punchline: 12.5s, 1920x1080, 30fps.

Narration: "So the output is not just a summary. It is a forensic report,
ranked hypotheses, and a patch a human can review immediately."

Product-closure beat. No new evidence. No diff hero. Three outputs
(report / ranked outcome / scoped patch) packaged as one deliverable
bundle. Diff keeps slightly more visual weight than the other two but
never dominates the frame.

Beats:
  A 0.0-2.5   bundle frame intro: "deliverable" eyebrow + 3-slot skeleton
  B 2.5-6.0   three output cards reveal (report / ranked outcome / patch)
  C 6.0-9.5   reviewability emphasis — amber hairline under patch, DIM
              annotation "human reviews · system does not auto-apply"
  D 9.5-12.5  lockup: "not just a summary." / "ready for review."

Sources grounded in data/final_runs/sanfer_tunnel/{report.md, bundle/}.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "video_assets" / "block_09_punchline"
OUT.mkdir(parents=True, exist_ok=True)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

W, H = 1920, 1080
FPS = 30
DUR = 12.5
N = int(DUR * FPS)

BG = (10, 12, 16)
FG = (230, 232, 236)
DIM = (120, 128, 140)
ACCENT = (255, 184, 64)
MUTED_AMBER = (196, 150, 72)
PANEL = (18, 20, 26)
BORDER = (60, 66, 78)

ADD_BG = (22, 44, 28)
ADD_FG = (186, 230, 170)
DEL_BG = (54, 22, 26)
DEL_FG = (230, 150, 150)
HUNK_FG = (170, 140, 220)

SEG_BOUNDS = [(0.0, 2.5), (2.5, 6.0), (6.0, 9.5), (9.5, 12.5)]
XFADE = 0.45


def ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def fade_alpha(local_t: float, dur: float, fade: float = 0.45) -> float:
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


def draw_text_centered(d: ImageDraw.ImageDraw, xy, text, f, fill) -> None:
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
    d.text((cx - 140, y + 18), "  block 09 · deliverable", font=fm, fill=(90, 96, 108))


def shadow_for(w: int, h: int, pad: int = 20, alpha: int = 140, blur: int = 18) -> Image.Image:
    sh = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([(pad, pad), (w + pad, h + pad)], fill=(0, 0, 0, alpha))
    return sh.filter(ImageFilter.GaussianBlur(blur))


# -----------------------------------------------------------------------------
# Card builders — three output cards
# -----------------------------------------------------------------------------


def render_report_card(w: int, h: int) -> Image.Image:
    """Forensic report card — simulated page crop, formal, not a UI screenshot."""
    card = Image.new("RGBA", (w, h), PANEL + (255,))
    d = ImageDraw.Draw(card)
    d.rectangle([(0, 0), (w - 1, h - 1)], outline=BORDER, width=2)

    # title bar
    d.rectangle([(0, 0), (w, 52)], fill=(28, 30, 36))
    d.text((20, 14), "report.md", font=font(FONT_MONO_BOLD, 22), fill=FG)
    d.text((w - 170, 17), "12.7 KB · md", font=font(FONT_MONO, 18), fill=DIM)

    y = 78
    d.text((24, y), "Black Box — Forensic Report", font=font(FONT_BOLD, 24), fill=FG)
    y += 40
    d.text((24, y), "Case  sanfer_tunnel · post_mortem", font=font(FONT_MONO, 17), fill=DIM)
    y += 26
    d.text((24, y), "Duration  3626.70 s · model  claude-opus-4-7", font=font(FONT_MONO, 17), fill=DIM)

    y += 40
    d.rectangle([(24, y), (w - 24, y + 2)], fill=BORDER)
    y += 18

    d.text((24, y), "Executive Summary", font=font(FONT_BOLD, 18), fill=FG)
    y += 32

    # faint prose body block to signal "page of text"
    lorem = [
        "Moving-baseline RTCM uplink from /ublox_moving_base to",
        "/ublox_rover is silently dead for the whole session —",
        "rover's differential-input port never receives MB",
        "carrier-phase observations, so carr_soln never leaves",
        "'none'. Eighteen thousand, one hundred thirty-three of",
        "18,133 NAV-RELPOSNED messages carry carr_soln=none.",
        "/odometry/filtered never published. DBW never enabled.",
    ]
    fs = font(FONT_REG, 15)
    for line in lorem:
        d.text((24, y), line, font=fs, fill=(160, 168, 180))
        y += 22

    y += 10
    d.rectangle([(24, y), (w - 24, y + 1)], fill=(40, 44, 52))
    y += 14
    d.text((24, y), "Timeline · 13 rows", font=font(FONT_MONO, 15), fill=DIM)
    y += 22
    d.text((24, y), "Hypotheses · 5 ranked", font=font(FONT_MONO, 15), fill=DIM)
    y += 22
    d.text((24, y), "Patch proposal · 1 hunk", font=font(FONT_MONO, 15), fill=DIM)

    return card


def render_ranked_card(w: int, h: int) -> Image.Image:
    """Ranked outcome card — top-5 hypotheses with confidence bars."""
    card = Image.new("RGBA", (w, h), PANEL + (255,))
    d = ImageDraw.Draw(card)
    d.rectangle([(0, 0), (w - 1, h - 1)], outline=BORDER, width=2)

    d.rectangle([(0, 0), (w, 52)], fill=(28, 30, 36))
    d.text((20, 14), "hypotheses · ranked", font=font(FONT_MONO_BOLD, 22), fill=FG)
    d.text((w - 90, 17), "5 of 5", font=font(FONT_MONO, 18), fill=DIM)

    rows = [
        (1, "sensor_timeout",     0.60, "ROOT",       FG),
        (2, "missing_null_check", 0.55, "supporting", FG),
        (3, "other",              0.35, "partial",    DIM),
        (4, "latency_spike",      0.15, "symptom",    DIM),
        (5, "other",              0.05, "REFUTED",    (170, 86, 86)),
    ]

    y = 80
    fm = font(FONT_MONO, 18)
    fm_b = font(FONT_MONO_BOLD, 18)
    fs = font(FONT_REG, 14)
    for rank, klass, conf, tag, tag_col in rows:
        d.text((20, y), f"#{rank}", font=fm_b, fill=DIM)
        d.text((64, y), klass, font=fm, fill=FG if rank <= 2 else DIM)
        # confidence bar
        bar_x, bar_y = 320, y + 8
        bar_w, bar_h = 180, 10
        d.rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h)], fill=(40, 44, 52))
        fill_w = int(bar_w * conf)
        col = MUTED_AMBER if rank == 1 else (80, 90, 104)
        d.rectangle([(bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h)], fill=col)
        d.text((bar_x + bar_w + 14, y), f"{conf:.2f}", font=fm, fill=FG if rank == 1 else DIM)
        d.text((bar_x + bar_w + 82, y + 2), tag, font=fs, fill=tag_col)
        y += 42

    y += 6
    d.rectangle([(20, y), (w - 20, y + 1)], fill=(40, 44, 52))
    y += 12
    d.text((20, y), "root cause ranked · alternates retained · one refuted",
           font=font(FONT_REG, 14), fill=DIM)

    return card


def render_patch_card(w: int, h: int, accent_strip: bool = False) -> Image.Image:
    """Scoped patch card — 3 add lines visible, legible at card scale."""
    card = Image.new("RGBA", (w, h), PANEL + (255,))
    d = ImageDraw.Draw(card)
    d.rectangle([(0, 0), (w - 1, h - 1)], outline=BORDER, width=2)

    d.rectangle([(0, 0), (w, 52)], fill=(28, 30, 36))
    d.text((20, 14), "scoped_patch.diff", font=font(FONT_MONO_BOLD, 22), fill=FG)
    d.text((w - 160, 17), "1 file · +8 −1", font=font(FONT_MONO, 18), fill=DIM)

    y = 74
    fm = font(FONT_MONO, 15)
    fm_b = font(FONT_MONO_BOLD, 15)
    d.text((16, y), "--- a/localization/engage_gate.py", font=fm, fill=DEL_FG)
    y += 22
    d.text((16, y), "+++ b/localization/engage_gate.py", font=fm, fill=ADD_FG)
    y += 22
    d.text((16, y), "@@ def can_engage(self):", font=fm, fill=HUNK_FG)
    y += 32

    lines = [
        ("ctx", "    def can_engage(self):"),
        ("del", "        return self.dbw_ready and self.ekf_ready"),
        ("add", "        reasons = []"),
        ("add", "        if not self.rtk_heading_ok:"),
        ("add", "            reasons.append('rtk_heading_invalid')"),
        ("add", "        if reasons:"),
        ("add", "            self._diag.broadcast(ERROR, reasons)"),
        ("add", "            return False"),
        ("add", "        return True"),
    ]
    for kind, text in lines:
        row_top = y - 3
        row_bot = y + 18
        if kind == "del":
            d.rectangle([(8, row_top), (w - 8, row_bot)], fill=DEL_BG)
            d.text((16, y), "-", font=fm_b, fill=DEL_FG)
            d.text((34, y), text.lstrip(), font=fm, fill=DEL_FG)
        elif kind == "add":
            d.rectangle([(8, row_top), (w - 8, row_bot)], fill=ADD_BG)
            if accent_strip:
                d.rectangle([(8, row_top), (14, row_bot)], fill=ACCENT)
            d.text((16, y), "+", font=fm_b, fill=ADD_FG)
            d.text((34, y), text.lstrip(), font=fm, fill=ADD_FG)
        else:
            d.text((16, y), " ", font=fm_b, fill=DIM)
            d.text((34, y), text.lstrip(), font=fm, fill=FG)
        y += 22

    return card


# -----------------------------------------------------------------------------
# Beat A — bundle intro skeleton
# -----------------------------------------------------------------------------


def make_bundle_intro(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 2.5, 0.35)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 52)
    fs = font(FONT_REG, 24)
    fm = font(FONT_MONO, 20)
    fm_tag = font(FONT_MONO_BOLD, 20)

    # eyebrow tag
    tag_x, tag_y = 260, 170
    d.rectangle([(tag_x, tag_y), (tag_x + 160, tag_y + 38)], outline=MUTED_AMBER, width=2)
    d.text((tag_x + 14, tag_y + 8), "DELIVERABLE", font=fm_tag, fill=MUTED_AMBER)

    d.text((260, tag_y + 68), "not just a summary", font=fb, fill=FG)
    d.rectangle([(260, tag_y + 138), (420, tag_y + 140)], fill=ACCENT)
    d.text((260, tag_y + 160),
           "the system hands over a bundle an engineer can open and act on",
           font=fs, fill=DIM)
    d.text((260, tag_y + 196),
           "bundle · data/final_runs/sanfer_tunnel/",
           font=fm, fill=(90, 96, 108))

    # three empty placeholder slots, staggered in
    slot_w, slot_h = 440, 440
    gap = 40
    total_w = slot_w * 3 + gap * 2
    x0 = (W - total_w) // 2
    y0 = 600

    fm_lbl = font(FONT_MONO, 18)
    labels = ["forensic report", "ranked outcome", "scoped patch"]
    for i, lbl in enumerate(labels):
        # staggered appearance
        appear = max(0.0, min(1.0, (t - 0.6 - i * 0.25) / 0.5))
        alpha = int(appear * 255)
        slot_img = Image.new("RGBA", (slot_w, 120), (0, 0, 0, 0))
        sd = ImageDraw.Draw(slot_img)
        sd.rectangle([(0, 0), (slot_w - 1, 119)], outline=(40, 44, 52), width=2)
        sd.text((20, 44), lbl, font=font(FONT_MONO_BOLD, 22), fill=DIM)
        sd.text((20, 78), "…", font=font(FONT_MONO, 22), fill=(60, 64, 72))
        if alpha > 0:
            r, g, b, al = slot_img.split()
            al = al.point(lambda v: int(v * appear))
            slot_img = Image.merge("RGBA", (r, g, b, al))
            layer.alpha_composite(slot_img, (x0 + i * (slot_w + gap), y0))

    draw_beat_dots(d, active=3)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat B — three outputs reveal
# -----------------------------------------------------------------------------


def _three_card_positions():
    slot_w = 540
    slot_h_report = 560
    slot_h_ranked = 500
    slot_h_patch = 580
    gap = 40
    total_w = slot_w * 3 + gap * 2
    x0 = (W - total_w) // 2
    y0 = 260
    return x0, y0, slot_w, gap, slot_h_report, slot_h_ranked, slot_h_patch


def make_three_outputs(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 3.5, 0.4)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 38)
    fs = font(FONT_REG, 22)
    fm_lbl = font(FONT_MONO_BOLD, 20)

    d.text((260, 100), "the deliverable", font=fb, fill=FG)
    d.rectangle([(260, 156), (420, 158)], fill=ACCENT)
    d.text((260, 176), "one bundle · three outputs · human-reviewable",
           font=fs, fill=DIM)

    x0, y0, slot_w, gap, h_rep, h_rnk, h_pat = _three_card_positions()
    # vertically align all cards around same y0 center
    centers_y = y0 + max(h_rep, h_rnk, h_pat) // 2

    specs = [
        ("forensic report", render_report_card(slot_w, h_rep), h_rep),
        ("ranked outcome",  render_ranked_card(slot_w, h_rnk), h_rnk),
        ("scoped patch",    render_patch_card(slot_w, h_pat), h_pat),
    ]

    for i, (lbl, card, hc) in enumerate(specs):
        appear = max(0.0, min(1.0, (t - 0.2 - i * 0.5) / 0.6))
        if appear <= 0:
            continue
        cx = x0 + i * (slot_w + gap)
        cy = centers_y - hc // 2
        sh = shadow_for(slot_w, hc)
        sh_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sh_layer.alpha_composite(sh, (cx - 20, cy - 20))
        sh_layer.alpha_composite(card, (cx, cy))
        # label above
        ld = ImageDraw.Draw(sh_layer)
        ld.text((cx, cy - 38), lbl, font=fm_lbl, fill=MUTED_AMBER if i < 2 else ACCENT)

        # fade in
        r, g, b, al = sh_layer.split()
        al = al.point(lambda v: int(v * appear))
        sh_layer = Image.merge("RGBA", (r, g, b, al))
        layer.alpha_composite(sh_layer, (0, 0))

    draw_beat_dots(d, active=3)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat C — reviewability emphasis
# -----------------------------------------------------------------------------


def make_reviewable(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 3.5, 0.45)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 38)
    fs = font(FONT_REG, 22)
    fm_lbl = font(FONT_MONO_BOLD, 20)
    fm = font(FONT_MONO, 18)

    d.text((260, 100), "ready for review", font=fb, fill=FG)
    d.rectangle([(260, 156), (420, 158)], fill=ACCENT)
    d.text((260, 176),
           "grounded report · ranked reasoning · patch a human applies",
           font=fs, fill=DIM)

    x0, y0, slot_w, gap, h_rep, h_rnk, h_pat = _three_card_positions()
    centers_y = y0 + max(h_rep, h_rnk, h_pat) // 2

    # report + ranked: muted (dim overlay). patch: accent strip (reviewable).
    specs = [
        ("forensic report", render_report_card(slot_w, h_rep), h_rep, 0.55, False, MUTED_AMBER),
        ("ranked outcome",  render_ranked_card(slot_w, h_rnk), h_rnk, 0.55, False, MUTED_AMBER),
        ("scoped patch",    render_patch_card(slot_w, h_pat, accent_strip=True), h_pat, 1.0, True, ACCENT),
    ]

    for i, (lbl, card, hc, card_a, is_hero, lbl_col) in enumerate(specs):
        cx = x0 + i * (slot_w + gap)
        cy = centers_y - hc // 2
        sh = shadow_for(slot_w, hc)
        lyr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        lyr.alpha_composite(sh, (cx - 20, cy - 20))
        lyr.alpha_composite(card, (cx, cy))
        ld = ImageDraw.Draw(lyr)
        ld.text((cx, cy - 38), lbl, font=fm_lbl, fill=lbl_col)

        r, g, b, al = lyr.split()
        al = al.point(lambda v: int(v * card_a))
        lyr = Image.merge("RGBA", (r, g, b, al))
        layer.alpha_composite(lyr, (0, 0))

        if is_hero:
            # annotation under patch card
            note_appear = max(0.0, min(1.0, (t - 0.8) / 0.5))
            if note_appear > 0:
                note_lyr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                nd = ImageDraw.Draw(note_lyr)
                ny = cy + hc + 24
                nd.rectangle([(cx, ny), (cx + 6, ny + 40)], fill=ACCENT)
                nd.text((cx + 18, ny), "human reviews · applies", font=fm_lbl, fill=FG)
                nd.text((cx + 18, ny + 26), "system does not auto-apply", font=fm, fill=DIM)
                r2, g2, b2, a2 = note_lyr.split()
                a2 = a2.point(lambda v: int(v * note_appear))
                note_lyr = Image.merge("RGBA", (r2, g2, b2, a2))
                layer.alpha_composite(note_lyr, (0, 0))

    draw_beat_dots(d, active=3)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat D — lockup
# -----------------------------------------------------------------------------


def make_lockup(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 3.0, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 96)
    fs = font(FONT_REG, 28)
    fm = font(FONT_MONO, 20)

    draw_text_centered(d, (W // 2, H // 2 - 60), "not just a summary.", fb, FG)
    draw_text_centered(d, (W // 2, H // 2 + 50), "ready for review.", fb, ACCENT)

    d.rectangle([(W // 2 - 120, H // 2 + 150), (W // 2 + 120, H // 2 + 152)],
                fill=(60, 64, 72))
    draw_text_centered(d, (W // 2, H // 2 + 194),
                       "forensic report · ranked outcome · scoped patch",
                       fs, DIM)

    draw_text_centered(d, (W // 2, H - 120), "BLACK  BOX  —  forensic copilot",
                       fm, (90, 96, 108))

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
        return make_bundle_intro(local_t)
    if i == 1:
        return make_three_outputs(local_t)
    if i == 2:
        return make_reviewable(local_t)
    return make_lockup(local_t)


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
    report = ROOT / "data/final_runs/sanfer_tunnel/report.md"
    assert report.exists(), f"missing report: {report}"

    tmp = Path(tempfile.mkdtemp(prefix="block09_"))
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

    preview = render_at(7.5).convert("RGB")
    preview.save(OUT / "preview.png", "PNG", optimize=True)

    shutil.rmtree(tmp)
    print(f"wrote {out_mp4}")


if __name__ == "__main__":
    main()
