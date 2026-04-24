# SPDX-License-Identifier: MIT
"""Render block_08_money_shot: 14.5s, 1920x1080, 30fps.

Narration: "This is the bug. This is the fix. One scoped diff. Not a
redesign. A targeted change tied directly to the evidence the system
found."

Visual identity preserved from block_01 / block_02 / block_07:
  - BG (10,12,16), FG (230,232,236), DIM (120,128,140)
  - DejaVu Sans / Sans Mono typography
  - 80px grid backdrop, drop shadows, 4-dot beat indicator

Payoff-phase treatment:
  - amber returns to full ACCENT (255,184,64) — sparingly, only on added
    lines and the "fix" label (block_07 used MUTED_AMBER everywhere)
  - diff is the hero — one dominant composition across beats B/C
  - beat C zooms into added-lines only, everything else dimmed to keep
    focus on the scoped patch
  - beat D returns to breathing-room lockup, carrying over the
    centered-text discipline from block_07's principle card

Beats:
  A 0.0-2.0   setup: target file + "bug" label + 1-line evidence tie
  B 2.0-5.5   full diff reveal, hunks fade in
  C 5.5-11.0  zoom to added lines, amber strip, hold long
  D 11.0-14.5 lockup: "scoped diff · not a redesign"

Source: demo_assets/analyses/sanfer_tunnel.json.patch_proposal
Hero hunk: localization/engage_gate.py — matches the RTK-heading finding
surfaced in blocks 07's candidate set (project_sanfer_finding memory).
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
OUT = ROOT / "video_assets" / "block_08_money_shot"
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
ACCENT = (255, 184, 64)
PANEL = (18, 20, 26)
BORDER = (60, 66, 78)

ADD_BG = (22, 44, 28)
ADD_FG = (186, 230, 170)
DEL_BG = (54, 22, 26)
DEL_FG = (230, 150, 150)
META_FG = (140, 168, 220)
HUNK_FG = (170, 140, 220)

SOURCE = ROOT / "demo_assets/analyses/sanfer_tunnel.json"

SEG_BOUNDS = [(0.0, 2.0), (2.0, 5.5), (5.5, 11.0), (11.0, 14.5)]
XFADE = 0.4


# -----------------------------------------------------------------------------
# Real diff hunk — extracted from sanfer_tunnel.json.patch_proposal
# -----------------------------------------------------------------------------

HUNK_HEADER_A = "--- a/localization/engage_gate.py"
HUNK_HEADER_B = "+++ b/localization/engage_gate.py"
HUNK_AT = "@@ def can_engage(self):"

# (kind, text). kind ∈ {"ctx","del","add","blank"}
DIFF_LINES = [
    ("ctx", "    def can_engage(self):"),
    ("del", "        return self.dbw_ready and self.ekf_ready"),
    ("add", "        reasons = []"),
    ("add", "        if not self.dbw_ready:      reasons.append('dbw_not_ready')"),
    ("add", "        if not self.ekf_ready:      reasons.append('ekf_no_odom')"),
    ("add", "        if not self.rtk_heading_ok: reasons.append('rtk_heading_invalid')"),
    ("add", "        if reasons:"),
    ("add", "            self._diag.broadcast(ERROR, 'engage blocked: ' + ','.join(reasons))"),
    ("add", "            return False"),
    ("add", "        return True"),
]


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
    d.text((cx - 140, y + 18), "  block 08 · scoped patch", font=fm, fill=(90, 96, 108))


def shadow_for(w: int, h: int, pad: int = 20, alpha: int = 160, blur: int = 20) -> Image.Image:
    sh = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([(pad, pad), (w + pad, h + pad)], fill=(0, 0, 0, alpha))
    return sh.filter(ImageFilter.GaussianBlur(blur))


# -----------------------------------------------------------------------------
# Diff card renderer (reused for beats B and C)
# -----------------------------------------------------------------------------


def render_diff_card(
    width: int,
    line_size: int = 28,
    line_pad: int = 14,
    reveal_lines: int = 999,
    highlight_adds: bool = False,
    focus_adds_only: bool = False,
) -> Image.Image:
    """Render the diff card. reveal_lines limits how many DIFF_LINES are shown."""
    fm = font(FONT_MONO, line_size)
    fm_b = font(FONT_MONO_BOLD, line_size)
    fm_h = font(FONT_MONO_BOLD, 24)

    header_rows = 4  # two file headers + @@ line + blank
    total_rows = header_rows + len(DIFF_LINES)
    row_h = line_size + line_pad
    inner_pad_y = 32
    title_bar_h = 56
    card_h = title_bar_h + inner_pad_y * 2 + total_rows * row_h

    card = Image.new("RGBA", (width, card_h), PANEL + (255,))
    cd = ImageDraw.Draw(card)
    cd.rectangle([(0, 0), (width - 1, card_h - 1)], outline=BORDER, width=2)
    cd.rectangle([(0, 0), (width, title_bar_h)], fill=(28, 30, 36))
    cd.text((24, 14), "scoped_patch.diff", font=fm_h, fill=FG)
    cd.text((width - 260, 18), "1 file · +8 −1", font=font(FONT_MONO, 20), fill=DIM)

    x0 = 32
    y = title_bar_h + inner_pad_y

    # headers
    cd.text((x0, y), HUNK_HEADER_A, font=fm, fill=DEL_FG)
    y += row_h
    cd.text((x0, y), HUNK_HEADER_B, font=fm, fill=ADD_FG)
    y += row_h
    cd.text((x0, y), HUNK_AT, font=fm, fill=HUNK_FG)
    y += row_h * 2  # include a blank row spacer

    for i, (kind, text) in enumerate(DIFF_LINES):
        if i >= reveal_lines:
            break
        row_top = y - line_pad // 2
        row_bot = y + line_size + line_pad // 2

        if kind == "del":
            cd.rectangle([(x0 - 12, row_top), (width - 24, row_bot)], fill=DEL_BG)
            prefix = "-"
            prefix_col = DEL_FG
            line_col = DEL_FG
        elif kind == "add":
            bg = ADD_BG
            if highlight_adds:
                bg = (30, 60, 36)
            cd.rectangle([(x0 - 12, row_top), (width - 24, row_bot)], fill=bg)
            if highlight_adds:
                cd.rectangle([(x0 - 12, row_top), (x0 - 6, row_bot)], fill=ACCENT)
            prefix = "+"
            prefix_col = ADD_FG
            line_col = ADD_FG
        else:
            prefix = " "
            prefix_col = DIM
            line_col = DIM if focus_adds_only else FG

        cd.text((x0, y), prefix, font=fm_b, fill=prefix_col)
        cd.text((x0 + line_size, y), text.lstrip(), font=fm, fill=line_col)
        y += row_h

    return card


# -----------------------------------------------------------------------------
# Beat A — setup: target file + "bug" label
# -----------------------------------------------------------------------------


def make_setup_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 2.0, 0.35)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 48)
    fs = font(FONT_REG, 26)
    fm = font(FONT_MONO, 28)
    fm_b = font(FONT_MONO_BOLD, 34)
    fm_tag = font(FONT_MONO_BOLD, 22)

    # "BUG" tag, upper left zone
    tag_x, tag_y = 260, 240
    d.rectangle([(tag_x, tag_y), (tag_x + 90, tag_y + 44)], outline=ACCENT, width=2)
    d.text((tag_x + 18, tag_y + 10), "BUG", font=fm_tag, fill=ACCENT)
    d.text((tag_x + 116, tag_y + 10), "engage silently gated on RTK heading", font=fs, fill=FG)

    # file path (the subject)
    d.text((260, tag_y + 90), "localization/engage_gate.py", font=fm_b, fill=FG)

    # amber hairline
    d.rectangle([(260, tag_y + 148), (420, tag_y + 150)], fill=ACCENT)

    # 1-line evidence tie (grounded in the sanfer finding)
    d.text((260, tag_y + 174),
           "evidence: rel_pos_heading_valid = 0 for 18,133 / 18,133 RTK samples",
           font=fm, fill=DIM)
    d.text((260, tag_y + 218),
           "autonomy never engages · operators see no reason why",
           font=fm, fill=DIM)

    draw_beat_dots(d, active=3)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat B — full diff reveal
# -----------------------------------------------------------------------------


def make_diff_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 3.5, 0.4)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 38)
    fs = font(FONT_REG, 22)

    d.text((260, 70), "The fix", font=fb, fill=FG)
    d.text((260, 120), "one scoped diff · targeted change · reviewable patch",
           font=fs, fill=DIM)
    d.rectangle([(260, 160), (420, 162)], fill=ACCENT)

    # staggered reveal: header instantly, lines progressive
    # t in [0, 3.5]; lines appear between 0.2s and 2.2s
    n_lines = len(DIFF_LINES)
    prog = max(0.0, min(1.0, (t - 0.2) / 2.0))
    reveal = int(prog * n_lines + 0.5)

    card_w = 1400
    card = render_diff_card(card_w, line_size=28, line_pad=14, reveal_lines=reveal)
    card_h = card.height
    cx = (W - card_w) // 2
    cy = 210

    sh = shadow_for(card_w, card_h)
    img.alpha_composite(sh, (cx - 20, cy - 20))
    paste_alpha(img, card, (cx, cy), 1.0)

    draw_beat_dots(d, active=3)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat C — zoom to added lines, amber strip
# -----------------------------------------------------------------------------


def make_zoom_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 5.5, 0.45)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 40)
    fs = font(FONT_REG, 22)
    fm_tag = font(FONT_MONO_BOLD, 22)

    # "FIX" tag + short label
    tag_x, tag_y = 260, 80
    d.rectangle([(tag_x, tag_y), (tag_x + 90, tag_y + 44)], outline=ACCENT, width=2)
    d.text((tag_x + 24, tag_y + 10), "FIX", font=fm_tag, fill=ACCENT)
    d.text((tag_x + 116, tag_y + 4), "scoped patch", font=fb, fill=FG)
    d.text((tag_x + 116, tag_y + 52), "engage_gate.py · surface why engage blocks",
           font=fs, fill=DIM)
    d.rectangle([(260, 170), (420, 172)], fill=ACCENT)

    # larger diff card, added-lines focus (context/del dimmed by shrinking row set)
    card_w = 1500
    card = render_diff_card(
        card_w,
        line_size=32,
        line_pad=18,
        reveal_lines=999,
        highlight_adds=True,
        focus_adds_only=True,
    )
    card_h = card.height

    # may be taller than available — clip vertically to fit
    max_h = H - 330
    if card_h > max_h:
        card = card.crop((0, 0, card_w, max_h))
        card_h = max_h

    cx = (W - card_w) // 2
    cy = 200

    sh = shadow_for(card_w, card_h)
    img.alpha_composite(sh, (cx - 20, cy - 20))
    paste_alpha(img, card, (cx, cy), 1.0)

    draw_beat_dots(d, active=3)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat D — final lockup
# -----------------------------------------------------------------------------


def make_lockup_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 3.5, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 112)
    fs = font(FONT_REG, 32)
    fm = font(FONT_MONO, 22)

    draw_text_centered(d, (W // 2, H // 2 - 40), "scoped diff.", fb, FG)
    draw_text_centered(d, (W // 2, H // 2 + 80), "not a redesign.", fb, ACCENT)

    d.rectangle([(W // 2 - 120, H // 2 + 190), (W // 2 + 120, H // 2 + 192)],
                fill=(60, 64, 72))
    draw_text_centered(d, (W // 2, H // 2 + 230),
                       "targeted change · tied to surfaced evidence · reviewable",
                       fs, DIM)

    draw_text_centered(d, (W // 2, H - 120), "BLACK  BOX  —  forensic copilot", fm, (90, 96, 108))

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
        return make_setup_beat(local_t)
    if i == 1:
        return make_diff_beat(local_t)
    if i == 2:
        return make_zoom_beat(local_t)
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
    assert SOURCE.exists(), f"missing real diff source: {SOURCE}"
    # sanity: confirm hunk is in patch_proposal
    patch = json.loads(SOURCE.read_text())["patch_proposal"]
    assert "localization/engage_gate.py" in patch, "engage_gate hunk missing in source"

    tmp = Path(tempfile.mkdtemp(prefix="block08_"))
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

    preview = render_at(8.5).convert("RGB")
    preview.save(OUT / "preview.png", "PNG", optimize=True)

    shutil.rmtree(tmp)
    print(f"wrote {out_mp4}")


if __name__ == "__main__":
    main()
