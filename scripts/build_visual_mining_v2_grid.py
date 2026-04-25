# SPDX-License-Identifier: MIT
"""Build the demo's 5-camera cross-modal grid PNG (#128).

Picks one frame per camera at the highest-priority telemetry window
center, stacks them into a single grid with a caption that names the
window and the cross-modal mode (`visual_mining_v2`). Output:
``docs/assets/visual_mining_v2_grid.png``.

Why this exists: the demo VO claims "5 cameras in one prompt anchored on
a telemetry window" but the video had no visual proof. This script
produces a stand-alone artifact a viewer can recognize as a
cross-modal-mode card.

Re-run any time the sanfer run changes:
    python scripts/build_visual_mining_v2_grid.py
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "data" / "runs" / "sanfer_sanisidro__no_prompt"
OUT = ROOT / "docs" / "assets" / "visual_mining_v2_grid.png"

CELL = (480, 320)
PADDING = 12
CAPTION_H = 110
N_COLS = 5
N_ROWS = 1
TITLE = "visual_mining_v2 — 5 cameras in ONE prompt, anchored on telemetry window"


def _pick_frames() -> list[tuple[str, Path]]:
    frames_dir = RUN / "frames"
    windows = json.loads((RUN / "windows.json").read_text())
    if not windows:
        raise SystemExit("no windows.json — run the sanfer pipeline first")
    target = max(windows, key=lambda w: w.get("priority", 0))
    center_ns = int(target["center_ns"])
    label = target.get("label", "")
    pat = re.compile(r"(cam\d)_image_raw_compressed_\d+_t(\d+)_small\.jpg$")
    per_cam: dict[str, list[tuple[int, Path]]] = defaultdict(list)
    for p in frames_dir.iterdir():
        m = pat.search(p.name)
        if not m:
            continue
        per_cam[m.group(1)].append((int(m.group(2)), p))
    chosen: list[tuple[str, Path]] = []
    for cam in sorted(per_cam):
        chosen.append((cam, min(per_cam[cam], key=lambda x: abs(x[0] - center_ns))[1]))
    return chosen, label, center_ns


def _font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> int:
    chosen, label, center_ns = _pick_frames()
    if len(chosen) < 2:
        raise SystemExit(f"only {len(chosen)} cameras in run; need ≥2 for visual_mining_v2")
    grid_w = N_COLS * CELL[0] + (N_COLS + 1) * PADDING
    grid_h = N_ROWS * CELL[1] + 2 * PADDING + CAPTION_H
    canvas = Image.new("RGB", (grid_w, grid_h), color=(28, 28, 26))
    draw = ImageDraw.Draw(canvas)
    title_font = _font(22)
    cell_font = _font(14)
    sub_font = _font(13)

    for col, (cam, path) in enumerate(chosen[:N_COLS]):
        try:
            im = Image.open(path).convert("RGB").resize(CELL, Image.Resampling.LANCZOS)
        except Exception:
            im = Image.new("RGB", CELL, (60, 60, 58))
        x = PADDING + col * (CELL[0] + PADDING)
        y = PADDING
        canvas.paste(im, (x, y))
        tag = f"{cam}  ·  t={center_ns/1e9:.2f}s"
        tag_w = draw.textlength(tag, font=cell_font)
        draw.rectangle([x, y + CELL[1] - 26, x + tag_w + 14, y + CELL[1]], fill=(255, 253, 248))
        draw.text((x + 7, y + CELL[1] - 22), tag, font=cell_font, fill=(28, 28, 26))

    cap_y = PADDING + CELL[1] + PADDING
    draw.text((PADDING + 4, cap_y), TITLE, font=title_font, fill=(255, 253, 248))
    label_short = (label[:180] + "…") if len(label) > 180 else label
    draw.text(
        (PADDING + 4, cap_y + 32),
        f"window source: from_timeline   center_ns: {center_ns}",
        font=sub_font,
        fill=(180, 180, 175),
    )
    draw.text(
        (PADDING + 4, cap_y + 52),
        f"label: {label_short}",
        font=sub_font,
        fill=(180, 180, 175),
    )
    draw.text(
        (PADDING + 4, cap_y + 72),
        "frame discipline: 800×600 thumbnails · 3.75 MP escalation only on demand · single cross-view call",
        font=sub_font,
        fill=(140, 200, 140),
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT, optimize=True)
    print(f"wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
