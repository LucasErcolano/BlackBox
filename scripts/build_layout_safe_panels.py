"""Rebuild every text-heavy still panel with measured layout.

For each panel we draw using PIL with real ``textbbox`` measurements,
keep all text inside a 1920x1080 safe area (96/1824 x, 72/1008 y), and
emit:

  * ``<panel>.png`` — production frame.
  * ``<panel>.qa.png`` — debug overlay (safe area + cards + text bboxes).
  * ``<panel>.layout.json`` — sidecar consumed by qa_panel_layout.py.

Panels rebuilt:

  * opus47_delta_panel — 4 big tiles per the demo brief.
  * operator_vs_blackbox — refutation contrast, 2 cards.
  * breadth_montage — 4 case tiles.

Numbers come from the canonical bench JSONs in ``data/bench_runs/``.
No fabrication.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "demo_assets/final_demo_pack/panels"
OUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
SAFE = {"x_min": 96, "x_max": 1824, "y_min": 72, "y_max": 1008}

BG = (10, 12, 16)
PANEL = (22, 25, 32)
PANEL_2 = (28, 32, 40)
LINE = (60, 66, 78)
INK = (231, 234, 238)
INK_2 = (200, 205, 214)
MUTED = (122, 128, 144)
AMBER = (255, 184, 64)
TEAL = (98, 212, 200)
RED = (224, 98, 90)
GREEN = (95, 178, 122)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


@dataclass
class TextBox:
    x: int
    y: int
    w: int
    h: int
    text: str
    font_size: int
    role: str = "body"
    card: str | None = None


@dataclass
class Card:
    id: str
    x: int
    y: int
    w: int
    h: int


@dataclass
class Layout:
    panel: str
    frame: tuple[int, int] = (W, H)
    cards: list[Card] = field(default_factory=list)
    texts: list[TextBox] = field(default_factory=list)


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int, int, int]:
    """Return (left, top, w, h) for a baseline-anchored draw."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_text(
    draw: ImageDraw.ImageDraw,
    layout: Layout,
    x: int,
    y: int,
    text: str,
    font_path: str,
    font_size: int,
    fill: tuple[int, int, int] | tuple[int, int, int, int],
    role: str = "body",
    card: str | None = None,
    align: str = "left",
) -> TextBox:
    f = _font(font_path, font_size)
    left, top, w, h = _measure(draw, text, f)
    if align == "center":
        x -= w // 2
    elif align == "right":
        x -= w
    # PIL draws the glyph relative to its own bbox top-left; subtract `top`
    # so the visible top of the text lands exactly on `y`.
    draw.text((x - left, y - top), text, font=f, fill=fill)
    box = TextBox(x=x, y=y, w=w, h=h, text=text, font_size=font_size, role=role, card=card)
    layout.texts.append(box)
    return box


def _shrink_to_fit(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    start_size: int,
    floor: int,
    max_w: int,
) -> int:
    s = start_size
    while s >= floor:
        f = _font(font_path, s)
        _, _, w, _ = _measure(draw, text, f)
        if w <= max_w:
            return s
        s -= 1
    return floor


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    font_size: int,
    max_w: int,
    max_lines: int,
) -> list[str]:
    f = _font(font_path, font_size)
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        _, _, tw, _ = _measure(draw, trial, f)
        if tw <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines


def _card(layout: Layout, draw: ImageDraw.ImageDraw, cid: str, x: int, y: int, w: int, h: int,
          fill: tuple[int, int, int] = PANEL, border: tuple[int, int, int] = LINE,
          accent: tuple[int, int, int] | None = None) -> Card:
    draw.rectangle([(x, y), (x + w - 1, y + h - 1)], fill=fill, outline=border, width=2)
    if accent is not None:
        draw.rectangle([(x, y), (x + 6, y + h - 1)], fill=accent)
    c = Card(id=cid, x=x, y=y, w=w, h=h)
    layout.cards.append(c)
    return c


def _new_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # subtle grid
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=(18, 20, 26), width=1)
    for y in range(0, H, 80):
        d.line([(0, y), (W, y)], fill=(18, 20, 26), width=1)
    return img, d


