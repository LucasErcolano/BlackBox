"""Render block_02_problem: 13.5s, 1920x1080, 30fps.

Narration: "Robotics teams collect more sessions than any human can review
end-to-end. Logs, video, controller behavior, sensor traces — the evidence
is there, but the forensic work is still manual."

Visual language matches block_01_hook:
  - BG (10,12,16), FG (230,232,236), DIM (120,128,140), ACCENT amber (255,184,64)
  - DejaVu Sans / Sans Mono fonts
  - grid backdrop, drop shadows, progress dots
  - 350ms eased crossfades between beats

Beats:
  A 0.0-2.5   title + repo tree scrolling in
  B 2.5-6.0   folder-listing montage (5 real listings animating in)
  C 6.0-10.0  5-tile grid of real evidence types (plot, frame, log, code, trace)
              with an amber highlight traversing tile by tile
  D 10.0-13.5 final lockup: "Too much evidence." / "Manual forensic work."
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
OUT = ROOT / "video_assets" / "block_02_problem"
OUT.mkdir(parents=True, exist_ok=True)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

W, H = 1920, 1080
FPS = 30
DUR = 13.5
N = int(DUR * FPS)

BG = (10, 12, 16)
FG = (230, 232, 236)
DIM = (120, 128, 140)
ACCENT = (255, 184, 64)
PANEL = (18, 20, 26)
BORDER = (60, 66, 78)

PLOT = ROOT / "demo_assets/diff_viewer/moving_base_rover.png"
FRAME = ROOT / "demo_assets/bag_footage/car_1/frame_0045s.jpg"
PATCH = ROOT / "data/patches/054061f2c1f9.json"
COSTS = ROOT / "data/costs.jsonl"

SEG_BOUNDS = [(0.0, 2.5), (2.5, 6.0), (6.0, 10.0), (10.0, 13.5)]
XFADE = 0.35


def ease(t: float) -> float:
    return t * t * (3 - 2 * t)


def fade_alpha(local_t: float, dur: float, fade: float = 0.35) -> float:
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
    labels = ["title", "evidence", "why", "diff"]  # aligned with block_01
    # block_02 is part of "title/problem/..." arc — we expose 4 dots shared with block_01 set
    total = 4 * gap
    start = cx - total // 2
    fm = font(FONT_MONO, 16)
    for i in range(4):
        x = start + i * gap
        col = ACCENT if i == active else (60, 64, 72)
        d.ellipse([(x - 6, y - 6), (x + 6, y + 6)], fill=col)
    d.text((cx - 95, y + 18), "  block 02 · problem", font=fm, fill=(90, 96, 108))


def shadow_for(w: int, h: int, pad: int = 20, alpha: int = 160, blur: int = 14) -> Image.Image:
    sh = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([(pad, pad), (w + pad, h + pad)], fill=(0, 0, 0, alpha))
    return sh.filter(ImageFilter.GaussianBlur(blur))


# -----------------------------------------------------------------------------
# Real repo evidence — gathered once
# -----------------------------------------------------------------------------

TREE_LINES = [
    "BlackBox/",
    "├── src/black_box/",
    "│   ├── ingestion/     rosbag parser, frame sampler",
    "│   ├── analysis/      Claude client, prompts, schemas",
    "│   ├── synthesis/     bug injection, controllers",
    "│   ├── reporting/     NTSB-style reports, diffs",
    "│   └── eval/          3-tier runner",
    "├── data/",
    "│   ├── bags/          rosbags (55 GB+ per session)",
    "│   ├── reports/       generated post-mortems",
    "│   ├── patches/       scoped unified diffs",
    "│   └── costs.jsonl    token + USD log",
    "├── demo_assets/",
    "│   ├── bag_footage/   extracted video frames",
    "│   ├── diff_viewer/   RTK + controller plots",
    "│   └── analyses/      JSON findings per case",
    "├── black-box-bench/",
    "│   └── cases/         7 forensic cases",
    "└── scripts/           37 render + analysis tools",
]


def listing_data(label: str, count_label: str, lines: list[str]) -> dict:
    return {"label": label, "count": count_label, "lines": lines}


LISTINGS = [
    listing_data(
        "data/bags/", "1 session · 55.8 GB",
        ["1_cam-lidar.bag        55816 MB",
         "sample/",
         ".gitkeep"],
    ),
    listing_data(
        "demo_assets/bag_footage/", "3 sessions",
        ["boat_lidar/",
         "car_1/",
         "sanfer_tunnel/",
         "README.md"],
    ),
    listing_data(
        "black-box-bench/cases/", "7 cases",
        ["bad_gain_01/",
         "boat_lidar_01/",
         "pid_saturation_01/",
         "reflect_public_01/",
         "rtk_heading_break_01/",
         "sensor_drop_cameras_01/",
         "sensor_timeout_01/"],
    ),
    listing_data(
        "scripts/", "37 scripts",
        ["analyze_bag_v2.py",
         "build_sanfer_timelapse.py",
         "extract_windows_v2.py",
         "final_pipeline.py",
         "render_rtk_diff.py",
         "..."],
    ),
    listing_data(
        "docs/", "8 docs",
        ["DEMO_SCRIPT.md",
         "ONBOARDING.md",
         "PITCH.md",
         "REHEARSAL.md",
         "RISKS.md",
         "SUBMISSION.md"],
    ),
]


def code_snippet_lines() -> list[str]:
    return [
        "def step(self, setpoint, measured):",
        "    error = setpoint - measured",
        "    self.integral += error * self.dt",
        "    # no clamp  ← windup",
        "    d = (error - self.prev) / self.dt",
        "    u = (self.kp*error",
        "         + self.ki*self.integral",
        "         + self.kd*d)",
        "    self.prev = error",
        "    return u",
    ]


def log_snippet_lines() -> list[str]:
    lines = []
    try:
        raw = COSTS.read_text().splitlines()[:6]
        for ln in raw:
            try:
                rec = json.loads(ln)
                lines.append(
                    f"cached={rec.get('cached_input_tokens',0):>5}  "
                    f"uncached={rec.get('uncached_input_tokens',0):>5}  "
                    f"out={rec.get('output_tokens',0):>4}  "
                    f"usd={rec.get('usd_cost',0):.4f}"
                )
            except Exception:
                lines.append(ln[:60])
    except Exception:
        lines = ["(no costs.jsonl)"]
    return lines[:6]


def trace_snippet_lines() -> list[str]:
    return [
        "topic                                     msgs   type",
        "/cam_front/image_raw/compressed          18324   sensor_msgs/CompressedImage",
        "/cam_rear/image_raw/compressed           18312   sensor_msgs/CompressedImage",
        "/velodyne_points                          7233   sensor_msgs/PointCloud2",
        "/imu/data                                91566   sensor_msgs/Imu",
        "/ublox/navrelposned                       1833   ublox_msgs/NavRELPOSNED9",
        "/cmd_vel                                  6105   geometry_msgs/Twist",
        "duration: 305.5s   size: 55.8 GB   topics: 42",
    ]


# -----------------------------------------------------------------------------
# Beat A — title + tree scroll
# -----------------------------------------------------------------------------


def make_title_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 2.5, 0.35)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 66)
    fs = font(FONT_REG, 30)
    fm = font(FONT_MONO, 20)

    # left column: title text
    d.text((120, 160), "Evidence grows.", font=fb, fill=FG)
    d.text((120, 240), "Review doesn't scale.", font=fb, fill=ACCENT)

    d.text((120, 340), "Every session ships logs, video,", font=fs, fill=DIM)
    d.text((120, 380), "controller behavior, sensor traces.", font=fs, fill=DIM)

    d.rectangle([(120, 450), (420, 454)], fill=ACCENT)

    # right column: scrolling repo tree
    tree_x = 1000
    tree_y_base = 140
    line_h = 32
    u = ease(min(1.0, t / 2.2))
    scroll = int((1 - u) * 60)
    fm_tree = font(FONT_MONO, 22)
    fm_tree_b = font(FONT_MONO_BOLD, 22)
    # panel background
    panel_w = 820
    panel_h = 720
    panel = Image.new("RGBA", (panel_w, panel_h), PANEL + (230,))
    pd = ImageDraw.Draw(panel)
    pd.rectangle([(0, 0), (panel_w - 1, panel_h - 1)], outline=BORDER, width=2)
    pd.rectangle([(0, 0), (panel_w, 40)], fill=(28, 30, 36))
    pd.text((16, 10), "$ tree -L 2 BlackBox/", font=fm_tree_b, fill=FG)

    for i, line in enumerate(TREE_LINES):
        ty = 60 + i * line_h + scroll
        if ty < 44 or ty > panel_h - 20:
            continue
        col = FG if not line.startswith("│") and not line.startswith("├") and not line.startswith("└") else DIM
        if "/" in line and not line.startswith("│"):
            col = FG
        # path vs description
        if "     " in line and (line.startswith("│") or line.startswith("└")):
            # split comment from path
            pd.text((16, ty), line, font=fm_tree, fill=DIM)
        else:
            pd.text((16, ty), line, font=fm_tree, fill=FG if i == 0 else DIM)

    paste_alpha(img, panel, (tree_x - 80, tree_y_base), a)

    draw_beat_dots(d, active=0)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat B — folder-listing montage, 5 panels stagger in
# -----------------------------------------------------------------------------


def render_listing_panel(entry: dict, hovered: bool = False) -> Image.Image:
    pw, ph = 540, 280
    panel = Image.new("RGBA", (pw, ph), PANEL + (255,))
    d = ImageDraw.Draw(panel)
    outline = ACCENT if hovered else BORDER
    d.rectangle([(0, 0), (pw - 1, ph - 1)], outline=outline, width=2)
    d.rectangle([(0, 0), (pw, 44)], fill=(28, 30, 36))

    fb = font(FONT_MONO_BOLD, 22)
    fm = font(FONT_MONO, 20)
    fs = font(FONT_REG, 16)

    d.text((16, 10), entry["label"], font=fb, fill=FG)
    bbox = d.textbbox((0, 0), entry["count"], font=fs)
    d.text((pw - (bbox[2] - bbox[0]) - 16, 14), entry["count"], font=fs, fill=ACCENT)

    y = 64
    for ln in entry["lines"]:
        d.text((20, y), ln, font=fm, fill=DIM if ln == "..." else FG)
        y += 30
    return panel


def make_sweep_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 3.5, 0.35)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d_top = ImageDraw.Draw(layer)

    # header
    fb = font(FONT_BOLD, 48)
    fs = font(FONT_REG, 26)
    d_top.text((120, 70), "One session, many artifact types.", font=fb, fill=FG)
    d_top.text((120, 130), "heterogeneous · voluminous · unreviewable by hand", font=fs, fill=DIM)

    # 5 panels in an arc, stagger in
    positions = [
        (80, 200),
        (700, 200),
        (1320, 200),
        (380, 540),
        (1000, 540),
    ]
    for i, entry in enumerate(LISTINGS):
        delay = 0.25 + i * 0.28
        local = max(0.0, t - delay)
        in_u = ease(min(1.0, local / 0.55))
        if in_u <= 0:
            continue
        panel = render_listing_panel(entry)
        pw, ph = panel.size
        px, py = positions[i]
        # slide-up offset
        py_off = int((1 - in_u) * 40)
        sh = shadow_for(pw, ph)
        img.alpha_composite(sh, (px - 20, py - 20 + py_off))
        paste_alpha(img, panel, (px, py + py_off), in_u)

    draw_beat_dots(d_top, active=1)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat C — 5 evidence-type tiles with amber sweep
# -----------------------------------------------------------------------------


def make_plot_tile() -> Image.Image:
    w, h = 560, 360
    tile = Image.new("RGBA", (w, h), (250, 250, 250, 255))
    try:
        src = Image.open(PLOT).convert("RGBA")
        sw, sh = src.size
        rs = min(w / sw, h / sh)
        nw, nh = int(sw * rs), int(sh * rs)
        r = src.resize((nw, nh), Image.LANCZOS)
        tile.alpha_composite(r, ((w - nw) // 2, (h - nh) // 2))
    except Exception:
        pass
    return tile


def make_frame_tile() -> Image.Image:
    w, h = 560, 360
    tile = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    try:
        src = Image.open(FRAME).convert("RGBA")
        sw, sh = src.size
        rs = max(w / sw, h / sh)
        nw, nh = int(sw * rs), int(sh * rs)
        r = src.resize((nw, nh), Image.LANCZOS)
        ox, oy = (nw - w) // 2, (nh - h) // 2
        tile.alpha_composite(r.crop((ox, oy, ox + w, oy + h)))
    except Exception:
        pass
    return tile


def make_code_tile() -> Image.Image:
    w, h = 560, 360
    tile = Image.new("RGBA", (w, h), PANEL + (255,))
    d = ImageDraw.Draw(tile)
    d.rectangle([(0, 0), (w, 40)], fill=(28, 30, 36))
    fm_h = font(FONT_MONO_BOLD, 18)
    fm = font(FONT_MONO, 19)
    d.text((14, 10), "pid_controller.py", font=fm_h, fill=FG)
    y = 58
    for ln in code_snippet_lines():
        col = (220, 120, 120) if "windup" in ln else FG
        d.text((18, y), ln, font=fm, fill=col)
        y += 28
    return tile


def make_log_tile() -> Image.Image:
    w, h = 560, 360
    tile = Image.new("RGBA", (w, h), PANEL + (255,))
    d = ImageDraw.Draw(tile)
    d.rectangle([(0, 0), (w, 40)], fill=(28, 30, 36))
    fm_h = font(FONT_MONO_BOLD, 18)
    fm = font(FONT_MONO, 17)
    d.text((14, 10), "data/costs.jsonl", font=fm_h, fill=FG)
    y = 58
    for ln in log_snippet_lines():
        d.text((14, y), ln, font=fm, fill=FG)
        y += 28
    d.text((14, y + 8), "… 90 entries · token + USD per call", font=fm, fill=DIM)
    return tile


def make_trace_tile() -> Image.Image:
    w, h = 560, 360
    tile = Image.new("RGBA", (w, h), PANEL + (255,))
    d = ImageDraw.Draw(tile)
    d.rectangle([(0, 0), (w, 40)], fill=(28, 30, 36))
    fm_h = font(FONT_MONO_BOLD, 18)
    fm = font(FONT_MONO, 15)
    d.text((14, 10), "rosbag info 1_cam-lidar.bag", font=fm_h, fill=FG)
    y = 58
    for ln in trace_snippet_lines():
        d.text((14, y), ln, font=fm, fill=FG if "topic" != ln.split()[0] else ACCENT)
        y += 28
    return tile


TILE_FACTORIES = [
    ("Video",              make_frame_tile),
    ("Controller behavior", make_code_tile),
    ("Sensor traces",      make_trace_tile),
    ("Plots",              make_plot_tile),
    ("Logs",               make_log_tile),
]


def make_tiles_beat(t: float, cached_tiles: list[Image.Image]) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 4.0, 0.35)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d_top = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 46)
    fs = font(FONT_REG, 24)
    d_top.text((120, 50), "Logs · Video · Controller behavior · Sensor traces", font=fb, fill=FG)
    d_top.text((120, 108), "the evidence is there. the forensic work is still manual.", font=fs, fill=DIM)

    # tile grid: 5 tiles, 3 top row, 2 bottom row (centered)
    tile_w, tile_h = 560, 360
    gap = 40
    top_y = 200
    bot_y = top_y + tile_h + gap
    total_w_top = tile_w * 3 + gap * 2
    total_w_bot = tile_w * 2 + gap
    top_x0 = (W - total_w_top) // 2
    bot_x0 = (W - total_w_bot) // 2

    coords = [
        (top_x0, top_y),
        (top_x0 + tile_w + gap, top_y),
        (top_x0 + 2 * (tile_w + gap), top_y),
        (bot_x0, bot_y),
        (bot_x0 + tile_w + gap, bot_y),
    ]
    labels = [lbl for lbl, _ in TILE_FACTORIES]

    # reveal stagger per tile
    fm_lbl = font(FONT_MONO_BOLD, 22)

    # amber traversal: one active tile at a time during 1.2-3.8s
    traverse_start = 1.0
    traverse_end = 3.6
    active_idx = -1
    if traverse_start <= t <= traverse_end:
        frac = (t - traverse_start) / (traverse_end - traverse_start)
        active_idx = min(len(coords) - 1, int(frac * len(coords)))

    for i, ((x, y), tile, lbl) in enumerate(zip(coords, cached_tiles, labels)):
        delay = 0.15 + i * 0.18
        local = max(0.0, t - delay)
        u = ease(min(1.0, local / 0.5))
        if u <= 0:
            continue
        y_off = int((1 - u) * 30)
        pw, ph = tile.size
        sh = shadow_for(pw, ph)
        img.alpha_composite(sh, (x - 20, y - 20 + y_off))
        paste_alpha(img, tile, (x, y + y_off), u)
        # border
        outline = ACCENT if i == active_idx else BORDER
        width = 4 if i == active_idx else 2
        bd = ImageDraw.Draw(img)
        bd.rectangle([(x, y + y_off), (x + pw - 1, y + y_off + ph - 1)], outline=outline, width=width)
        # label above tile
        d_top.text((x, y + y_off - 34), lbl, font=fm_lbl, fill=ACCENT if i == active_idx else FG)

    draw_beat_dots(d_top, active=1)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat D — final lockup
# -----------------------------------------------------------------------------


def make_lockup_beat(t: float, dim_tiles_img: Image.Image) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)

    # dim the tile composite behind
    dim = dim_tiles_img.copy()
    r, g, b, al = dim.split()
    al = al.point(lambda v: int(v * 0.22))
    dim = Image.merge("RGBA", (r, g, b, al))
    img.alpha_composite(dim)

    # vignette
    vg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vg)
    for i in range(6):
        vd.rectangle([(i * 30, i * 20), (W - i * 30, H - i * 20)], outline=(0, 0, 0, 18), width=1)
    img.alpha_composite(vg)

    a = fade_alpha(t, 3.5, 0.4)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 96)
    fs = font(FONT_REG, 36)
    fm = font(FONT_MONO, 24)

    draw_text_centered(d, (W // 2, H // 2 - 80), "Too much evidence.", fb, FG)

    # amber bar
    d.rectangle([(W // 2 - 160, H // 2 + 0), (W // 2 + 160, H // 2 + 4)], fill=ACCENT)

    draw_text_centered(d, (W // 2, H // 2 + 70), "Manual forensic work.", fb, ACCENT)

    draw_text_centered(d, (W // 2, H // 2 + 160), "one session · 55.8 GB · 42 topics · 7 bug classes", fs, DIM)
    draw_text_centered(d, (W // 2, H - 120), "BLACK  BOX  —  forensic copilot", fm, (90, 96, 108))

    draw_beat_dots(d, active=1)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Render loop
# -----------------------------------------------------------------------------


def crossfade(a: Image.Image, b: Image.Image, u: float) -> Image.Image:
    return Image.blend(a, b, u)


def _seg(i: int, local_t: float, tiles, lockup_bg) -> Image.Image:
    if i == 0:
        return make_title_beat(local_t)
    if i == 1:
        return make_sweep_beat(local_t)
    if i == 2:
        return make_tiles_beat(local_t, tiles)
    return make_lockup_beat(local_t, lockup_bg)


def render_at(t: float, tiles, lockup_bg) -> Image.Image:
    for i, (s, e) in enumerate(SEG_BOUNDS):
        if s <= t < e:
            base = _seg(i, t - s, tiles, lockup_bg)
            if i + 1 < len(SEG_BOUNDS) and (e - t) < XFADE:
                u = 1.0 - (e - t) / XFADE
                nxt = _seg(i + 1, t - SEG_BOUNDS[i + 1][0], tiles, lockup_bg)
                return crossfade(base, nxt, ease(u))
            return base
    return _seg(len(SEG_BOUNDS) - 1, t - SEG_BOUNDS[-1][0], tiles, lockup_bg)


def main() -> None:
    tiles = [fac() for _, fac in TILE_FACTORIES]
    # build a representative tiles frame (t near end of beat C) to use as dim bg in D
    lockup_bg = make_tiles_beat(3.8, tiles).convert("RGBA")

    tmp = Path(tempfile.mkdtemp(prefix="block02_"))
    print(f"tmp: {tmp}", file=sys.stderr)

    for k in range(N):
        t = k / FPS
        fr = render_at(t, tiles, lockup_bg).convert("RGB")
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

    preview = render_at(8.8, tiles, lockup_bg).convert("RGB")
    preview.save(OUT / "preview.png", "PNG", optimize=True)

    shutil.rmtree(tmp)
    print(f"wrote {out_mp4}")


if __name__ == "__main__":
    main()
