# SPDX-License-Identifier: MIT
"""Render block_04_analysis_live: ~21s, 1920x1080, 30fps.

Narration: "Black Box fuses heterogeneous artifacts in one loop: telemetry,
video, and controller context. It scans the full session, surfaces moments
worth review, cross-checks signals against each other, and ranks only the
hypotheses that survive the evidence."

The backbone is a dark-theme, film-language composite of the real progress
surface (sticky header + source badge + stage pills + progress bar +
reasoning stream) — identical structure to src/black_box/ui/templates/progress.html.
The source badge shows REPLAY, honestly, because the underlying stream comes
from data/final_runs/sanfer_tunnel/stream_events.jsonl (replay mode).

All text content is repo-grounded:
  - reasoning lines from the real stream_events.jsonl (formatted like _fmt_replay_event)
  - candidate moments from analysis.json['timeline']
  - ranked hypotheses from analysis.json['hypotheses'] (confidence shown as bars)

Visual identity continuous with blocks 01/02/03/05/06/07/08/09/10.
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
OUT = ROOT / "video_assets" / "block_04_analysis_live"
OUT.mkdir(parents=True, exist_ok=True)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

W, H = 1920, 1080
FPS = 30
DUR = 21.0
N = int(DUR * FPS)

BG = (10, 12, 16)
FG = (230, 232, 236)
DIM = (120, 128, 140)
PANEL = (18, 20, 26)
PANEL2 = (22, 24, 30)
BORDER = (60, 66, 78)
ACCENT = (255, 184, 64)
MUTED_AMBER = (196, 150, 72)
MUTED_RED = (170, 86, 86)
MUTED_GREEN = (111, 178, 111)
STRIKE = (90, 94, 100)

STREAM_PATH = ROOT / "data/final_runs/sanfer_tunnel/stream_events.jsonl"
ANALYSIS_PATH = ROOT / "data/final_runs/sanfer_tunnel/analysis.json"

assert STREAM_PATH.exists(), f"missing: {STREAM_PATH}"
assert ANALYSIS_PATH.exists(), f"missing: {ANALYSIS_PATH}"


def ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def grid_bg(img: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    col = (18, 20, 26)
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


def shadow_for(w: int, h: int, pad: int = 18, alpha: int = 130, blur: int = 16) -> Image.Image:
    sh = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([(pad, pad), (w + pad, h + pad)], fill=(0, 0, 0, alpha))
    return sh.filter(ImageFilter.GaussianBlur(blur))


def text_width(f: ImageFont.FreeTypeFont, s: str) -> int:
    bbox = f.getbbox(s)
    return bbox[2] - bbox[0]


def draw_text_centered(d: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, f, fill) -> None:
    bbox = d.textbbox((0, 0), text, font=f)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    d.text((xy[0] - w // 2, xy[1] - h // 2 - bbox[1]), text, font=f, fill=fill)


def draw_beat_dots(d: ImageDraw.ImageDraw, active: int, total: int = 5) -> None:
    cx = W // 2
    y = H - 60
    gap = 28
    tot = total * gap
    start = cx - tot // 2
    fm = font(FONT_MONO, 16)
    for i in range(total):
        x = start + i * gap
        col = ACCENT if i == active else (60, 64, 72)
        d.ellipse([(x - 6, y - 6), (x + 6, y + 6)], fill=col)
    d.text((cx - 160, y + 18), "  block 04 · analysis live", font=fm, fill=(90, 96, 108))


# ---- Real content extraction ----------------------------------------------


def _fmt_replay_event(ev: dict) -> str | None:
    t = ev.get("type")
    p = ev.get("payload") or {}
    if t == "status":
        return None
    if t == "reasoning":
        return "[reasoning] (thinking...)"
    if t == "tool_call":
        name = p.get("name", "tool")
        inp = p.get("input") or {}
        prev = inp.get("command") or inp.get("file_path") or json.dumps(inp)[:120]
        return f"[tool:{name}] {str(prev)[:96]}"
    if t == "tool_result":
        text = (p.get("text") or "").replace("\n", " ")
        err = "ERR " if p.get("is_error") else ""
        return f"[result] {err}{text[:96]}"
    if t == "assistant":
        text = (p.get("text") or "").replace("\n", " ")
        return f"[assistant] {text[:100]}"
    return None


EVENTS = [json.loads(l) for l in STREAM_PATH.read_text().splitlines() if l.strip()]
REASON_LINES: list[str] = []
for ev in EVENTS:
    ln = _fmt_replay_event(ev)
    if ln:
        REASON_LINES.append(ln)

ANALYSIS = json.loads(ANALYSIS_PATH.read_text())
TIMELINE = ANALYSIS["timeline"]
HYPS = ANALYSIS["hypotheses"]


# ---- Progress card (dark-theme mirror of progress.html) -------------------


CARD_X = 120
CARD_Y = 120
CARD_W = 1080
CARD_H = 820


def _draw_source_badge(card: Image.Image, x: int, y: int, source: str = "replay") -> None:
    # mirror the light-theme .source-badge.source-replay but on dark canvas
    fm_b = font(FONT_MONO_BOLD, 22)
    label = "REPLAY"
    glyph = "▶"
    text = f"{glyph}  {label}"
    tw = text_width(fm_b, text)
    pad_x, pad_y = 14, 8
    bw = tw + pad_x * 2
    bh = 40
    d = ImageDraw.Draw(card)
    d.rectangle([(x, y), (x + bw, y + bh)], fill=(44, 40, 28), outline=MUTED_AMBER, width=2)
    d.text((x + pad_x, y + pad_y - 2), text, font=fm_b, fill=ACCENT)


def _draw_stage_pills(card: Image.Image, x: int, y: int, active_idx: int, progress: float) -> None:
    pills = ["ingest", "analyze", "report"]
    d = ImageDraw.Draw(card)
    fm_b = font(FONT_MONO_BOLD, 20)
    fm = font(FONT_MONO, 20)
    total_w = CARD_W - 80
    gap = 16
    pw = (total_w - gap * (len(pills) - 1)) // len(pills)
    for i, p in enumerate(pills):
        px = x + i * (pw + gap)
        active = i == active_idx
        done = i < active_idx
        bg = (44, 40, 28) if active else PANEL2
        border = MUTED_AMBER if active else BORDER
        d.rectangle([(px, y), (px + pw, y + 52)], fill=bg, outline=border, width=2)
        # index circle
        cx = px + 28
        cy = y + 26
        ccol = ACCENT if active else (done and MUTED_AMBER or BORDER)
        d.ellipse([(cx - 14, cy - 14), (cx + 14, cy + 14)], fill=ccol)
        idx_f = font(FONT_MONO_BOLD, 16)
        draw_text_centered(d, (cx, cy), str(i + 1), idx_f,
                           (20, 22, 28) if active else FG)
        tcol = ACCENT if active else (FG if done else DIM)
        d.text((px + 58, y + 16), p.upper(), font=fm_b if active else fm, fill=tcol)


def _draw_bar(card: Image.Image, x: int, y: int, w: int, h: int, pct: float) -> None:
    d = ImageDraw.Draw(card)
    d.rectangle([(x, y), (x + w, y + h)], fill=(34, 36, 42))
    fw = int(w * max(0.0, min(1.0, pct)))
    d.rectangle([(x, y), (x + fw, y + h)], fill=ACCENT)


def _draw_reasoning_stream(card: Image.Image, x: int, y: int, w: int, h: int,
                           lines: list[str], cursor_blink: bool, stream_done: bool) -> None:
    d = ImageDraw.Draw(card)
    # frame
    d.rectangle([(x, y), (x + w, y + h)], fill=(20, 20, 18), outline=(42, 40, 37), width=2)
    # header
    d.rectangle([(x, y), (x + w, y + 36)], fill=(30, 29, 27))
    fm = font(FONT_MONO, 15)
    fm_b = font(FONT_MONO_BOLD, 15)
    d.text((x + 14, y + 9), "FORENSIC REASONING", font=fm_b, fill=(154, 149, 138))
    # stream dot
    dot_col = MUTED_GREEN if stream_done else ACCENT
    dcx = x + w - 24
    dcy = y + 18
    d.ellipse([(dcx - 5, dcy - 5), (dcx + 5, dcy + 5)], fill=dot_col)
    # lines
    fl = font(FONT_MONO, 15)
    line_h = 24
    inner_top = y + 46
    inner_bot = y + h - 14
    max_lines = (inner_bot - inner_top) // line_h
    shown = lines[-max_lines:]
    for i, ln in enumerate(shown):
        # trim to fit width
        maxc = (w - 28) // 9
        s = ln if len(ln) <= maxc else ln[: maxc - 1] + "…"
        col = FG if i == len(shown) - 1 else (214, 208, 192)
        d.text((x + 14, inner_top + i * line_h), s, font=fl, fill=col)
    # cursor on last line
    if shown and not stream_done and cursor_blink:
        last = shown[-1]
        maxc = (w - 28) // 9
        s = last if len(last) <= maxc else last[: maxc - 1] + "…"
        cx = x + 14 + text_width(fl, s) + 4
        cy = inner_top + (len(shown) - 1) * line_h
        d.rectangle([(cx, cy + 4), (cx + 9, cy + 18)], fill=FG)


def _draw_progress_card(t: float) -> Image.Image:
    card = Image.new("RGBA", (CARD_W, CARD_H), PANEL + (255,))
    d = ImageDraw.Draw(card)
    d.rectangle([(0, 0), (CARD_W - 1, CARD_H - 1)], outline=BORDER, width=2)

    # ---- sticky header ----
    fm_b = font(FONT_MONO_BOLD, 22)
    fm = font(FONT_MONO, 20)
    fm_s = font(FONT_MONO, 18)
    d.rectangle([(0, 0), (CARD_W, 78)], fill=(28, 30, 36))
    d.rectangle([(0, 78), (CARD_W, 80)], fill=BORDER)
    d.text((32, 24), "case", font=fm_s, fill=DIM)
    d.text((88, 20), "sanfer_tunnel", font=fm_b, fill=FG)
    # badge right after name
    case_name_w = text_width(fm_b, "sanfer_tunnel")
    _draw_source_badge(card, 88 + case_name_w + 24, 18, source="replay")

    # elapsed + spend on right
    elapsed_s = int(t * 18) + 12  # honest: session elapsed counter ticks during the shot
    mm, ss = divmod(elapsed_s, 60)
    spend = 0.00 + t * 0.004  # spend counter ticks modestly; stays tiny
    d.text((CARD_W - 360, 12), "elapsed", font=fm_s, fill=DIM)
    d.text((CARD_W - 360, 34), f"{mm:02d}:{ss:02d}", font=fm_b, fill=FG)
    d.text((CARD_W - 200, 12), "spend", font=fm_s, fill=DIM)
    d.text((CARD_W - 200, 34), f"${spend:.2f}", font=fm_b, fill=FG)

    # ---- stage pills ----
    # progress schedule:
    #   0-2s:   ingest, 0.10->0.22
    #   2-5s:   ingest->analyze, 0.22->0.42
    #   5-18s:  analyze, 0.42->0.82
    #   18-21s: analyze (holds, engine running), 0.82->0.88  — do NOT jump to report
    if t < 2.5:
        pct = 0.10 + (t / 2.5) * 0.14
        active = 0
    elif t < 5.0:
        pct = 0.24 + ((t - 2.5) / 2.5) * 0.20
        active = 0 if t < 3.5 else 1
    else:
        pct = 0.44 + min(1.0, (t - 5.0) / 15.0) * 0.44
        active = 1

    _draw_stage_pills(card, 40, 108, active, pct)

    # ---- progress-head + bar ----
    stage_label_map = [
        (0, "Decoding bag and extracting frames"),
        (1, "Claude is reviewing evidence"),
    ]
    label = "Decoding bag and extracting frames" if active == 0 else "Claude is reviewing evidence"
    fm_head = font(FONT_MONO_BOLD, 22)
    d.text((40, 192), label.upper(), font=fm_head, fill=FG)
    pct_txt = f"{int(pct*100):>3d}%"
    d.text((CARD_W - 130, 192), pct_txt, font=fm_head, fill=DIM)
    _draw_bar(card, 40, 228, CARD_W - 80, 6, pct)

    # ---- reasoning stream ----
    # progressive reveal: reveal one line every ~0.45s
    n_lines = min(len(REASON_LINES), int(t / 0.45) + 2)
    shown = REASON_LINES[:n_lines]
    cursor_blink = int(t * 2) % 2 == 0
    _draw_reasoning_stream(card, 40, 260, CARD_W - 80, 450, shown,
                           cursor_blink=cursor_blink, stream_done=False)

    # ---- meta row (job / mode) ----
    fm_meta = font(FONT_MONO, 16)
    d.text((40, 728), "job", font=fm_meta, fill=DIM)
    d.text((74, 728), "replay_sanfer_tunnel_01", font=fm_meta, fill=FG)
    d.text((380, 728), "mode", font=fm_meta, fill=DIM)
    d.text((436, 728), "post_mortem", font=fm_meta, fill=FG)
    d.text((620, 728), "source", font=fm_meta, fill=DIM)
    d.text((692, 728), "data/final_runs/sanfer_tunnel", font=fm_meta, fill=FG)

    return card


# ---- Right column: evolving analysis overlays -----------------------------

RIGHT_X = 1260
RIGHT_Y = 120
RIGHT_W = 540


def _right_panel(title: str, eyebrow: str, accent: tuple[int, int, int] = ACCENT) -> Image.Image:
    panel = Image.new("RGBA", (RIGHT_W, 820), PANEL + (255,))
    d = ImageDraw.Draw(panel)
    d.rectangle([(0, 0), (RIGHT_W - 1, 819)], outline=BORDER, width=2)
    fb = font(FONT_BOLD, 30)
    fm = font(FONT_MONO_BOLD, 15)
    d.text((26, 28), eyebrow.upper(), font=fm, fill=accent)
    d.text((26, 52), title, font=fb, fill=FG)
    d.rectangle([(26, 96), (140, 98)], fill=accent)
    return panel


def _artifacts_panel() -> Image.Image:
    panel = _right_panel("scanning evidence", "heterogeneous artifacts")
    d = ImageDraw.Draw(panel)
    fm_b = font(FONT_MONO_BOLD, 18)
    fm = font(FONT_MONO, 17)
    items = [
        ("TELEMETRY", "ublox_rover_navrelposned.csv · 18,133 rows"),
        ("TELEMETRY", "ublox_rover_navpvt.csv · fix_type history"),
        ("DIAGNOSTICS", "diagnostics_nonzero_unique.csv · 10 rows"),
        ("DIAGNOSTICS", "rosout_warnings.csv · ntrip + mb driver"),
        ("VIDEO", "frame_00000.0s_dense.jpg · cam_fc"),
        ("VIDEO", "frame_01036.3s_base.jpg · cam_fc"),
        ("CONTROLLER", "twist_20hz.csv · cmd_vel history"),
        ("CONTROLLER", "steering_20hz.csv · sw_angle · sw_torque"),
    ]
    y = 130
    for i, (kind, name) in enumerate(items):
        d.rectangle([(26, y), (RIGHT_W - 26, y + 62)], fill=PANEL2, outline=BORDER, width=1)
        # kind tag
        col = {
            "TELEMETRY": MUTED_AMBER,
            "DIAGNOSTICS": MUTED_RED,
            "VIDEO": (120, 160, 200),
            "CONTROLLER": (150, 200, 150),
        }[kind]
        d.rectangle([(26, y), (32, y + 62)], fill=col)
        d.text((48, y + 8), kind, font=fm_b, fill=col)
        d.text((48, y + 32), name, font=fm, fill=FG)
        y += 72
    return panel


def _candidates_panel() -> Image.Image:
    panel = _right_panel("candidate moments", "surfaced by cross-check")
    d = ImageDraw.Draw(panel)
    fm_b = font(FONT_MONO_BOLD, 18)
    fm = font(FONT_MONO, 16)
    # pick 4 real timeline entries with varied times
    picks = [TIMELINE[0], TIMELINE[1], TIMELINE[2], TIMELINE[4]]
    y = 130
    for tl in picks:
        t_s = tl["t_ns"] / 1e9
        label = tl["label"]
        # wrap to ~56 chars
        words = label.split()
        lines = []
        cur = ""
        for w in words:
            if len(cur) + len(w) + 1 > 56:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            lines.append(cur)
        lines = lines[:2]
        box_h = 42 + 22 * len(lines)
        d.rectangle([(26, y), (RIGHT_W - 26, y + box_h)], fill=PANEL2, outline=BORDER, width=1)
        d.rectangle([(26, y), (32, y + box_h)], fill=MUTED_AMBER)
        d.text((48, y + 8), f"t = {t_s:7.2f} s", font=fm_b, fill=ACCENT)
        for i, ln in enumerate(lines):
            d.text((48, y + 32 + i * 22), ln, font=fm, fill=FG)
        y += box_h + 10
    return panel


def _hyps_panel() -> Image.Image:
    panel = _right_panel("ranked hypotheses", "only what survives evidence")
    d = ImageDraw.Draw(panel)
    fm_b = font(FONT_MONO_BOLD, 18)
    fm = font(FONT_MONO, 16)
    y = 130
    for i, h in enumerate(HYPS[:4]):
        conf = float(h.get("confidence", 0.0))
        summ = (h.get("summary") or h.get("title") or "")
        # wrap
        words = summ.split()
        lines = []
        cur = ""
        for w in words:
            if len(cur) + len(w) + 1 > 52:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        if cur:
            lines.append(cur)
        lines = lines[:2]
        is_refuted = summ.startswith("REFUTED")
        box_h = 58 + 22 * len(lines)
        bar_col = MUTED_RED if is_refuted else (ACCENT if conf >= 0.5 else MUTED_AMBER)
        d.rectangle([(26, y), (RIGHT_W - 26, y + box_h)], fill=PANEL2, outline=BORDER, width=1)
        d.rectangle([(26, y), (32, y + box_h)], fill=bar_col)
        # rank + conf bar
        d.text((48, y + 8), f"#{i+1}", font=fm_b, fill=FG)
        bar_x = 92
        bar_y = y + 14
        bar_w = 200
        d.rectangle([(bar_x, bar_y), (bar_x + bar_w, bar_y + 10)], fill=(34, 36, 42))
        d.rectangle([(bar_x, bar_y), (bar_x + int(bar_w * conf), bar_y + 10)],
                    fill=bar_col)
        d.text((bar_x + bar_w + 16, y + 6), f"{conf:.2f}", font=fm_b, fill=DIM)
        for j, ln in enumerate(lines):
            d.text((48, y + 34 + j * 22), ln, font=fm, fill=FG if not is_refuted else STRIKE)
            if is_refuted:
                tw = text_width(fm, ln)
                d.line([(48, y + 42 + j * 22), (48 + tw, y + 42 + j * 22)],
                       fill=MUTED_RED, width=2)
        y += box_h + 10
    return panel


# ---- Right-panel scheduler -----------------------------------------------
#
# Five phases map to the 5 dots at the bottom and drive the right column.
# The progress card (left) runs continuously; overlays on the right fade
# between panels so the viewer feels the engine working.
#
#   0.0 -  3.5   : "opening" — faint placeholder, focus on source badge + ingest
#   3.5 -  8.0   : "artifacts" — heterogeneous evidence types
#   8.0 - 13.0   : "cross-check" — still artifacts + overlay pulse
#   13.0 - 17.5  : "candidates" — timeline moments
#   17.5 - 21.0  : "ranked" — hypotheses with survive-evidence line


def _opening_panel() -> Image.Image:
    panel = _right_panel("analyzing…", "engine online")
    d = ImageDraw.Draw(panel)
    fm = font(FONT_MONO, 18)
    fm_b = font(FONT_MONO_BOLD, 18)
    d.text((26, 140), "fusing heterogeneous artifacts", font=fm_b, fill=FG)
    items = [
        ("telemetry", MUTED_AMBER),
        ("video frames", (120, 160, 200)),
        ("diagnostics", MUTED_RED),
        ("controller context", (150, 200, 150)),
    ]
    y = 180
    for name, col in items:
        d.ellipse([(30, y + 8), (44, y + 22)], fill=col)
        d.text((58, y + 4), name, font=fm, fill=FG)
        y += 34
    d.text((26, y + 18), "ingesting bag + bundle", font=fm, fill=DIM)
    d.text((26, y + 44), "decoding /mnt/session/uploads/", font=fm, fill=DIM)
    return panel


def _cross_check_overlay_panel() -> Image.Image:
    # same artifact panel but with cross-check connectors across the tags
    panel = _artifacts_panel()
    d = ImageDraw.Draw(panel)
    # draw faint amber hairlines connecting telemetry row to diagnostics row
    # to indicate cross-check; also telemetry to controller
    pairs = [(0, 2), (0, 6), (2, 4)]
    row_h = 72
    y0 = 130 + 31
    for a, b in pairs:
        ya = y0 + a * row_h
        yb = y0 + b * row_h
        x = RIGHT_W - 40
        d.line([(x, ya), (x + 0, yb)], fill=ACCENT, width=2)
        # end ticks
        d.line([(x - 6, ya), (x, ya)], fill=ACCENT, width=2)
        d.line([(x - 6, yb), (x, yb)], fill=ACCENT, width=2)
    # overlay label
    fm_b = font(FONT_MONO_BOLD, 16)
    d.text((RIGHT_W - 190, 100), "CROSS-CHECKING", font=fm_b, fill=ACCENT)
    return panel


# ---- Overlay labels at top of composite -----------------------------------


def _top_overlay_label(text: str, accent: tuple[int, int, int] = ACCENT) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    fb = font(FONT_BOLD, 32)
    fm = font(FONT_MONO_BOLD, 16)
    x = 120
    y = 60
    d.rectangle([(x, y + 6), (x + 8, y + 38)], fill=accent)
    d.text((x + 22, y), text, font=fb, fill=FG)
    return layer


# ---- Render ---------------------------------------------------------------


def render_at(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)

    # left: progress card
    card = _draw_progress_card(t)
    sh = shadow_for(CARD_W, CARD_H)
    img.alpha_composite(sh, (CARD_X - 18, CARD_Y - 18))
    paste_alpha(img, card, (CARD_X, CARD_Y), 1.0)

    # right: evolving panels, fade between
    # fade curves
    def weight(center: float, width: float) -> float:
        # triangular window, peaks at `center`, zero beyond ±width
        d = abs(t - center)
        return max(0.0, 1.0 - d / width)

    phases = [
        ("opening",     _opening_panel,               1.5,  2.8),
        ("artifacts",   _artifacts_panel,             6.0,  3.0),
        ("cross_check", _cross_check_overlay_panel,  10.5,  3.0),
        ("candidates",  _candidates_panel,           15.0,  3.0),
        ("ranked",      _hyps_panel,                 19.3,  2.4),
    ]

    # cache generated panels (they're pure)
    if not hasattr(render_at, "_cache"):
        render_at._cache = {}  # type: ignore[attr-defined]
    cache = render_at._cache  # type: ignore[attr-defined]

    # composite all active panels (usually only one with w~1, blend during crossfade)
    right_sh = shadow_for(RIGHT_W, 820)
    img.alpha_composite(right_sh, (RIGHT_X - 18, RIGHT_Y - 18))

    # find top 2 by weight for crossfade
    weights = [(name, fn, weight(c, w)) for name, fn, c, w in phases]
    weights.sort(key=lambda x: -x[2])
    top = [w for w in weights if w[2] > 0.01][:2]
    # normalize so card visibility stays consistent
    tot = sum(w for _, _, w in top) or 1.0
    # don't normalize — keep absolute weights so the card dims naturally at edges

    for name, fn, w in top:
        if w <= 0:
            continue
        if name not in cache:
            cache[name] = fn()
        paste_alpha(img, cache[name], (RIGHT_X, RIGHT_Y), min(1.0, w))

    # top overlay labels tied to phase center
    overlay_map = [
        ("scanning evidence",        6.0,  2.2),
        ("cross-checking",          10.5,  2.0),
        ("candidate moments",       15.0,  2.2),
        ("only what survives evidence", 19.3, 2.4),
    ]
    for text, c, w in overlay_map:
        alpha = max(0.0, 1.0 - abs(t - c) / w)
        if alpha > 0.02:
            label = _top_overlay_label(text)
            paste_alpha(img, label, (0, 0), min(1.0, alpha))

    # bottom beat dots (active by phase)
    d = ImageDraw.Draw(img)
    if t < 3.5:
        active = 0
    elif t < 8.0:
        active = 1
    elif t < 13.0:
        active = 2
    elif t < 17.5:
        active = 3
    else:
        active = 4
    draw_beat_dots(d, active=active)

    # brand lockup bottom-left
    fm = font(FONT_MONO, 14)
    d.text((120, H - 60), "BLACK  BOX  —  forensic copilot", font=fm, fill=(90, 96, 108))

    return img


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="block04_"))
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

    preview = render_at(15.0).convert("RGB")
    preview.save(OUT / "preview.png", "PNG", optimize=True)

    shutil.rmtree(tmp)
    print(f"wrote {out_mp4}")


if __name__ == "__main__":
    main()
