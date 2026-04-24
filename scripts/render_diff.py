# SPDX-License-Identifier: MIT
"""Render a unified diff as a PNG screenshot (GitHub-style colors).

Usage:
    python scripts/render_diff.py <before.py> <after.py> <out.png> [--title TITLE] [--label-before STR] [--label-after STR]
"""
from __future__ import annotations

import argparse
import difflib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BG = (13, 17, 23)
FG = (201, 209, 217)
HEADER_BG = (22, 27, 34)
HEADER_FG = (139, 148, 158)
ADD_BG = (28, 49, 41)
ADD_FG = (126, 231, 135)
DEL_BG = (73, 27, 27)
DEL_FG = (255, 129, 130)
HUNK_BG = (22, 27, 34)
HUNK_FG = (121, 192, 255)
TITLE_FG = (240, 246, 252)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
]


def _load_font(size: int, bold: bool = False):
    names = FONT_CANDIDATES if not bold else FONT_CANDIDATES[:1] + FONT_CANDIDATES[1:]
    for n in names:
        if Path(n).exists():
            try:
                return ImageFont.truetype(n, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def render(before: Path, after: Path, out: Path, title: str | None = None,
           label_before: str = "before", label_after: str = "after") -> None:
    a = before.read_text().splitlines(keepends=False)
    b = after.read_text().splitlines(keepends=False)
    diff = list(difflib.unified_diff(a, b,
                                     fromfile=f"a/{before.name} ({label_before})",
                                     tofile=f"b/{after.name} ({label_after})",
                                     n=3, lineterm=""))

    font_size = 16
    font = _load_font(font_size)
    title_font = _load_font(20, bold=True)
    line_h = font_size + 8
    pad_x = 28
    pad_y = 20
    max_w = 0
    dummy = Image.new("RGB", (10, 10))
    ddraw = ImageDraw.Draw(dummy)
    for ln in diff:
        w = ddraw.textlength(ln, font=font)
        if w > max_w:
            max_w = int(w)
    title_h = 40 if title else 0
    img_w = max_w + 2 * pad_x
    img_h = title_h + len(diff) * line_h + 2 * pad_y

    img = Image.new("RGB", (img_w, img_h), BG)
    draw = ImageDraw.Draw(img)

    y = pad_y
    if title:
        draw.text((pad_x, y), title, fill=TITLE_FG, font=title_font)
        y += title_h

    for ln in diff:
        if ln.startswith("+++") or ln.startswith("---"):
            draw.rectangle([0, y, img_w, y + line_h], fill=HEADER_BG)
            draw.text((pad_x, y + 4), ln, fill=HEADER_FG, font=font)
        elif ln.startswith("@@"):
            draw.rectangle([0, y, img_w, y + line_h], fill=HUNK_BG)
            draw.text((pad_x, y + 4), ln, fill=HUNK_FG, font=font)
        elif ln.startswith("+"):
            draw.rectangle([0, y, img_w, y + line_h], fill=ADD_BG)
            draw.text((pad_x, y + 4), ln, fill=ADD_FG, font=font)
        elif ln.startswith("-"):
            draw.rectangle([0, y, img_w, y + line_h], fill=DEL_BG)
            draw.text((pad_x, y + 4), ln, fill=DEL_FG, font=font)
        else:
            draw.text((pad_x, y + 4), ln, fill=FG, font=font)
        y += line_h

    img.save(out, "PNG", optimize=True)
    print(f"wrote {out} ({img_w}x{img_h})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--title", default=None)
    ap.add_argument("--label-before", default="before")
    ap.add_argument("--label-after", default="after")
    args = ap.parse_args()
    render(args.before, args.after, args.out, args.title,
           args.label_before, args.label_after)


if __name__ == "__main__":
    main()
