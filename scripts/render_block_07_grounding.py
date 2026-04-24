# SPDX-License-Identifier: MIT
"""Render block_07_grounding: 16.5s, 1920x1080, 30fps.

Narration: "And if the evidence is weak, Black Box does not force an
answer. It can return empty moments, reject low-support explanations,
and keep the report narrow. The rule is simple: no evidence, no claim."

Visual identity preserved from block_01 / block_02:
  - same bg (10,12,16), fg (230,232,236), dim (120,128,140)
  - same DejaVu Sans/Mono typography
  - same subtle 80px grid backdrop
  - same drop-shadow recipe
  - same 4-dot beat indicator

Stricter-phase treatment (intentional):
  - amber desaturated (ACCENT -> MUTED_AMBER) and used sparingly
  - only 1-2 elements on screen at once
  - long holds, no stagger swarms
  - rejection uses muted-red strike-through + greyed-out text, not motion
  - final principle card breathes — generous margins
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
OUT = ROOT / "video_assets" / "block_07_grounding"
OUT.mkdir(parents=True, exist_ok=True)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

W, H = 1920, 1080
FPS = 30
DUR = 16.5
N = int(DUR * FPS)

# shared palette
BG = (10, 12, 16)
FG = (230, 232, 236)
DIM = (120, 128, 140)
PANEL = (18, 20, 26)
BORDER = (60, 66, 78)

# stricter-phase modifiers
MUTED_AMBER = (196, 150, 72)     # desaturated from (255,184,64)
MUTED_RED = (170, 86, 86)        # for "rejected" marks
STRIKE = (90, 94, 100)

# Real grounding gate evidence
RAW_PATH = ROOT / "demo_assets/grounding_gate/clean_recording/raw_hypotheses.json"
DROPS_PATH = ROOT / "demo_assets/grounding_gate/clean_recording/drop_reasons.json"
GATED_PATH = ROOT / "demo_assets/grounding_gate/clean_recording/gated_report.json"

SEG_BOUNDS = [(0.0, 3.2), (3.2, 7.0), (7.0, 11.5), (11.5, 16.5)]
XFADE = 0.45  # slightly slower than block_01/02 — clinical cadence


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
        col = MUTED_AMBER if i == active else (60, 64, 72)
        d.ellipse([(x - 6, y - 6), (x + 6, y + 6)], fill=col)
    d.text((cx - 120, y + 18), "  block 07 · grounding", font=fm, fill=(90, 96, 108))


def shadow_for(w: int, h: int, pad: int = 20, alpha: int = 140, blur: int = 18) -> Image.Image:
    sh = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([(pad, pad), (w + pad, h + pad)], fill=(0, 0, 0, alpha))
    return sh.filter(ImageFilter.GaussianBlur(blur))


# -----------------------------------------------------------------------------
# Load real data
# -----------------------------------------------------------------------------

RAW = json.loads(RAW_PATH.read_text())
DROPS = json.loads(DROPS_PATH.read_text())
GATED = json.loads(GATED_PATH.read_text())

# Build candidate list with drop reason (real data, one-to-one with RAW hypotheses)
CANDIDATES = []
for h, drop in zip(RAW["hypotheses"], DROPS):
    CANDIDATES.append({
        "bug_class": h["bug_class"],
        "confidence": h["confidence"],
        "summary": h["summary"],
        "evidence_n": len(h["evidence"]),
        "reason_dropped": drop["reason_dropped"],
    })

# -----------------------------------------------------------------------------
# Reusable: candidate row renderer
# -----------------------------------------------------------------------------


def render_candidate_row(cand: dict, rejected: bool, width: int = 1400, height: int = 130) -> Image.Image:
    row = Image.new("RGBA", (width, height), PANEL + (255,))
    d = ImageDraw.Draw(row)
    outline = (60, 30, 30) if rejected else BORDER
    d.rectangle([(0, 0), (width - 1, height - 1)], outline=outline, width=2)

    fb = font(FONT_MONO_BOLD, 26)
    fs = font(FONT_REG, 22)
    fm = font(FONT_MONO, 18)

    title_col = STRIKE if rejected else FG
    meta_col = STRIKE if rejected else DIM
    d.text((32, 22), cand["bug_class"], font=fb, fill=title_col)

    # confidence pill
    conf = cand["confidence"]
    pill_x = 420
    pill_col = (60, 30, 30) if rejected else (30, 34, 42)
    d.rectangle([(pill_x, 24), (pill_x + 170, 60)], fill=pill_col)
    d.text((pill_x + 14, 30), f"conf {conf:.2f}", font=fm, fill=title_col)

    # evidence count
    ev_x = pill_x + 190
    d.text((ev_x, 30), f"evidence: {cand['evidence_n']}", font=fm, fill=meta_col)

    # summary line
    summary = cand["summary"]
    if len(summary) > 92:
        summary = summary[:89] + "…"
    d.text((32, 78), summary, font=fs, fill=meta_col)

    if rejected:
        # red strike-through across title + summary zone
        sy1 = 36
        sy2 = 92
        d.line([(24, sy1), (width - 24, sy1)], fill=MUTED_RED, width=2)
        d.line([(24, sy2), (width - 24, sy2)], fill=MUTED_RED, width=2)
        # right-side REJECTED tag
        tag_w = 230
        tag_x = width - tag_w - 20
        d.rectangle([(tag_x, 40), (tag_x + tag_w, 90)], outline=MUTED_RED, width=2)
        d.text((tag_x + 18, 50), "REJECTED", font=fb, fill=MUTED_RED)

    return row


# -----------------------------------------------------------------------------
# Beat A — candidates under review (all neutral)
# -----------------------------------------------------------------------------


def make_candidates_beat(t: float, rejected_count: int = 0, show_reasons: bool = False) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 3.2, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 42)
    fs = font(FONT_REG, 24)
    fm = font(FONT_MONO, 20)

    d.text((260, 80), "Candidates under review", font=fb, fill=FG)
    d.text((260, 136), "4 hypotheses emitted by the model · grounding gate pending", font=fs, fill=DIM)

    # muted amber hairline
    d.rectangle([(260, 180), (420, 182)], fill=MUTED_AMBER)

    # four rows
    row_w = 1400
    row_h = 130
    gap = 18
    start_y = 220
    start_x = (W - row_w) // 2
    for i, cand in enumerate(CANDIDATES):
        rejected = i < rejected_count
        row = render_candidate_row(cand, rejected=rejected, width=row_w, height=row_h)
        y = start_y + i * (row_h + gap)
        sh = shadow_for(row_w, row_h)
        img.alpha_composite(sh, (start_x - 20, y - 20))
        paste_alpha(img, row, (start_x, y), 1.0)

    # annotation to the right of most recently rejected (shown once all rejected? optional)
    if show_reasons and rejected_count > 0:
        # show the drop-reason callout for the most recently rejected row
        idx = rejected_count - 1
        cand = CANDIDATES[idx]
        y = start_y + idx * (row_h + gap)
        callout_x = start_x + row_w + 40
        if callout_x + 400 < W:
            d.text((callout_x, y + 32), "drop reason", font=fm, fill=MUTED_AMBER)
            reason = cand["reason_dropped"]
            # wrap
            lines = wrap_text(reason, 24)
            for li, ln in enumerate(lines[:3]):
                d.text((callout_x, y + 62 + li * 26), ln, font=fm, fill=FG)

    draw_beat_dots(d, active=2)
    paste_alpha(img, layer, (0, 0), a)
    return img


def wrap_text(s: str, max_chars: int) -> list[str]:
    words = s.split()
    out, cur = [], ""
    for w in words:
        if len(cur) + 1 + len(w) <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


# -----------------------------------------------------------------------------
# Beat B — progressive rejection with reasons (one-by-one, long holds)
# -----------------------------------------------------------------------------


def make_rejection_beat(t: float) -> Image.Image:
    # Over 3.8s, reject candidates one at a time at t = 0.4, 1.3, 2.2, 3.1
    schedule = [0.4, 1.3, 2.2, 3.1]
    rejected_count = sum(1 for ts in schedule if t >= ts)
    return make_candidates_beat(t, rejected_count=rejected_count, show_reasons=True)


# -----------------------------------------------------------------------------
# Beat C — narrowed report (empty hypotheses array hero)
# -----------------------------------------------------------------------------


def make_narrowed_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 4.5, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 44)
    fs = font(FONT_REG, 26)
    fm = font(FONT_MONO, 28)
    fm_b = font(FONT_MONO_BOLD, 28)

    d.text((260, 80), "Narrowed report", font=fb, fill=FG)
    d.text((260, 136), "all four candidates dropped · report emitted empty", font=fs, fill=DIM)
    d.rectangle([(260, 180), (420, 182)], fill=MUTED_AMBER)

    # single large JSON card, mono, centered
    card_w = 1200
    card_h = 500
    cx = (W - card_w) // 2
    cy = 260
    card = Image.new("RGBA", (card_w, card_h), PANEL + (255,))
    cd = ImageDraw.Draw(card)
    cd.rectangle([(0, 0), (card_w - 1, card_h - 1)], outline=BORDER, width=2)
    cd.rectangle([(0, 0), (card_w, 52)], fill=(28, 30, 36))
    cd.text((20, 14), "gated_report.json", font=fm_b, fill=FG)

    lines = [
        ("{",                                                         FG),
        ('  "timeline": [ … 2 markers … ],',                          DIM),
        ('  "hypotheses": [],',                                       MUTED_AMBER),
        ('  "root_cause_idx": 0,',                                    DIM),
        ('  "patch_proposal":',                                       FG),
        ('    "No anomaly detected with sufficient evidence',          FG),
        ('     to support a scoped fix."',                             FG),
        ("}",                                                         FG),
    ]
    y = 90
    for line, col in lines:
        cd.text((40, y), line, font=fm, fill=col)
        y += 44

    sh = shadow_for(card_w, card_h)
    img.alpha_composite(sh, (cx - 20, cy - 20))
    paste_alpha(img, card, (cx, cy), 1.0)

    # tag: "empty moment"
    tag_fs = font(FONT_MONO_BOLD, 22)
    d.text((cx, cy + card_h + 24), "empty moment · insufficient evidence · narrowed report",
           font=tag_fs, fill=DIM)

    draw_beat_dots(d, active=2)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat D — principle card (breathing room)
# -----------------------------------------------------------------------------


def make_principle_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)

    a = fade_alpha(t, 5.0, 0.6)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 110)
    fs = font(FONT_REG, 32)
    fm = font(FONT_MONO, 22)

    # generous negative space — text sits center
    draw_text_centered(d, (W // 2, H // 2 - 40), "no evidence,", fb, FG)
    draw_text_centered(d, (W // 2, H // 2 + 80), "no claim.", fb, MUTED_AMBER)

    # hairline divider above subtitle
    d.rectangle([(W // 2 - 120, H // 2 + 190), (W // 2 + 120, H // 2 + 192)], fill=(60, 64, 72))
    draw_text_centered(d, (W // 2, H // 2 + 230),
                       "grounding gate · min 2 evidence · min 2 sources · conf ≥ 0.40",
                       fs, DIM)

    draw_text_centered(d, (W // 2, H - 120), "BLACK  BOX  —  forensic copilot", fm, (90, 96, 108))

    draw_beat_dots(d, active=2)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Render
# -----------------------------------------------------------------------------


def crossfade(a: Image.Image, b: Image.Image, u: float) -> Image.Image:
    return Image.blend(a, b, u)


def _seg(i: int, local_t: float) -> Image.Image:
    if i == 0:
        return make_candidates_beat(local_t, rejected_count=0)
    if i == 1:
        return make_rejection_beat(local_t)
    if i == 2:
        return make_narrowed_beat(local_t)
    return make_principle_beat(local_t)


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
    tmp = Path(tempfile.mkdtemp(prefix="block07_"))
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

    preview = render_at(14.0).convert("RGB")
    preview.save(OUT / "preview.png", "PNG", optimize=True)

    shutil.rmtree(tmp)
    print(f"wrote {out_mp4}")


if __name__ == "__main__":
    main()
