# SPDX-License-Identifier: MIT
"""Render block_05_first_moment: 17.5s, 1920x1080, 30fps.

Narration: "Here. USV session, 416 seconds. The LIDAR companion IMU was
declared but never published a single message — while the point cloud
stream on the same sensor ran nominal at 10 Hz. A silent driver failure,
not a QoS mismatch."

Visual identity preserved from block_01 / block_02 / block_07 / block_08:
  - BG (10,12,16), FG (230,232,236), DIM (120,128,140)
  - DejaVu Sans / Sans Mono typography
  - 80px grid backdrop, drop shadows, 4-dot beat indicator

First-finding treatment:
  - ACCENT amber returns (discovery energy) but used only on healthy
    stream + final diagnosis, NOT everywhere
  - dead stream rendered with MUTED_RED (same palette as block_07's
    REJECTED tag) — borrowed to signal "this is wrong"
  - paired two-column composition holds across beats B/C so viewer
    locks onto the asymmetry
  - QoS interpretation rejected with strike-through borrowed verbatim
    from block_07's rejection language
  - final lockup is less climactic than block_08 (no amber flood, no
    BUG/FIX lockup): this is evidence discovery, not payoff

Beats:
  A 0.0-3.0    case identity: USV session, 416.76s, source
  B 3.0-8.0    paired streams: /lidar_imu vs /lidar_points, same sensor
  C 8.0-12.0   reject QoS interpretation (strike-through)
  D 12.0-17.5  lockup: "silent driver failure"

Source: data/runs/boat_lidar_rerun/report.md (real re-run, sensor_timeout
0.95, driver-level patch hint that explicitly says "not a QoS mismatch").
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "video_assets" / "block_05_first_moment"
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
HEALTH_BG = (22, 32, 24)
HEALTH_FG = (186, 220, 170)
STRIKE = (90, 94, 100)

SEG_BOUNDS = [(0.0, 3.0), (3.0, 8.0), (8.0, 12.0), (12.0, 17.5)]
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
    d.text((cx - 150, y + 18), "  block 05 · first finding", font=fm, fill=(90, 96, 108))


def shadow_for(w: int, h: int, pad: int = 20, alpha: int = 140, blur: int = 18) -> Image.Image:
    sh = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([(pad, pad), (w + pad, h + pad)], fill=(0, 0, 0, alpha))
    return sh.filter(ImageFilter.GaussianBlur(blur))


# -----------------------------------------------------------------------------
# Beat A — case identity
# -----------------------------------------------------------------------------


def make_identity_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 3.0, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 72)
    fmed = font(FONT_BOLD, 40)
    fs = font(FONT_REG, 26)
    fm = font(FONT_MONO, 22)

    # top eyebrow
    d.text((260, 200), "FIRST FINDING", font=fm, fill=ACCENT)
    d.rectangle([(260, 240), (420, 242)], fill=ACCENT)

    # title
    d.text((260, 270), "USV session", font=fb, fill=FG)

    # duration, large
    d.text((260, 380), "416.76 s", font=fb, fill=ACCENT)
    d.text((260, 470), "rosbag2 · ROS 2 · LIDAR-only platform", font=fs, fill=DIM)

    # source crumb
    src_y = 580
    d.text((260, src_y), "source", font=fm, fill=DIM)
    d.text((260, src_y + 32), "/mnt/ssd_boat/rosbag2_2025_09_17-14_01_14", font=fm, fill=FG)
    d.text((260, src_y + 72), "report  data/runs/boat_lidar_rerun/report.md", font=fm, fill=DIM)

    # right-side session metadata card
    card_x, card_y, card_w, card_h = 1160, 260, 540, 380
    card = Image.new("RGBA", (card_w, card_h), PANEL + (255,))
    cd = ImageDraw.Draw(card)
    cd.rectangle([(0, 0), (card_w - 1, card_h - 1)], outline=BORDER, width=2)
    cd.rectangle([(0, 0), (card_w, 48)], fill=(28, 30, 36))
    cd.text((20, 12), "session metadata", font=font(FONT_MONO_BOLD, 22), fill=FG)

    rows = [
        ("duration",    "416.76 s"),
        ("case",        "rosbag2_2025_09_17-14_01_14"),
        ("mode",        "run_session_v1 · telemetry_only"),
        ("cameras",     "none (LIDAR-only)"),
        ("top finding", "sensor_timeout · 0.95"),
    ]
    y = 80
    fm_b = font(FONT_MONO_BOLD, 20)
    fm_r = font(FONT_MONO, 20)
    for k, v in rows:
        cd.text((24, y), k, font=fm_r, fill=DIM)
        cd.text((220, y), v, font=fm_b, fill=FG)
        y += 52

    sh = shadow_for(card_w, card_h)
    img.alpha_composite(sh, (card_x - 20, card_y - 20))
    paste_alpha(img, card, (card_x, card_y), 1.0)

    draw_beat_dots(d, active=0)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat B — paired streams, same sensor
# -----------------------------------------------------------------------------


def render_stream_card(
    topic: str,
    msgtype: str,
    state_label: str,
    primary_number: str,
    primary_caption: str,
    secondary_number: str,
    secondary_caption: str,
    dead: bool,
    highlight: float = 1.0,
    width: int = 760,
    height: int = 580,
) -> Image.Image:
    card = Image.new("RGBA", (width, height), PANEL + (255,))
    d = ImageDraw.Draw(card)
    outline = MUTED_RED if dead else ACCENT
    # fade outline strength by highlight
    if highlight < 1.0:
        mix = highlight
        outline = tuple(int(BORDER[i] + (outline[i] - BORDER[i]) * mix) for i in range(3))
    d.rectangle([(0, 0), (width - 1, height - 1)], outline=outline, width=3)
    # header band
    band = DEAD_BG if dead else HEALTH_BG
    d.rectangle([(0, 0), (width, 62)], fill=band)

    fm_b = font(FONT_MONO_BOLD, 26)
    fm_r = font(FONT_MONO, 20)
    fs = font(FONT_REG, 22)
    fb_huge = font(FONT_BOLD, 120)
    fb_med = font(FONT_BOLD, 40)

    d.text((24, 18), topic, font=fm_b, fill=FG)
    state_color = MUTED_RED if dead else HEALTH_FG
    # right-aligned state tag
    tag_bbox = d.textbbox((0, 0), state_label, font=fm_b)
    tag_w = tag_bbox[2] - tag_bbox[0]
    d.text((width - tag_w - 24, 18), state_label, font=fm_b, fill=state_color)

    # msgtype subtitle
    d.text((24, 80), msgtype, font=fm_r, fill=DIM)

    # primary number, very large
    num_color = MUTED_RED if dead else ACCENT
    draw_text_centered(d, (width // 2, 240), primary_number, fb_huge, num_color)
    draw_text_centered(d, (width // 2, 330), primary_caption, fs, DIM)

    # divider hairline
    d.rectangle([(80, 380), (width - 80, 382)], fill=BORDER)

    # secondary metric
    draw_text_centered(d, (width // 2, 450), secondary_number, fb_med, FG if not dead else STRIKE)
    draw_text_centered(d, (width // 2, 510), secondary_caption, fs, DIM)

    return card


def make_paired_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 5.0, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 42)
    fs = font(FONT_REG, 24)
    fm = font(FONT_MONO, 20)

    d.text((260, 70), "Two streams · same sensor pod", font=fb, fill=FG)
    d.text((260, 126), "LIDAR unit publishes both a point cloud and a companion IMU", font=fs, fill=DIM)
    d.rectangle([(260, 168), (420, 170)], fill=ACCENT)

    # Staggered reveal: left card first, right card at t>=0.8
    left_a = min(1.0, max(0.0, (t - 0.1) / 0.6))
    right_a = min(1.0, max(0.0, (t - 0.8) / 0.6))

    # Left: /lidar_imu (dead)
    left = render_stream_card(
        topic="/lidar_imu",
        msgtype="sensor_msgs/msg/Imu",
        state_label="SILENT",
        primary_number="0",
        primary_caption="messages published across entire session",
        secondary_number="0.00 Hz",
        secondary_caption="rate (topic declared, never emits)",
        dead=True,
        highlight=left_a,
    )

    # Right: /lidar_points (healthy)
    right = render_stream_card(
        topic="/lidar_points",
        msgtype="sensor_msgs/msg/PointCloud2",
        state_label="NOMINAL",
        primary_number="4318",
        primary_caption="messages across 416.76 s",
        secondary_number="10.00 Hz",
        secondary_caption="rate (median dt 100.0 ms)",
        dead=False,
        highlight=right_a,
    )

    card_w, card_h = 760, 580
    gap = 80
    total = card_w * 2 + gap
    lx = (W - total) // 2
    rx = lx + card_w + gap
    cy = 220

    sh = shadow_for(card_w, card_h)
    img.alpha_composite(sh, (lx - 20, cy - 20))
    paste_alpha(img, left, (lx, cy), left_a)
    img.alpha_composite(sh, (rx - 20, cy - 20))
    paste_alpha(img, right, (rx, cy), right_a)

    # connector: "same sensor pod"
    connector_a = min(1.0, max(0.0, (t - 1.6) / 0.6))
    if connector_a > 0:
        conn_y = cy + card_h + 30
        d.line([(lx + card_w // 2, conn_y), (lx + card_w // 2, conn_y + 20)], fill=DIM, width=2)
        d.line([(rx + card_w // 2, conn_y), (rx + card_w // 2, conn_y + 20)], fill=DIM, width=2)
        d.line([(lx + card_w // 2, conn_y + 20), (rx + card_w // 2, conn_y + 20)], fill=DIM, width=2)
        fm_b = font(FONT_MONO_BOLD, 22)
        draw_text_centered(d, (W // 2, conn_y + 52), "same LIDAR sensor pod · same QoS profile advertised", fm_b, DIM)

    draw_beat_dots(d, active=1)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat C — reject QoS interpretation
# -----------------------------------------------------------------------------


def make_reject_qos_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 4.0, 0.5)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 44)
    fs = font(FONT_REG, 26)
    fm = font(FONT_MONO, 22)
    fm_b = font(FONT_MONO_BOLD, 28)

    d.text((260, 80), "Wrong interpretation", font=fb, fill=FG)
    d.text((260, 138), "the obvious guess — and why it doesn't hold", font=fs, fill=DIM)
    d.rectangle([(260, 180), (420, 182)], fill=MUTED_AMBER)

    # wrong-interpretation card (gets struck)
    card_w, card_h = 1200, 180
    cx = (W - card_w) // 2
    cy = 260
    card = Image.new("RGBA", (card_w, card_h), PANEL + (255,))
    cd = ImageDraw.Draw(card)
    cd.rectangle([(0, 0), (card_w - 1, card_h - 1)], outline=BORDER, width=2)
    cd.text((32, 28), "QoS mismatch", font=fm_b, fill=FG)
    cd.text((32, 78), "subscriber and publisher speak incompatible reliability/durability;", font=fs, fill=DIM)
    cd.text((32, 112), "subscriber drops every frame — topic looks silent.", font=fs, fill=DIM)

    sh = shadow_for(card_w, card_h)
    img.alpha_composite(sh, (cx - 20, cy - 20))
    paste_alpha(img, card, (cx, cy), 1.0)

    # strike-through + REJECTED tag at t >= 0.6
    strike_a = min(1.0, max(0.0, (t - 0.6) / 0.5))
    if strike_a > 0:
        so = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(so)
        sd.line([(cx + 24, cy + 56), (cx + card_w - 24, cy + 56)], fill=MUTED_RED, width=3)
        sd.line([(cx + 24, cy + 130), (cx + card_w - 24, cy + 130)], fill=MUTED_RED, width=3)
        tag_w = 240
        tag_x = cx + card_w - tag_w - 24
        sd.rectangle([(tag_x, cy + 24), (tag_x + tag_w, cy + 74)], outline=MUTED_RED, width=2)
        sd.text((tag_x + 18, cy + 34), "REJECTED", font=fm_b, fill=MUTED_RED)
        paste_alpha(img, so, (0, 0), strike_a)

    # why-not panel below
    why_a = min(1.0, max(0.0, (t - 1.4) / 0.6))
    why_y = cy + card_h + 80
    why_w, why_h = 1200, 340
    wx = (W - why_w) // 2
    why = Image.new("RGBA", (why_w, why_h), PANEL + (255,))
    wd = ImageDraw.Draw(why)
    wd.rectangle([(0, 0), (why_w - 1, why_h - 1)], outline=ACCENT, width=2)
    wd.rectangle([(0, 0), (why_w, 52)], fill=(28, 30, 36))
    wd.text((20, 14), "why not QoS", font=fm_b, fill=ACCENT)

    bullets = [
        ("metadata", "/lidar_imu and /lidar_points advertise identical QoS profile"),
        ("recorder", "rosbag2 subscribed — a QoS mismatch would log warnings; none found"),
        ("publisher", "zero messages emitted — not dropped, never sent"),
    ]
    yy = 92
    for label, text in bullets:
        wd.text((32, yy), label, font=fm_b, fill=MUTED_AMBER)
        wd.text((200, yy), text, font=fs, fill=FG)
        yy += 60

    sh2 = shadow_for(why_w, why_h)
    if why_a > 0:
        img.alpha_composite(sh2, (wx - 20, why_y - 20))
        paste_alpha(img, why, (wx, why_y), why_a)

    draw_beat_dots(d, active=2)
    paste_alpha(img, layer, (0, 0), a)
    return img


# -----------------------------------------------------------------------------
# Beat D — lockup: silent driver failure
# -----------------------------------------------------------------------------


def make_lockup_beat(t: float) -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    a = fade_alpha(t, 5.5, 0.6)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    fb = font(FONT_BOLD, 110)
    fb_med = font(FONT_BOLD, 36)
    fs = font(FONT_REG, 30)
    fm = font(FONT_MONO, 22)
    fm_b = font(FONT_MONO_BOLD, 24)

    # small eyebrow
    draw_text_centered(d, (W // 2, 240), "DIAGNOSIS", fm_b, DIM)

    # two-line hero
    draw_text_centered(d, (W // 2, H // 2 - 40), "silent driver failure.", fb, ACCENT)

    # hairline
    d.rectangle([(W // 2 - 140, H // 2 + 70), (W // 2 + 140, H // 2 + 72)], fill=(60, 64, 72))

    # class + confidence pill row
    pill_y = H // 2 + 130
    pill_h = 56
    items = [
        ("bug_class", "sensor_timeout"),
        ("confidence", "0.95"),
        ("scope", "session-global · 416.76 s"),
    ]
    # measure total width
    padding = 18
    gap = 28
    widths = []
    for label, value in items:
        lb_w = d.textbbox((0, 0), label, font=fm)[2]
        v_w = d.textbbox((0, 0), value, font=fm_b)[2]
        widths.append(lb_w + 10 + v_w + padding * 2)
    total = sum(widths) + gap * (len(items) - 1)
    x = (W - total) // 2
    for (label, value), w in zip(items, widths):
        d.rectangle([(x, pill_y), (x + w, pill_y + pill_h)], fill=(28, 30, 36), outline=BORDER, width=1)
        d.text((x + padding, pill_y + 16), label, font=fm, fill=DIM)
        lb_w = d.textbbox((0, 0), label, font=fm)[2]
        d.text((x + padding + lb_w + 10, pill_y + 14), value, font=fm_b, fill=ACCENT if label == "bug_class" else FG)
        x += w + gap

    # footer caveat line (what to check)
    draw_text_centered(
        d,
        (W // 2, H - 180),
        "check driver launch params  ·  imu_publish, imu_port  ·  sensor hardware connectivity",
        fs, DIM,
    )

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
        return make_identity_beat(local_t)
    if i == 1:
        return make_paired_beat(local_t)
    if i == 2:
        return make_reject_qos_beat(local_t)
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
    tmp = Path(tempfile.mkdtemp(prefix="block05_"))
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

    # preview: hero frame from beat B (paired streams full)
    preview = render_at(6.5).convert("RGB")
    preview.save(OUT / "preview.png", "PNG", optimize=True)

    shutil.rmtree(tmp)
    print(f"wrote {out_mp4}")


if __name__ == "__main__":
    main()