def _save(img: Image.Image, layout: Layout, out_png: Path) -> None:
    img.save(out_png, "PNG", optimize=True)
    sidecar = out_png.with_suffix(".layout.json")
    sidecar.write_text(json.dumps(
        {
            "panel": layout.panel,
            "frame": list(layout.frame),
            "safe_area": SAFE,
            "cards": [c.__dict__ for c in layout.cards],
            "texts": [t.__dict__ for t in layout.texts],
        },
        indent=2,
    ))
    qa = img.copy()
    qd = ImageDraw.Draw(qa, "RGBA")
    qd.rectangle([(SAFE["x_min"], SAFE["y_min"]), (SAFE["x_max"], SAFE["y_max"])],
                 outline=(255, 184, 64, 200), width=3)
    for c in layout.cards:
        qd.rectangle([(c.x, c.y), (c.x + c.w, c.y + c.h)],
                     outline=(98, 212, 200, 220), width=2)
    for t in layout.texts:
        qd.rectangle([(t.x, t.y), (t.x + t.w, t.y + t.h)],
                     outline=(224, 98, 90, 220), width=1)
    qa.save(out_png.with_suffix(".qa.png"), "PNG", optimize=True)


# -----------------------------------------------------------------------------
# Bench data load
# -----------------------------------------------------------------------------

BENCH_NONE = ROOT / "data/bench_runs/opus46_vs_opus47_20260425T182237Z.json"
BENCH_FALSE = ROOT / "data/bench_runs/opus46_vs_opus47_20260425T183141Z.json"
BENCH_VISION = ROOT / "data/bench_runs/opus_vision_d1_20260425T185628Z.json"


def _agg(path: Path, model: str) -> dict:
    d = json.loads(path.read_text())
    return next(a for a in d["aggregates"] if a["model"] == model)


# -----------------------------------------------------------------------------
# Panel: opus47_delta_panel — 4 big tiles
# -----------------------------------------------------------------------------

def build_opus47_panel() -> Path:
    a46_n = _agg(BENCH_NONE, "claude-opus-4-6")
    a47_n = _agg(BENCH_NONE, "claude-opus-4-7")
    a46_f = _agg(BENCH_FALSE, "claude-opus-4-6")
    a47_f = _agg(BENCH_FALSE, "claude-opus-4-7")
    v46 = _agg(BENCH_VISION, "claude-opus-4-6")
    v47 = _agg(BENCH_VISION, "claude-opus-4-7")

    img, d = _new_canvas()
    layout = Layout(panel="opus47_delta_panel")

    # Heading band — single headline + supporting label
    _draw_text(d, layout, 96, 96,
               "Opus 4.7 vs 4.6", FONT_BOLD, 64, INK, role="heading")
    _draw_text(d, layout, 96, 176,
               "same accuracy · better judgment · sharper eyes",
               FONT_REG, 32, MUTED, role="label")

    # 4 tiles in 2x2 grid inside the safe area
    grid_x0 = 96
    grid_y0 = 280
    grid_w = SAFE["x_max"] - grid_x0           # 1728
    grid_h = SAFE["y_max"] - grid_y0           # 728
    gap = 32
    tile_w = (grid_w - gap) // 2               # 848
    tile_h = (grid_h - gap) // 2               # 348

    tiles = [
        ("tile_acc", "Same accuracy",
         f"{int(round(a46_n['solvable_accuracy']*100))}%",
         f"{int(round(a47_n['solvable_accuracy']*100))}%",
         "solvable bench · n=12 runs", AMBER, AMBER),
        ("tile_abs", "Better abstention",
         f"{int(round(a46_n['abstention_correctness']*100))}%",
         f"{int(round(a47_n['abstention_correctness']*100))}%",
         "under-specified case · n=3 each", RED, TEAL),
        ("tile_brier", "Better calibration",
         f"{a46_f['brier_score']:.3f}",
         f"{a47_f['brier_score']:.3f}",
         "Brier ↓ under wrong-operator framing", RED, TEAL),
        ("tile_vis", "More visual detail",
         f"{int(round(v46['detection_rate']*3))}/3",
         f"{int(round(v47['detection_rate']*3))}/3",
         "10pt token @ 3.84 MP · n=3", RED, TEAL),
    ]

    for i, (cid, title, v46_str, v47_str, sub, c46, c47) in enumerate(tiles):
        col = i % 2
        row = i // 2
        x = grid_x0 + col * (tile_w + gap)
        y = grid_y0 + row * (tile_h + gap)
        _card(layout, d, cid, x, y, tile_w, tile_h, fill=PANEL, border=LINE,
              accent=AMBER if i == 0 else None)

        pad = 28
        _draw_text(d, layout, x + pad, y + pad,
                   title, FONT_BOLD, 36, INK, role="heading", card=cid)

        # Two columns: 4.6 / 4.7
        col_y = y + pad + 60
        col_h = tile_h - pad - 80
        col_label_y = col_y
        value_y = col_y + 40
        col_w = (tile_w - 2 * pad) // 2

        # 4.6 column
        _draw_text(d, layout, x + pad, col_label_y,
                   "4.6", FONT_MONO_BOLD, 24, MUTED, role="label", card=cid)
        _draw_text(d, layout, x + pad, value_y,
                   v46_str, FONT_BOLD, 88, c46, role="heading", card=cid)
        # 4.7 column
        _draw_text(d, layout, x + pad + col_w, col_label_y,
                   "4.7", FONT_MONO_BOLD, 24, AMBER, role="label", card=cid)
        _draw_text(d, layout, x + pad + col_w, value_y,
                   v47_str, FONT_BOLD, 88, c47, role="heading", card=cid)

        # Footer label, shrunk to fit if necessary
        max_w = tile_w - 2 * pad
        size = _shrink_to_fit(d, sub, FONT_REG, 26, 22, max_w)
        sub_y = y + tile_h - pad - size - 4
        _draw_text(d, layout, x + pad, sub_y, sub, FONT_REG, size, MUTED,
                   role="label", card=cid)

    out = OUT_DIR / "opus47_delta_panel.png"
    _save(img, layout, out)
    return out


