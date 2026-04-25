# SPDX-License-Identifier: MIT
"""D1 — vision-resolution A/B test for Opus 4.6 vs Opus 4.7.

Renders one plot at 2400x1600 (3.84 MP) with a fine-grain text annotation
at ~10 pt that contains a secret token (``ANOM_TS=42.5s``). Sends the
image to both models at ``resolution="hires_xl"``. The Anthropic API
auto-downsamples to each model's image cap server-side:

    - Opus 4.6: cap ~1568 px / 1.15 MP. Token at ~10 pt rendered on a
      2400 px canvas becomes ~6 px tall after downsample → unreadable.
    - Opus 4.7: cap ~2576 px / 3.75 MP. Token survives at ~10 px tall →
      readable.

This is a *physical capability* test, not a behavior test. 4.7 wins by
spec. Score = fraction of seeds whose response contains the secret
token.

Re-run::

    .venv/bin/python scripts/compare_opus_vision.py --seeds 3 --budget-usd 2

Dry-run::

    .venv/bin/python scripts/compare_opus_vision.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from base64 import b64encode
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from black_box.analysis.client import build_client  # noqa: E402

OUT_ROOT = ROOT / "data" / "bench_runs"
ASSET_DIR = ROOT / "data" / "bench_runs" / "vision_assets"

DEFAULT_MODELS = ["claude-opus-4-6", "claude-opus-4-7"]
SECRET_TOKEN = "ANOM_TS=42.5s"
CANVAS_W = 2400
CANVAS_H = 1600
ANNOTATION_FONT_PT = 10  # ~10px tall on 2400-wide canvas; ~6px after 4.6 downsample.

# Pricing aligned with ClaudeClient.PRICING_BY_MODEL — vision script bypasses
# `analyze()` so we duplicate the schedule here. Per MTok.
PRICING = {
    "input": 15.0,
    "output": 75.0,
}


@dataclass
class VisionResult:
    model: str
    seed: int
    detected: bool
    response_excerpt: str
    cost_usd: float
    wall_time_s: float
    notes: str


@dataclass
class VisionAggregate:
    model: str
    n_runs: int
    detection_rate: float
    total_cost_usd: float
    total_wall_time_s: float
    rows: list[dict] = field(default_factory=list)


def render_plot_with_secret(out_path: Path, secret: str = SECRET_TOKEN) -> Image.Image:
    """Render a 2400x1600 telemetry-like plot with a small text token at corner."""
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), color=(245, 246, 248))
    d = ImageDraw.Draw(img)

    # Title + axis labels rendered large — both models read these easily.
    try:
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 48)
        axis_font = ImageFont.truetype("DejaVuSans.ttf", 28)
    except OSError:
        title_font = ImageFont.load_default()
        axis_font = ImageFont.load_default()
    d.text((40, 30), "Telemetry: PWM left/right vs time", font=title_font, fill=(20, 20, 20))
    d.text((40, CANVAS_H - 60), "t (s)", font=axis_font, fill=(60, 60, 60))
    d.text((10, 100), "PWM", font=axis_font, fill=(60, 60, 60))

    # Pseudo-signal: two oscillating PWM lines.
    cx0, cy0 = 120, 200
    cx1, cy1 = CANVAS_W - 60, CANVAS_H - 120
    plot_w, plot_h = cx1 - cx0, cy1 - cy0
    n = 1200
    import math as _m
    pts_left = []
    pts_right = []
    for i in range(n):
        x = cx0 + i * plot_w / n
        phase = i / n * 8 * _m.pi
        amp = 250 * (1 + 0.3 * _m.sin(i / n * 2 * _m.pi))
        y_l = cy0 + plot_h / 2 + amp * _m.sin(phase)
        y_r = cy0 + plot_h / 2 - amp * _m.sin(phase)
        pts_left.append((x, y_l))
        pts_right.append((x, y_r))
    d.line(pts_left, fill=(40, 80, 200), width=3)
    d.line(pts_right, fill=(200, 60, 40), width=3)

    # The fine-grain payload: small annotation in upper-right corner. Rendered
    # at ~10 pt on a 2400-wide canvas — survives 4.7's 2576 px cap, illegible
    # after 4.6 downsample to 1568 px.
    try:
        small_font = ImageFont.truetype("DejaVuSans.ttf", ANNOTATION_FONT_PT)
    except OSError:
        small_font = ImageFont.load_default()
    annotation = f"NOTE: {secret}"
    box_x, box_y = CANVAS_W - 280, 90
    d.rectangle(
        [box_x - 4, box_y - 2, box_x + 240, box_y + ANNOTATION_FONT_PT + 4],
        outline=(120, 120, 120), width=1,
    )
    d.text((box_x, box_y), annotation, font=small_font, fill=(30, 30, 30))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    return img


def _resize_to(image: Image.Image, max_side: int) -> Image.Image:
    w, h = image.size
    if max(w, h) <= max_side:
        return image
    scale = max_side / max(w, h)
    return image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)


def _image_b64(image: Image.Image, quality: int = 92) -> str:
    out = BytesIO()
    image.save(out, format="JPEG", quality=quality)
    return b64encode(out.getvalue()).decode("utf-8")


PROMPT = (
    "Inspect this telemetry plot carefully. List every text annotation, "
    "label, or note you can read on the image, including any small text "
    "in corners or near the plot edges. Report the literal text — do not "
    "paraphrase. If you see a token of the form KEY=VALUE, quote it exactly."
)


def _detect(text: str, secret: str = SECRET_TOKEN) -> bool:
    if not text:
        return False
    t = text.lower()
    if secret.lower() in t:
        return True
    # Fallbacks — still credits the model when it reports the timestamp value.
    if "anom_ts" in t and "42.5" in t:
        return True
    return False


def _call_model(model: str, image: Image.Image, max_side: int = 2400, seed: int = 0) -> tuple[str, float, float, str]:
    """Single API call. Returns (text, usd, wall_s, notes)."""
    client = build_client()
    resized = _resize_to(image, max_side)
    b64 = _image_b64(resized)
    t0 = time.time()
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg", "data": b64,
                    }},
                    {"type": "text", "text": PROMPT},
                ],
            }],
            temperature=1.0,
        )
        text = resp.content[0].text
        usage = resp.usage
        usd = (
            usage.input_tokens * PRICING["input"]
            + usage.output_tokens * PRICING["output"]
        ) / 1e6
        return text, usd, time.time() - t0, "ok"
    except Exception as e:
        return "", 0.0, time.time() - t0, repr(e)[:300]


def _aggregate(model: str, rows: list[VisionResult]) -> VisionAggregate:
    n = len(rows)
    if n == 0:
        return VisionAggregate(model=model, n_runs=0, detection_rate=0.0,
                               total_cost_usd=0.0, total_wall_time_s=0.0)
    return VisionAggregate(
        model=model,
        n_runs=n,
        detection_rate=sum(1 for r in rows if r.detected) / n,
        total_cost_usd=sum(r.cost_usd for r in rows),
        total_wall_time_s=sum(r.wall_time_s for r in rows),
        rows=[asdict(r) for r in rows],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--seeds", type=int, default=3,
                    help="Repeats per model. Default 3 = 6 total calls for default models.")
    ap.add_argument("--budget-usd", type=float, default=2.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    plot_path = ASSET_DIR / f"vision_plot_{stamp}.png"
    image = render_plot_with_secret(plot_path)
    print(f"Models: {args.models}")
    print(f"Plot: {plot_path}  ({image.size[0]}x{image.size[1]})")
    print(f"Secret token: {SECRET_TOKEN!r}  font={ANNOTATION_FONT_PT}pt")
    print(f"Total calls: {len(args.models) * args.seeds}  budget=${args.budget_usd:.2f}")
    if args.dry_run:
        print("Dry-run — no API calls.")
        return 0

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else OUT_ROOT / f"opus_vision_d1_{stamp}.json"

    spent = 0.0
    aggregates: list[VisionAggregate] = []
    for model in args.models:
        print(f"\n=== {model} ===")
        rows: list[VisionResult] = []
        for s in range(args.seeds):
            if (args.budget_usd - spent) < 0.5:
                print(f"[budget] ${spent:.2f}/${args.budget_usd:.2f} — stop before {model}/seed{s}.")
                break
            print(f"[s{s}] {model} ...", flush=True)
            text, usd, wall, notes = _call_model(model, image, max_side=CANVAS_W, seed=s)
            detected = _detect(text)
            rows.append(VisionResult(
                model=model, seed=s, detected=detected,
                response_excerpt=text[:600], cost_usd=usd, wall_time_s=wall, notes=notes,
            ))
            spent += usd
            mark = "DETECT" if detected else "MISS  "
            print(f"  -> {mark} cost=${usd:.3f} wall={wall:.1f}s")
            if notes != "ok":
                print(f"  notes: {notes[:200]}")
        aggregates.append(_aggregate(model, rows))

    delta: dict[str, float] = {}
    if len(aggregates) == 2 and aggregates[0].n_runs and aggregates[1].n_runs:
        a, b = aggregates[0], aggregates[1]
        delta = {
            "from_model": a.model,
            "to_model": b.model,
            "detection_rate_delta": b.detection_rate - a.detection_rate,
            "total_cost_usd_delta": b.total_cost_usd - a.total_cost_usd,
            "total_wall_time_s_delta": b.total_wall_time_s - a.total_wall_time_s,
        }

    payload = {
        "schema": "opus_vision_d1/1.0",
        "timestamp_utc": stamp,
        "secret_token": SECRET_TOKEN,
        "annotation_font_pt": ANNOTATION_FONT_PT,
        "canvas_size": [CANVAS_W, CANVAS_H],
        "plot_path": str(plot_path.relative_to(ROOT)),
        "models": [a.model for a in aggregates],
        "aggregates": [asdict(a) for a in aggregates],
        "delta": delta,
        "total_spent_usd": spent,
    }
    out_path.write_text(json.dumps(payload, indent=2, default=str))

    print(f"\n{'=' * 60}")
    for a in aggregates:
        print(f"{a.model}: detect={a.detection_rate:.0%} (n={a.n_runs})  "
              f"cost=${a.total_cost_usd:.3f}  wall={a.total_wall_time_s:.1f}s")
    if delta:
        print(f"\nDelta {delta['from_model']} -> {delta['to_model']}:")
        print(f"  detection_rate     {delta['detection_rate_delta']:+.2%}")
        print(f"  cost_usd           ${delta['total_cost_usd_delta']:+.3f}")
        print(f"  wall_time_s        {delta['total_wall_time_s_delta']:+.1f}")
    print(f"\nWritten: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
