"""Render a UI-independent grounding-gate clip for the Phase 1 demo cut."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parent.parent
ASSET_DIR = REPO / "demo_assets" / "phase1" / "grounding_gate_dual_exit"
VIDEO_PATH = ASSET_DIR / "grounding_gate_dual_exit.mp4"
PREVIEW_PATH = ASSET_DIR / "grounding_gate_dual_exit_preview.png"
MANIFEST_PATH = ASSET_DIR / "manifest.json"
NOTES_PATH = ASSET_DIR / "notes.md"

OUTPUT_W = 1920
OUTPUT_H = 1080
BOARD_W = 2880
BOARD_H = 1620
FPS = 24
DURATION_S = 12.0
FRAME_COUNT = int(FPS * DURATION_S)

BG_TOP = (247, 242, 234)
BG_BOTTOM = (236, 229, 218)
INK = (31, 30, 26)
MUTED = (104, 99, 90)
HAIRLINE = (214, 203, 191)
RED = (173, 58, 53)
RED_FILL = (249, 236, 233)
GREEN = (37, 115, 74)
GREEN_FILL = (232, 244, 235)
AMBER = (176, 118, 34)
AMBER_FILL = (249, 240, 221)
PANEL_FILL = (252, 249, 244)
CODE_FILL = (243, 239, 232)
WHITE = (255, 255, 255)

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
SANS = FONT_DIR / "DejaVuSans.ttf"
SANS_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"
SERIF = FONT_DIR / "DejaVuSerif.ttf"
SERIF_BOLD = FONT_DIR / "DejaVuSerif-Bold.ttf"

PLOT_PATH = REPO / "docs" / "assets" / "rtk_numsv.png"
ANALYSIS_PATH = REPO / "demo_assets" / "analyses" / "sanfer_tunnel.json"
README_PATH = REPO / "demo_assets" / "grounding_gate" / "README.md"
DROP_REASONS_PATH = REPO / "demo_assets" / "grounding_gate" / "clean_recording" / "drop_reasons.json"
GATED_REPORT_PATH = REPO / "demo_assets" / "grounding_gate" / "clean_recording" / "gated_report.json"
TELEMETRY_PATH = REPO / "black-box-bench" / "cases" / "rtk_heading_break_01" / "telemetry.npz"


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def _load_json(path: Path) -> object:
    return json.loads(path.read_text())


def _blend(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_multiline(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    max_width: int,
    line_gap: int = 10,
) -> int:
    x, y = xy
    lines = _wrap_lines(draw, text, font, max_width)
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    line_height = bbox[3] - bbox[1]
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height + line_gap
    return y


def _shadow(base: Image.Image, box: tuple[int, int, int, int], radius: int = 28, alpha: int = 64) -> None:
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    x0, y0, x1, y1 = box
    sd.rounded_rectangle((x0, y0 + 10, x1, y1 + 10), radius=radius, fill=(0, 0, 0, alpha))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    base.alpha_composite(shadow)


def _panel(
    base: Image.Image,
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int] = PANEL_FILL,
    outline: tuple[int, int, int] = HAIRLINE,
    radius: int = 34,
) -> None:
    _shadow(base, box, radius=radius)
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)


def _pill(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    ink: tuple[int, int, int],
    padding_x: int = 24,
    padding_y: int = 12,
    radius: int = 28,
) -> tuple[int, int, int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    w = (bbox[2] - bbox[0]) + padding_x * 2
    h = (bbox[3] - bbox[1]) + padding_y * 2
    x, y = xy
    box = (x, y, x + w, y + h)
    draw.rounded_rectangle(box, radius=radius, fill=fill)
    draw.text((x + padding_x, y + padding_y - 2), text, font=font, fill=ink)
    return box


def _fit_image(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    scale = min(max_w / img.width, max_h / img.height)
    out_w = max(1, int(round(img.width * scale)))
    out_h = max(1, int(round(img.height * scale)))
    return img.resize((out_w, out_h), Image.Resampling.LANCZOS)


def _draw_background(base: Image.Image) -> None:
    draw = ImageDraw.Draw(base)
    for y in range(BOARD_H):
        t = y / max(1, BOARD_H - 1)
        color = _blend(BG_TOP, BG_BOTTOM, t)
        draw.line((0, y, BOARD_W, y), fill=color)
    for x in range(120, BOARD_W, 120):
        draw.line((x, 0, x, BOARD_H), fill=(255, 255, 255, 14), width=1)
    for y in range(120, BOARD_H, 120):
        draw.line((0, y, BOARD_W, y), fill=(255, 255, 255, 14), width=1)
    draw.rectangle((80, 84, BOARD_W - 80, BOARD_H - 84), outline=(255, 255, 255, 44), width=2)


def _load_refutation_data() -> dict[str, object]:
    analysis = _load_json(ANALYSIS_PATH)
    if not isinstance(analysis, dict):
        raise TypeError("sanfer analysis must be a JSON object")
    hypotheses = analysis["hypotheses"]
    if not isinstance(hypotheses, list):
        raise TypeError("hypotheses must be a list")
    refuted = next(
        hyp for hyp in hypotheses
        if isinstance(hyp, dict) and "REFUTED" in str(hyp.get("summary", ""))
    )
    with np.load(TELEMETRY_PATH) as telemetry:
        rover_num_sv = telemetry["rover_numSV"]
        min_sv = int(np.min(rover_num_sv))
        max_sv = int(np.max(rover_num_sv))
        median_sv = int(np.median(rover_num_sv))
    evidence = refuted["evidence"]
    if not isinstance(evidence, list):
        raise TypeError("refuted hypothesis evidence must be a list")
    first_sample = next(
        item for item in evidence
        if isinstance(item, dict) and item.get("topic_or_file") == "ublox_rover_navrelposned.csv"
    )
    first_t_ns = first_sample.get("t_ns")
    if not isinstance(first_t_ns, int):
        raise TypeError("expected integer t_ns on first sample evidence")
    first_t_s = first_t_ns / 1e9
    return {
        "confidence": float(refuted["confidence"]),
        "first_t_s": first_t_s,
        "summary": str(refuted["summary"]),
        "min_sv": min_sv,
        "max_sv": max_sv,
        "median_sv": median_sv,
    }


def _draw_refutation_card(
    base: Image.Image,
    box: tuple[int, int, int, int],
    draw: ImageDraw.ImageDraw,
    data: dict[str, object],
    fonts: dict[str, ImageFont.FreeTypeFont],
) -> None:
    _panel(base, box)
    x0, y0, x1, y1 = box
    inner_x = x0 + 54
    inner_y = y0 + 40
    _pill(draw, (inner_x, inner_y), "Refutation Exit", fonts["label"], RED_FILL, RED)
    title_y = inner_y + 78
    draw.text((inner_x, title_y), "Submitted narrative rejected by telemetry", font=fonts["h2"], fill=INK)
    subtitle_y = _draw_multiline(
        draw,
        (inner_x, title_y + 64),
        "The operator blamed the tunnel. The session data says the localization fault started before any tunnel window.",
        fonts["body"],
        MUTED,
        max_width=(x1 - x0) - 108,
        line_gap=8,
    )

    claim_box = (inner_x, subtitle_y + 22, x1 - 54, subtitle_y + 150)
    draw.rounded_rectangle(claim_box, radius=24, fill=RED_FILL, outline=(236, 206, 201), width=2)
    draw.text((claim_box[0] + 24, claim_box[1] + 20), "Operator claim", font=fonts["label"], fill=RED)
    draw.text((claim_box[0] + 24, claim_box[1] + 58), '"tunnel caused anomaly"', font=fonts["quote"], fill=INK)

    bullets_y = claim_box[3] + 28
    bullet_items = [
        f"RTK failure is already present at t={data['first_t_s']:.3f} s on the first NAV-RELPOSNED sample.",
        f"carr_soln stays 'none' for the entire recorded heading stream; this is not a localized event.",
        f"rover numSV stays healthy (median {data['median_sv']}, min {data['min_sv']}, max {data['max_sv']}) instead of collapsing below 4.",
    ]
    for item in bullet_items:
        draw.ellipse((inner_x, bullets_y + 16, inner_x + 14, bullets_y + 30), fill=RED)
        bullets_y = _draw_multiline(
            draw,
            (inner_x + 28, bullets_y),
            item,
            fonts["body"],
            INK,
            max_width=(x1 - x0) - 150,
            line_gap=6,
        ) + 16

    plot_box = (inner_x, y1 - 422, x1 - 54, y1 - 98)
    draw.rounded_rectangle(plot_box, radius=28, fill=WHITE, outline=HAIRLINE, width=2)
    plot = Image.open(PLOT_PATH).convert("RGB")
    plot = _fit_image(plot, plot_box[2] - plot_box[0] - 24, plot_box[3] - plot_box[1] - 24)
    plot_x = plot_box[0] + (plot_box[2] - plot_box[0] - plot.width) // 2
    plot_y = plot_box[1] + (plot_box[3] - plot_box[1] - plot.height) // 2
    base.paste(plot, (plot_x, plot_y))

    footer_text = "Sources: demo_assets/grounding_gate/README.md  |  demo_assets/analyses/sanfer_tunnel.json  |  docs/assets/rtk_numsv.png"
    draw.text((inner_x, y1 - 52), footer_text, font=fonts["foot"], fill=MUTED)


def _draw_table_row(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fonts: dict[str, ImageFont.FreeTypeFont],
    bug_class: str,
    confidence: float,
    reason: str,
    fill: tuple[int, int, int],
) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=18, fill=fill)
    bug_w = 230
    conf_w = 120
    draw.text((x0 + 24, y0 + 18), bug_class, font=fonts["mono"], fill=INK)
    draw.text((x0 + bug_w + 40, y0 + 18), f"{confidence:.2f}", font=fonts["mono"], fill=MUTED)
    _draw_multiline(
        draw,
        (x0 + bug_w + conf_w + 80, y0 + 16),
        reason,
        fonts["small"],
        INK,
        max_width=(x1 - x0) - bug_w - conf_w - 120,
        line_gap=4,
    )


def _draw_silence_card(
    base: Image.Image,
    box: tuple[int, int, int, int],
    draw: ImageDraw.ImageDraw,
    drop_reasons: list[dict[str, object]],
    gated_report: dict[str, object],
    fonts: dict[str, ImageFont.FreeTypeFont],
) -> None:
    _panel(base, box)
    x0, y0, x1, y1 = box
    inner_x = x0 + 54
    inner_y = y0 + 40
    _pill(draw, (inner_x, inner_y), "Silence Exit", fonts["label"], GREEN_FILL, GREEN)
    title_y = inner_y + 78
    draw.text((inner_x, title_y), "Clean recording ships no bug", font=fonts["h2"], fill=INK)
    subtitle_y = _draw_multiline(
        draw,
        (inner_x, title_y + 64),
        "Plausible hypotheses are allowed to die here. If evidence is thin, the report says so explicitly.",
        fonts["body"],
        MUTED,
        max_width=(x1 - x0) - 108,
        line_gap=8,
    )

    table_top = subtitle_y + 24
    draw.text((inner_x, table_top), "Dropped before PDF export", font=fonts["label"], fill=AMBER)
    header_y = table_top + 44
    draw.text((inner_x + 24, header_y), "bug_class", font=fonts["small_bold"], fill=MUTED)
    draw.text((inner_x + 280, header_y), "conf", font=fonts["small_bold"], fill=MUTED)
    draw.text((inner_x + 410, header_y), "reason dropped", font=fonts["small_bold"], fill=MUTED)

    row_y = header_y + 34
    fills = [AMBER_FILL, RED_FILL, AMBER_FILL, RED_FILL]
    for idx, item in enumerate(drop_reasons):
        row_box = (inner_x, row_y, x1 - 54, row_y + 88)
        _draw_table_row(
            draw,
            row_box,
            fonts,
            bug_class=str(item["bug_class"]),
            confidence=float(item["confidence"]),
            reason=str(item["reason_dropped"]),
            fill=fills[idx % len(fills)],
        )
        row_y += 102

    ship_box = (inner_x, y1 - 340, x1 - 54, y1 - 98)
    draw.rounded_rectangle(ship_box, radius=28, fill=CODE_FILL, outline=HAIRLINE, width=2)
    draw.text((ship_box[0] + 28, ship_box[1] + 24), "What ships", font=fonts["label"], fill=GREEN)
    mono_y = ship_box[1] + 68
    code_lines = [
        "gated_report.json",
        "hypotheses: []",
        f"patch_proposal: {gated_report['patch_proposal']}",
    ]
    for line in code_lines:
        mono_y = _draw_multiline(
            draw,
            (ship_box[0] + 28, mono_y),
            line,
            fonts["mono"],
            INK,
            max_width=ship_box[2] - ship_box[0] - 56,
            line_gap=6,
        ) + 8

    footer_text = "Sources: demo_assets/grounding_gate/clean_recording/drop_reasons.json  |  gated_report.json"
    draw.text((inner_x, y1 - 52), footer_text, font=fonts["foot"], fill=MUTED)


def _render_board() -> Image.Image:
    refutation = _load_refutation_data()
    drop_reasons = _load_json(DROP_REASONS_PATH)
    gated_report = _load_json(GATED_REPORT_PATH)
    if not isinstance(drop_reasons, list) or not isinstance(gated_report, dict):
        raise TypeError("grounding gate assets have unexpected JSON structure")

    fonts = {
        "kicker": _font(SANS_BOLD, 28),
        "title": _font(SERIF_BOLD, 70),
        "subtitle": _font(SERIF, 32),
        "h2": _font(SERIF_BOLD, 42),
        "body": _font(SANS, 31),
        "quote": _font(SERIF_BOLD, 38),
        "label": _font(SANS_BOLD, 24),
        "small": _font(SANS, 25),
        "small_bold": _font(SANS_BOLD, 24),
        "mono": _font(SANS, 26),
        "foot": _font(SANS, 22),
    }

    base = Image.new("RGBA", (BOARD_W, BOARD_H), (255, 255, 255, 255))
    _draw_background(base)
    draw = ImageDraw.Draw(base)

    _pill(draw, (120, 100), "Black Box Demo Asset  |  Phase 1  |  UI-independent", fonts["kicker"], WHITE, INK, padding_x=26, padding_y=12)
    draw.text((120, 188), "Grounding Gate", font=fonts["title"], fill=INK)
    _draw_multiline(
        draw,
        (120, 286),
        "Same deterministic filter, two visible outcomes: reject a weak story or ship silence.",
        fonts["subtitle"],
        MUTED,
        max_width=1540,
        line_gap=8,
    )
    draw.line((120, 366, BOARD_W - 120, 366), fill=HAIRLINE, width=2)

    left_box = (120, 418, 1380, 1476)
    right_box = (1500, 418, BOARD_W - 120, 1476)
    _draw_refutation_card(base, left_box, draw, refutation, fonts)
    _draw_silence_card(base, right_box, draw, drop_reasons, gated_report, fonts)

    footer_box = (120, 1488, BOARD_W - 120, BOARD_H - 34)
    draw.rounded_rectangle(footer_box, radius=26, fill=(245, 241, 234), outline=HAIRLINE, width=2)
    draw.text(
        (footer_box[0] + 34, footer_box[1] + 20),
        "Weak explanations rejected before they reach the report.",
        font=fonts["subtitle"],
        fill=INK,
    )
    _draw_multiline(
        draw,
        (footer_box[0] + 34, footer_box[1] + 66),
        "Designed to sit before the final diff reveal. Uses only repo-grounded plots, JSON artifacts, and title treatment.",
        fonts["small"],
        MUTED,
        max_width=footer_box[2] - footer_box[0] - 68,
        line_gap=6,
    )
    return base


def _interpolate_rect(a: Rect, b: Rect, t: float) -> Rect:
    e = _ease(t)
    return Rect(
        _lerp(a.x, b.x, e),
        _lerp(a.y, b.y, e),
        _lerp(a.w, b.w, e),
        _lerp(a.h, b.h, e),
    )


def _camera_rect(t: float) -> Rect:
    full = Rect(0.0, 0.0, float(BOARD_W), float(BOARD_H))
    center = Rect(210.0, 120.0, 2460.0, 1383.75)
    left = Rect(60.0, 360.0, 1980.0, 1113.75)
    right = Rect(840.0, 360.0, 1980.0, 1113.75)
    if t < 1.6:
        return _interpolate_rect(Rect(120.0, 130.0, 2640.0, 1485.0), center, t / 1.6)
    if t < 5.3:
        return _interpolate_rect(center, left, (t - 1.6) / 3.7)
    if t < 8.8:
        return _interpolate_rect(left, right, (t - 5.3) / 3.5)
    return _interpolate_rect(right, full, (t - 8.8) / (DURATION_S - 8.8))


def _render_video(board: Image.Image) -> None:
    writer = cv2.VideoWriter(
        str(VIDEO_PATH),
        cv2.VideoWriter_fourcc(*"mp4v"),
        FPS,
        (OUTPUT_W, OUTPUT_H),
    )
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not open the output video writer")

    board_rgb = board.convert("RGB")
    for frame_idx in range(FRAME_COUNT):
        t = frame_idx / FPS
        rect = _camera_rect(t)
        crop = board_rgb.crop(
            (
                int(round(rect.x)),
                int(round(rect.y)),
                int(round(rect.x + rect.w)),
                int(round(rect.y + rect.h)),
            )
        )
        frame = crop.resize((OUTPUT_W, OUTPUT_H), Image.Resampling.LANCZOS)
        if t < 0.35:
            overlay = Image.new("RGB", frame.size, (0, 0, 0))
            frame = Image.blend(overlay, frame, _ease(t / 0.35))
        frame_bgr = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
        writer.write(frame_bgr)
    writer.release()


def _write_manifest() -> None:
    manifest = {
        "id": "grounding_gate_dual_exit",
        "title": "Grounding Gate - Refutation and Silence",
        "phase": 1,
        "kind": "non_ui_clip",
        "primary_asset": VIDEO_PATH.name,
        "preview_still": PREVIEW_PATH.name,
        "duration_s": DURATION_S,
        "fps": FPS,
        "resolution": {"width": OUTPUT_W, "height": OUTPUT_H},
        "ui_independent": True,
        "final_ready": True,
        "script": "scripts/render_phase1_grounding_gate_dual_exit.py",
        "source_artifacts": [
            str(README_PATH.relative_to(REPO)),
            str(ANALYSIS_PATH.relative_to(REPO)),
            str(DROP_REASONS_PATH.relative_to(REPO)),
            str(GATED_REPORT_PATH.relative_to(REPO)),
            str(PLOT_PATH.relative_to(REPO)),
            str(TELEMETRY_PATH.relative_to(REPO)),
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")


def _write_notes() -> None:
    NOTES_PATH.write_text(
        "\n".join(
            [
                "# Grounding Gate - Refutation and Silence",
                "",
                "- what is real: The sanfer analysis JSON, clean-recording gating JSON, and RTK plot all come from repo files rendered from real artifacts.",
                "- what is composited: The title card, panel layout, typography, pan/zoom move, and highlight treatment are editorial compositing around those real artifacts.",
                "- what is placeholder: No fake UI is shown. Only the editorial chrome is provisional and can be restyled later if the overall demo look changes.",
                "- whether this asset is UI-independent: Yes. It does not depend on the unfinished product UI.",
                "- whether it is final-ready or temporary: Final-ready for Phase 1 inserts.",
                "- what should wait for the finished UI: Any handoff into the live upload / streaming-analysis beats and any UI-dependent transitions should wait for the finished product UI.",
                "",
                "## Source Files",
                "",
                "- demo_assets/grounding_gate/README.md",
                "- demo_assets/analyses/sanfer_tunnel.json",
                "- demo_assets/grounding_gate/clean_recording/drop_reasons.json",
                "- demo_assets/grounding_gate/clean_recording/gated_report.json",
                "- docs/assets/rtk_numsv.png",
                "- black-box-bench/cases/rtk_heading_break_01/telemetry.npz",
            ]
        )
        + "\n"
    )


def main() -> int:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    board = _render_board()
    board.resize((OUTPUT_W, OUTPUT_H), Image.Resampling.LANCZOS).save(PREVIEW_PATH)
    _render_video(board)
    _write_manifest()
    _write_notes()
    print(f"wrote {VIDEO_PATH}")
    print(f"wrote {PREVIEW_PATH}")
    print(f"wrote {MANIFEST_PATH}")
    print(f"wrote {NOTES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