# -----------------------------------------------------------------------------
# Panel: operator_vs_blackbox — refutation contrast, 2 cards
# -----------------------------------------------------------------------------

def build_operator_panel() -> Path:
    img, d = _new_canvas()
    layout = Layout(panel="operator_vs_blackbox")

    _draw_text(d, layout, 96, 96, "Refutation",
               FONT_MONO_BOLD, 28, AMBER, role="label")
    _draw_text(d, layout, 96, 144, "Operator theory rejected by evidence.",
               FONT_BOLD, 60, INK, role="heading")

    # Two contrast cards side-by-side
    card_y = 280
    card_h = 660
    gap = 40
    card_w = (SAFE["x_max"] - SAFE["x_min"] - gap) // 2  # 844
    left_x = SAFE["x_min"]
    right_x = left_x + card_w + gap

    # ---- left: operator hypothesis ----
    _card(layout, d, "operator", left_x, card_y, card_w, card_h,
          fill=PANEL, border=LINE, accent=RED)
    pad = 36
    _draw_text(d, layout, left_x + pad, card_y + pad,
               "OPERATOR THEORY", FONT_MONO_BOLD, 22, RED, role="label", card="operator")
    _draw_text(d, layout, left_x + pad, card_y + pad + 56,
               "“tunnel”", FONT_BOLD, 96, INK, role="heading", card="operator")

    sub_lines = [
        "GPS anomaly at tunnel entry",
        "caused behavior degradation",
    ]
    line_y = card_y + pad + 56 + 110 + 24
    for ln in sub_lines:
        _draw_text(d, layout, left_x + pad, line_y, ln,
                   FONT_REG, 32, INK_2, role="body", card="operator")
        line_y += 44

    # call-out chip
    chip_label = "localized · single moment"
    chip_size = _shrink_to_fit(d, chip_label, FONT_MONO, 26, 22, card_w - 2 * pad)
    chip_y = card_y + card_h - pad - chip_size - 4
    _draw_text(d, layout, left_x + pad, chip_y, chip_label,
               FONT_MONO, chip_size, MUTED, role="label", card="operator")

    # ---- right: black box finding ----
    _card(layout, d, "blackbox", right_x, card_y, card_w, card_h,
          fill=PANEL, border=LINE, accent=TEAL)
    _draw_text(d, layout, right_x + pad, card_y + pad,
               "BLACK BOX FINDING", FONT_MONO_BOLD, 22, TEAL, role="label", card="blackbox")
    _draw_text(d, layout, right_x + pad, card_y + pad + 56,
               "no RTK heading", FONT_BOLD, 76, INK, role="heading", card="blackbox")

    metric_y = card_y + pad + 56 + 110 + 24
    _draw_text(d, layout, right_x + pad, metric_y,
               "rel_pos_heading_valid = 0", FONT_MONO_BOLD, 30, AMBER,
               role="body", card="blackbox")
    _draw_text(d, layout, right_x + pad, metric_y + 46,
               "for 18,133 / 18,133 RTK samples", FONT_MONO, 28, INK_2,
               role="body", card="blackbox")
    _draw_text(d, layout, right_x + pad, metric_y + 92,
               "session-wide · not just tunnel", FONT_REG, 28, MUTED,
               role="body", card="blackbox")

    chip2 = "evidence ⊆ data/final_runs/sanfer_tunnel/"
    chip2_size = _shrink_to_fit(d, chip2, FONT_MONO, 26, 22, card_w - 2 * pad)
    chip2_y = card_y + card_h - pad - chip2_size - 4
    _draw_text(d, layout, right_x + pad, chip2_y, chip2,
               FONT_MONO, chip2_size, MUTED, role="label", card="blackbox")

    out = OUT_DIR / "operator_vs_blackbox.png"
    _save(img, layout, out)
    return out


