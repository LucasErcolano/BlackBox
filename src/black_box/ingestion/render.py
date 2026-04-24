# SPDX-License-Identifier: MIT
"""Render helpers: synced camera grid, telemetry plot, thumbnail, b64."""

from __future__ import annotations

import base64
import io
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import matplotlib

matplotlib.use("Agg")  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from .rosbag_reader import BagData, TimeSeries


# -------- helpers ------------------------------------------------------------


def _bgr_to_pil(arr: np.ndarray) -> Image.Image:
    if arr.ndim == 2:
        return Image.fromarray(arr, mode="L").convert("RGB")
    if arr.shape[2] == 3:
        return Image.fromarray(arr[:, :, ::-1])  # BGR -> RGB
    if arr.shape[2] == 4:
        return Image.fromarray(arr[:, :, [2, 1, 0]])
    return Image.fromarray(arr)


def thumb(img: Image.Image, max_side: int = 800) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_side:
        return img.copy()
    scale = max_side / float(max(w, h))
    return img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)


def to_b64(img: Image.Image, fmt: str = "JPEG", quality: int = 85) -> str:
    buf = io.BytesIO()
    rgb = img.convert("RGB") if fmt.upper() == "JPEG" else img
    rgb.save(buf, format=fmt, quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _font(size: int = 16) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size
        )
    except Exception:
        return ImageFont.load_default()


# -------- frame lookup -------------------------------------------------------


def frames_at(bag: BagData, t_ns_list: list[int], topic: str) -> list[Image.Image]:
    frames = bag.cameras.get(topic, [])
    if not frames:
        return []
    ts = np.asarray([f.t_ns for f in frames], dtype=np.int64)
    out: list[Image.Image] = []
    for t in t_ns_list:
        i = int(np.searchsorted(ts, t))
        if i <= 0:
            j = 0
        elif i >= len(ts):
            j = len(ts) - 1
        else:
            j = i - 1 if abs(ts[i - 1] - t) <= abs(ts[i] - t) else i
        out.append(_bgr_to_pil(frames[j].image))
    return out


# -------- synced grid --------------------------------------------------------


def synced_grid(synced_entry: dict, thumb_size: tuple[int, int] = (800, 600)) -> Image.Image:
    """Compose up to 5 camera frames into one image (2x3 grid, labeled)."""
    frames = synced_entry.get("frames", {})
    items = list(frames.items())[:5]
    if not items:
        # empty canvas
        return Image.new("RGB", thumb_size, color=(32, 32, 32))

    cols, rows = 3, 2
    cell_w, cell_h = thumb_size
    canvas = Image.new("RGB", (cell_w * cols, cell_h * rows), color=(16, 16, 16))
    font = _font(20)

    for idx, (topic, arr) in enumerate(items):
        r, c = divmod(idx, cols)
        pil = _bgr_to_pil(arr)
        pil = thumb(pil, max_side=max(cell_w, cell_h))
        # center inside cell
        tile = Image.new("RGB", (cell_w, cell_h), color=(16, 16, 16))
        px = (cell_w - pil.size[0]) // 2
        py = (cell_h - pil.size[1]) // 2
        tile.paste(pil, (px, py))
        # label
        draw = ImageDraw.Draw(tile)
        label = topic
        # background strip
        draw.rectangle([(0, 0), (cell_w, 28)], fill=(0, 0, 0))
        draw.text((6, 4), label, fill=(255, 255, 255), font=font)
        canvas.paste(tile, (c * cell_w, r * cell_h))

    # optional: timestamp banner
    t_ns = synced_entry.get("t_ns")
    if t_ns is not None:
        draw = ImageDraw.Draw(canvas)
        stamp = f"t = {t_ns / 1e9:.3f} s"
        draw.rectangle([(0, canvas.size[1] - 28), (260, canvas.size[1])], fill=(0, 0, 0))
        draw.text((6, canvas.size[1] - 24), stamp, fill=(255, 255, 255), font=font)
    return canvas


# -------- telemetry plot -----------------------------------------------------


def plot_telemetry(
    telemetry: dict[str, TimeSeries],
    marks_ns: list[int] | None = None,
    size: tuple[int, int] = (1200, 800),
) -> Image.Image:
    topics = list(telemetry.items())[:6]
    if not topics:
        img = Image.new("RGB", size, color=(240, 240, 240))
        draw = ImageDraw.Draw(img)
        draw.text((20, 20), "No telemetry", fill=(0, 0, 0), font=_font(24))
        return img

    dpi = 100
    fig, axes = plt.subplots(
        nrows=len(topics),
        ncols=1,
        figsize=(size[0] / dpi, size[1] / dpi),
        dpi=dpi,
        sharex=True,
    )
    if len(topics) == 1:
        axes = [axes]

    # Choose t0 for readable x axis
    t0 = min(ts.t_ns[0] for _, ts in topics if ts.t_ns.size)
    for ax, (topic, ts) in zip(axes, topics):
        if ts.t_ns.size == 0:
            ax.set_title(f"{topic} (empty)")
            continue
        xs = (ts.t_ns - t0) / 1e9
        vals = ts.values
        if vals.ndim == 1:
            ax.plot(xs, vals, linewidth=1.0, label=ts.fields[0] if ts.fields else "v")
        else:
            for j in range(min(vals.shape[1], 6)):
                label = ts.fields[j] if j < len(ts.fields) else f"d{j}"
                ax.plot(xs, vals[:, j], linewidth=1.0, label=label)
        ax.set_title(topic, fontsize=9, loc="left")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right", fontsize=7)
        if marks_ns:
            for m in marks_ns:
                ax.axvline((m - t0) / 1e9, color="red", linestyle="--", linewidth=0.8, alpha=0.8)
    axes[-1].set_xlabel("t (s, from bag start)")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")