# -----------------------------------------------------------------------------
# Panel: breadth_montage — 4 case tiles + headline
# -----------------------------------------------------------------------------

CASES = [
    ("rtk_heading_break_01", "RTK heading break", "AV", "rel_pos_heading_valid = 0"),
    ("boat_lidar_01", "Boat LiDAR drift", "Boat", "echo timing > sensor_timeout"),
    ("sensor_timeout_01", "Sensor timeout", "Car", "imu stale > 200 ms"),
    ("pid_saturation_01", "PID saturation", "Sim", "integral windup, no clamp"),
]


def build_breadth_panel() -> Path:
    img, d = _new_canvas()
    layout = Layout(panel="breadth_montage")

    _draw_text(d, layout, 96, 96, "Breadth",
               FONT_MONO_BOLD, 28, AMBER, role="label")
    _draw_text(d, layout, 96, 144,
               "One copilot · four platforms.", FONT_BOLD, 60, INK, role="heading")

    grid_x0 = 96
    grid_y0 = 280
    grid_w = SAFE["x_max"] - grid_x0
    grid_h = SAFE["y_max"] - grid_y0
    gap = 32
    tile_w = (grid_w - gap) // 2  # 848
    tile_h = (grid_h - gap) // 2  # 348

    for i, (cid, title, platform, evidence) in enumerate(CASES):
        col = i % 2
        row = i // 2
        x = grid_x0 + col * (tile_w + gap)
        y = grid_y0 + row * (tile_h + gap)
        _card(layout, d, cid, x, y, tile_w, tile_h, fill=PANEL, border=LINE,
              accent=AMBER if i == 0 else None)
        pad = 32
        _draw_text(d, layout, x + pad, y + pad,
                   platform.upper(), FONT_MONO_BOLD, 24, AMBER if i == 0 else MUTED,
                   role="label", card=cid)

        # Title — shrink to fit then wrap to max 2 lines
        max_w = tile_w - 2 * pad
        title_size = _shrink_to_fit(d, title, FONT_BOLD, 56, 36, max_w)
        title_lines = _wrap(d, title, FONT_BOLD, title_size, max_w, max_lines=2)
        ty = y + pad + 48
        for ln in title_lines:
            _draw_text(d, layout, x + pad, ty, ln, FONT_BOLD, title_size, INK,
                       role="heading", card=cid)
            ty += int(title_size * 1.15)

        # Evidence line — mono, shrunk if needed
        ev_size = _shrink_to_fit(d, evidence, FONT_MONO, 28, 22, max_w)
        ev_y = y + tile_h - pad - ev_size - 8
        _draw_text(d, layout, x + pad, ev_y, evidence, FONT_MONO, ev_size,
                   INK_2, role="body", card=cid)

        # Sub-label between heading and evidence
        sub_label = "evidence:"
        sub_size = 22
        _draw_text(d, layout, x + pad, ev_y - 32, sub_label, FONT_MONO_BOLD,
                   sub_size, MUTED, role="label", card=cid)

    out = OUT_DIR / "breadth_montage.png"
    _save(img, layout, out)
    return out


def main() -> None:
    a = build_opus47_panel()
    b = build_operator_panel()
    c = build_breadth_panel()
    for p in (a, b, c):
        print(f"wrote {p}")
        print(f"  qa     {p.with_suffix('.qa.png')}")
        print(f"  layout {p.with_suffix('.layout.json')}")


if __name__ == "__main__":
    main()
