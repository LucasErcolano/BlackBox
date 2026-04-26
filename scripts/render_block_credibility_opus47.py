# SPDX-License-Identifier: MIT
"""Render credibility montage: Opus 4.7 delta + breadth + grounding + bench/cost outro.

40-50s, 1920x1080, 30fps. Six static keyframe PNGs + ffmpeg xfade chain.
Sources: data/bench_runs/*.json, docs/OPUS47_DELTA.md, demo_assets/* (real artifacts).
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
OUT = ROOT / "video_assets" / "block_credibility_opus47"
OUT.mkdir(parents=True, exist_ok=True)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

W, H = 1920, 1080
FPS = 30

BG = (10, 12, 16)
FG = (230, 232, 236)
DIM = (120, 128, 140)
PANEL = (18, 20, 26)
BORDER = (60, 66, 78)
AMBER = (255, 184, 64)
TEAL = (98, 212, 200)
RED = (224, 98, 90)
MUTED_AMBER = (196, 150, 72)

NONE_BENCH = ROOT / "data/bench_runs/opus46_vs_opus47_20260425T182237Z.json"
FALSE_BENCH = ROOT / "data/bench_runs/opus46_vs_opus47_20260425T183141Z.json"
VISION_BENCH = ROOT / "data/bench_runs/opus_vision_d1_20260425T185628Z.json"

DELTA_PANEL = ROOT / "demo_assets/final_demo_pack/panels/opus47_delta_panel.png"
BREADTH_PANEL = ROOT / "demo_assets/final_demo_pack/panels/breadth_montage.png"


def font(p: str, s: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(p, s)


def grid_bg(img: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=(18, 20, 26), width=1)
    for y in range(0, H, 80):
        d.line([(0, y), (W, y)], fill=(18, 20, 26), width=1)


def shadow_for(w: int, h: int, pad: int = 20, alpha: int = 140, blur: int = 18) -> Image.Image:
    sh = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([(pad, pad), (w + pad, h + pad)], fill=(0, 0, 0, alpha))
    return sh.filter(ImageFilter.GaussianBlur(blur))


def draw_text_centered(d: ImageDraw.ImageDraw, xy, text: str, f, fill) -> None:
    bbox = d.textbbox((0, 0), text, font=f)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    d.text((xy[0] - w // 2, xy[1] - h // 2), text, font=f, fill=fill)


def beat_footer(d: ImageDraw.ImageDraw, label: str, idx: int, total: int = 6) -> None:
    fm = font(FONT_MONO, 16)
    cx = W // 2
    y = H - 60
    gap = 28
    start = cx - (total - 1) * gap // 2
    for i in range(total):
        x = start + i * gap
        col = MUTED_AMBER if i == idx else (60, 64, 72)
        d.ellipse([(x - 6, y - 6), (x + 6, y + 6)], fill=col)
    d.text((40, H - 40), label, font=fm, fill=(90, 96, 108))
    d.text((W - 380, H - 40), "BLACK BOX · credibility montage", font=fm, fill=(90, 96, 108))


# ---------------------------------------------------------------------------
# Beat 1 — title card
# ---------------------------------------------------------------------------
def beat_title() -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    d = ImageDraw.Draw(img)

    fb = font(FONT_BOLD, 84)
    fs = font(FONT_REG, 32)
    fm = font(FONT_MONO, 22)
    fm_b = font(FONT_MONO_BOLD, 28)

    draw_text_centered(d, (W // 2, 380), "Same accuracy.", fb, FG)
    draw_text_centered(d, (W // 2, 480), "Better judgment.", fb, AMBER)
    draw_text_centered(d, (W // 2, 580), "More eyes.", fb, TEAL)

    d.rectangle([(W // 2 - 140, 660), (W // 2 + 140, 662)], fill=DIM)
    draw_text_centered(d, (W // 2, 700), "Opus 4.7 vs 4.6  ·  closed-taxonomy bench  ·  n=9–12 runs/model",
                       fs, DIM)
    draw_text_centered(d, (W // 2, 760), "source: docs/OPUS47_DELTA.md  ·  data/bench_runs/*.json",
                       fm, (90, 96, 108))

    beat_footer(d, "block 01 · framing", 0)
    return img


# ---------------------------------------------------------------------------
# Beat 2 — Opus 4.7 delta panel (use prebuilt PNG, add framing)
# ---------------------------------------------------------------------------
def beat_delta_panel() -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    d = ImageDraw.Draw(img)

    panel = Image.open(DELTA_PANEL).convert("RGBA")
    # scale to 92% width, keep aspect
    scale = 0.94
    pw, ph = int(W * scale), int(H * scale)
    panel = panel.resize((pw, ph), Image.LANCZOS)
    px = (W - pw) // 2
    py = (H - ph) // 2 - 10
    sh = shadow_for(pw, ph, pad=24, alpha=160, blur=22)
    img.alpha_composite(sh, (px - 24, py - 24))
    img.alpha_composite(panel, (px, py))

    fm = font(FONT_MONO, 16)
    d.text((40, H - 40), "block 02 · 4.7 vs 4.6 delta",
           font=fm, fill=(90, 96, 108))
    d.text((W - 480, H - 40), "src: data/bench_runs/opus46_vs_opus47_*.json",
           font=fm, fill=(90, 96, 108))
    return img


# ---------------------------------------------------------------------------
# Beat 3 — breadth: car sessions + boat lidar (use prebuilt panel)
# ---------------------------------------------------------------------------
def beat_breadth() -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    d = ImageDraw.Draw(img)

    fb = font(FONT_BOLD, 56)
    fs = font(FONT_REG, 26)
    draw_text_centered(d, (W // 2, 80), "Not a one-bag demo.", fb, FG)
    draw_text_centered(d, (W // 2, 130), "Same pipeline · Lincoln MKZ · campus rover · USV lidar",
                       fs, DIM)

    panel = Image.open(BREADTH_PANEL).convert("RGBA")
    pw = int(W * 0.78)
    ph = int(panel.height * pw / panel.width)
    panel = panel.resize((pw, ph), Image.LANCZOS)
    px = (W - pw) // 2
    py = 180
    sh = shadow_for(pw, ph, pad=20, alpha=150, blur=18)
    img.alpha_composite(sh, (px - 20, py - 20))
    img.alpha_composite(panel, (px, py))

    fm = font(FONT_MONO, 16)
    d.text((40, H - 40), "block 03 · platform breadth",
           font=fm, fill=(90, 96, 108))
    d.text((W - 520, H - 40),
           "src: data/final_runs/{sanfer_tunnel, car_1, boat_lidar}",
           font=fm, fill=(90, 96, 108))
    return img


# ---------------------------------------------------------------------------
# Beat 4 — grounding gate: clean bag → no anomaly
# ---------------------------------------------------------------------------
def beat_grounding() -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    d = ImageDraw.Draw(img)

    fb = font(FONT_BOLD, 52)
    fs = font(FONT_REG, 26)
    fm = font(FONT_MONO, 22)
    fm_b = font(FONT_MONO_BOLD, 24)

    draw_text_centered(d, (W // 2, 70), "Clean bag in. Empty report out.", fb, FG)
    draw_text_centered(d, (W // 2, 122),
                       "grounding gate · min 2 evidence rows · min 2 sources · conf ≥ 0.40",
                       fs, DIM)

    # Left: rejected hypotheses (real drop_reasons.json)
    drops = json.loads((ROOT / "demo_assets/grounding_gate/clean_recording/drop_reasons.json").read_text())
    left_x = 80
    box_w = 880
    box_h = 700
    box = Image.new("RGBA", (box_w, box_h), PANEL + (255,))
    bd = ImageDraw.Draw(box)
    bd.rectangle([(0, 0), (box_w - 1, box_h - 1)], outline=BORDER, width=2)
    bd.rectangle([(0, 0), (box_w, 50)], fill=(28, 30, 36))
    bd.text((20, 14), "raw_hypotheses → drop_reasons", font=fm_b, fill=FG)

    y = 80
    for h in drops:
        bd.rectangle([(20, y), (box_w - 20, y + 130)], outline=(60, 30, 30), width=2)
        bd.text((36, y + 16), h["bug_class"], font=font(FONT_MONO_BOLD, 24), fill=(170, 170, 175))
        bd.text((36, y + 52), f"conf {h['confidence']:.2f}", font=fm, fill=(140, 100, 100))
        bd.line([(28, y + 24), (box_w - 28, y + 24)], fill=(170, 86, 86), width=2)
        bd.text((36, y + 86), f"drop: {h['reason_dropped']}", font=fm, fill=(180, 130, 130))
        # REJECTED tag
        bd.rectangle([(box_w - 180, y + 14), (box_w - 28, y + 54)], outline=(170, 86, 86), width=2)
        bd.text((box_w - 162, y + 22), "REJECTED", font=font(FONT_MONO_BOLD, 20), fill=(170, 86, 86))
        y += 150

    sh = shadow_for(box_w, box_h)
    img.alpha_composite(sh, (left_x - 20, 180 - 20))
    img.alpha_composite(box, (left_x, 180))

    # Right: gated_report.json hero
    right_x = left_x + box_w + 60
    rb_w = W - right_x - 80
    rb_h = box_h
    card = Image.new("RGBA", (rb_w, rb_h), PANEL + (255,))
    cd = ImageDraw.Draw(card)
    cd.rectangle([(0, 0), (rb_w - 1, rb_h - 1)], outline=BORDER, width=2)
    cd.rectangle([(0, 0), (rb_w, 50)], fill=(28, 30, 36))
    cd.text((20, 14), "gated_report.json", font=fm_b, fill=FG)

    fmh = font(FONT_MONO, 24)
    lines = [
        ("{",                                         FG),
        ('  "timeline": [ session start, end ],',     DIM),
        ('  "hypotheses": [],',                       MUTED_AMBER),
        ('  "root_cause_idx": 0,',                    DIM),
        ('  "patch_proposal":',                       FG),
        ('    "No anomaly detected with',             FG),
        ('     sufficient evidence to support',       FG),
        ('     a scoped fix."',                       FG),
        ("}",                                         FG),
    ]
    yy = 90
    for ln, col in lines:
        cd.text((30, yy), ln, font=fmh, fill=col)
        yy += 38

    cd.rectangle([(30, rb_h - 110), (rb_w - 30, rb_h - 108)], fill=(60, 64, 72))
    cd.text((30, rb_h - 90), "no evidence · no claim",
            font=font(FONT_MONO_BOLD, 26), fill=MUTED_AMBER)
    cd.text((30, rb_h - 50), "src: demo_assets/grounding_gate/clean_recording/",
            font=font(FONT_MONO, 16), fill=(90, 96, 108))

    sh2 = shadow_for(rb_w, rb_h)
    img.alpha_composite(sh2, (right_x - 20, 180 - 20))
    img.alpha_composite(card, (right_x, 180))

    fm2 = font(FONT_MONO, 16)
    d.text((40, H - 40), "block 04 · grounding gate · no hallucination",
           font=fm2, fill=(90, 96, 108))
    return img


# ---------------------------------------------------------------------------
# Beat 5 — bench coverage card
# ---------------------------------------------------------------------------
def beat_bench() -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    d = ImageDraw.Draw(img)

    fb = font(FONT_BOLD, 56)
    fs = font(FONT_REG, 28)
    fm = font(FONT_MONO, 22)
    fm_b = font(FONT_MONO_BOLD, 28)

    draw_text_centered(d, (W // 2, 90), "Backed by a public benchmark.", fb, FG)
    draw_text_centered(d, (W // 2, 150),
                       "black-box-bench · 9 cases · 7-class taxonomy · MIT",
                       fs, DIM)

    # Two cards: cases + axes
    card_y = 230
    card_h = 700
    gap = 60
    card_w = (W - 160 - gap) // 2

    def card(x, title, rows):
        c = Image.new("RGBA", (card_w, card_h), PANEL + (255,))
        cd = ImageDraw.Draw(c)
        cd.rectangle([(0, 0), (card_w - 1, card_h - 1)], outline=BORDER, width=2)
        cd.rectangle([(0, 0), (card_w, 60)], fill=(28, 30, 36))
        cd.text((24, 16), title, font=fm_b, fill=FG)
        yy = 100
        for label, val, col in rows:
            cd.text((30, yy), label, font=fm, fill=DIM)
            cd.text((card_w - 320, yy), val, font=font(FONT_MONO_BOLD, 24), fill=col)
            yy += 60
        sh = shadow_for(card_w, card_h)
        img.alpha_composite(sh, (x - 20, card_y - 20))
        img.alpha_composite(c, (x, card_y))

    cases = [
        ("bad_gain_01",         "PID/gain",        FG),
        ("pid_saturation_01",   "PID saturation",  FG),
        ("sensor_timeout_01",   "sensor timeout",  FG),
        ("rtk_heading_break_01","under-specified", AMBER),
        ("sanfer_tunnel_01",    "real Lincoln MKZ", TEAL),
        ("car_1_01",            "campus rover",    TEAL),
        ("boat_lidar_01",       "USV lidar-only",  TEAL),
        ("sensor_drop_cameras_01","cam drop",      FG),
        ("reflect_public_01",   "reflection",      FG),
    ]
    axes = [
        ("solvable accuracy",    "67% = 67%",  FG),
        ("calibrated abstention","0%  →  100%", TEAL),
        ("Brier (op pressure)",  "0.239 → 0.162", TEAL),
        ("fine vision (10 pt)",  "0/3  →  3/3", TEAL),
        ("wall-time latency",    "~30% faster", AMBER),
        ("cost @ parity",        "≈ tied raw",  FG),
        ("seeds / case / model", "3 each, n=9–12", DIM),
        ("scoring",              "exact bug_class match + grounding", DIM),
    ]
    card(80, "9 bench cases (black-box-bench/cases)",
         [(c, lab, col) for c, lab, col in cases])
    card(80 + card_w + gap, "5 evaluation axes (vs raw bug_match)",
         axes)

    fm2 = font(FONT_MONO, 16)
    d.text((40, H - 40),
           "block 05 · benchmark coverage  ·  scripts/compare_opus_models.py · compare_opus_vision.py",
           font=fm2, fill=(90, 96, 108))
    return img


# ---------------------------------------------------------------------------
# Beat 6 — cost / reproducibility outro
# ---------------------------------------------------------------------------
def beat_outro() -> Image.Image:
    img = Image.new("RGBA", (W, H), BG + (255,))
    grid_bg(img)
    d = ImageDraw.Draw(img)

    # Aggregate spend from costs.jsonl (real number, not invented)
    costs_file = ROOT / "data/costs.jsonl"
    total_usd = 0.0
    n_calls = 0
    if costs_file.exists():
        for line in costs_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                total_usd += float(rec.get("usd_cost", rec.get("usd", 0.0)) or 0.0)
                n_calls += 1
            except Exception:
                continue

    fb = font(FONT_BOLD, 80)
    fs = font(FONT_REG, 30)
    fm = font(FONT_MONO, 24)
    fm_b = font(FONT_MONO_BOLD, 32)

    draw_text_centered(d, (W // 2, 200), "Reproducible.", fb, FG)
    draw_text_centered(d, (W // 2, 290), "Logged. Open.", fb, AMBER)

    # Stats row
    stats = [
        ("API calls logged", f"{n_calls}",            FG),
        ("Total spend",      f"${total_usd:,.2f}",    TEAL),
        ("Hard cap",         "$500",                  DIM),
        ("Bench cases",      "9",                     FG),
        ("Models compared",  "Opus 4.7 vs 4.6",       AMBER),
    ]
    n = len(stats)
    cell_w = (W - 200) // n
    base_x = 100
    base_y = 480
    for i, (lab, val, col) in enumerate(stats):
        cx = base_x + i * cell_w + cell_w // 2
        draw_text_centered(d, (cx, base_y), val, fm_b, col)
        draw_text_centered(d, (cx, base_y + 52), lab, fm, DIM)

    d.rectangle([(W // 2 - 200, 620), (W // 2 + 200, 622)], fill=(60, 64, 72))
    draw_text_centered(d, (W // 2, 680),
                       "every Claude call → data/costs.jsonl  (cached + uncached tokens, USD)",
                       fs, DIM)
    draw_text_centered(d, (W // 2, 740),
                       "harness: scripts/compare_opus_models.py  ·  scripts/compare_opus_vision.py",
                       fm, DIM)
    draw_text_centered(d, (W // 2, 790),
                       "doc: docs/OPUS47_DELTA.md  ·  bench: black-box-bench/ (MIT)",
                       fm, DIM)

    draw_text_centered(d, (W // 2, 920), "BLACK  BOX  —  forensic copilot for robots",
                       font(FONT_MONO_BOLD, 30), FG)

    fm2 = font(FONT_MONO, 16)
    d.text((40, H - 40), "block 06 · reproducibility outro",
           font=fm2, fill=(90, 96, 108))
    return {"img": img, "total_usd": total_usd, "n_calls": n_calls}


# ---------------------------------------------------------------------------
# Render + ffmpeg xfade chain
# ---------------------------------------------------------------------------
DURATIONS = [7, 8, 11, 8, 8, 6]   # 48s raw, -2.5s of overlap = 45.5s
XFADE = 0.5


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="cred_opus47_"))
    print(f"tmp: {tmp}", file=sys.stderr)

    print("rendering keyframes…", file=sys.stderr)
    outro_data = beat_outro()
    keys = [
        beat_title(),
        beat_delta_panel(),
        beat_breadth(),
        beat_grounding(),
        beat_bench(),
        outro_data["img"],
    ]
    paths = []
    for i, k in enumerate(keys):
        p = tmp / f"k_{i}.png"
        k.convert("RGB").save(p, "PNG", optimize=False)
        paths.append(p)

    # preview = beat 2 (delta panel) — most visually distinctive
    keys[1].convert("RGB").save(OUT / "preview.png", "PNG", optimize=True)

    # Build ffmpeg command
    cmd = ["ffmpeg", "-y"]
    for p, dur in zip(paths, DURATIONS):
        cmd += ["-loop", "1", "-t", str(dur), "-i", str(p)]

    # filter_complex: chain xfades
    parts = []
    last = "[0:v]"
    cum_offset = 0.0
    for i in range(1, len(paths)):
        cum_offset += DURATIONS[i - 1] - XFADE
        out_lbl = f"[v{i}]" if i < len(paths) - 1 else "[vout]"
        parts.append(
            f"{last}[{i}:v]xfade=transition=fade:duration={XFADE}:offset={cum_offset:.3f}{out_lbl}"
        )
        last = out_lbl
    fc = ";".join(parts)

    out_mp4 = OUT / "clip.mp4"
    cmd += [
        "-filter_complex", fc,
        "-map", "[vout]",
        "-r", str(FPS),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "medium", "-crf", "18",
        "-movflags", "+faststart",
        str(out_mp4),
    ]
    print("ffmpeg…", file=sys.stderr)
    subprocess.run(cmd, check=True)

    # Manifest
    total_dur = sum(DURATIONS) - XFADE * (len(DURATIONS) - 1)
    manifest = {
        "name": "block_credibility_opus47",
        "title": "Same accuracy. Better judgment. More eyes.",
        "duration_s": round(total_dur, 2),
        "fps": FPS,
        "resolution": [W, H],
        "beats": [
            {"i": 0, "name": "title",     "dur_s": DURATIONS[0],
             "headline": "Opus 4.7 vs 4.6 framing"},
            {"i": 1, "name": "delta_panel","dur_s": DURATIONS[1],
             "headline": "6 axes: solvable acc tied, abstention 0→100, Brier 0.239→0.162, vision 0/3→3/3, ~30% faster, $ tied"},
            {"i": 2, "name": "breadth",   "dur_s": DURATIONS[2],
             "headline": "Lincoln MKZ + campus rover + USV lidar"},
            {"i": 3, "name": "grounding", "dur_s": DURATIONS[3],
             "headline": "clean bag → 4 hypotheses dropped → empty report"},
            {"i": 4, "name": "bench",     "dur_s": DURATIONS[4],
             "headline": "9 cases × 5 evaluation axes"},
            {"i": 5, "name": "outro",     "dur_s": DURATIONS[5],
             "headline": "logged + reproducible + open"},
        ],
        "sources": {
            "delta_panel_png": str(DELTA_PANEL.relative_to(ROOT)),
            "breadth_panel_png": str(BREADTH_PANEL.relative_to(ROOT)),
            "bench_none_pass": str(NONE_BENCH.relative_to(ROOT)),
            "bench_false_pass": str(FALSE_BENCH.relative_to(ROOT)),
            "bench_vision": str(VISION_BENCH.relative_to(ROOT)),
            "grounding_dir": "demo_assets/grounding_gate/clean_recording",
            "cost_ledger": "data/costs.jsonl",
            "doc": "docs/OPUS47_DELTA.md",
            "pr_referenced": "PR #142",
            "harness_scripts": [
                "scripts/compare_opus_models.py",
                "scripts/compare_opus_vision.py",
            ],
        },
        "claims": {
            "simple_post_mortem_acc":       {"4.6": "67%",  "4.7": "67%"},
            "under_specified_abstention":   {"4.6": "0%",   "4.7": "100%"},
            "operator_pressure_brier":      {"4.6": 0.239,  "4.7": 0.162},
            "fine_visual_detection_3.84MP": {"4.6": "0/3",  "4.7": "3/3"},
            "telemetry_text_latency_speedup": "~30% faster on 4.7",
            "explicit_non_claim": "We do NOT claim 4.7 is more accurate on simple cases — it is tied.",
        },
        "cost_state_at_render": {
            "total_usd": round(outro_data["total_usd"], 4),
            "calls_logged": outro_data["n_calls"],
        },
        "outputs": {
            "video": "video_assets/block_credibility_opus47/clip.mp4",
            "preview": "video_assets/block_credibility_opus47/preview.png",
            "manifest": "video_assets/block_credibility_opus47/manifest.json",
            "notes": "video_assets/block_credibility_opus47/notes.md",
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    notes = f"""# block_credibility_opus47 — editor notes

**Duration:** {total_dur:.1f}s @ {FPS}fps · 1920×1080 · libx264 yuv420p crf 18.

## Six beats

| # | Name | Dur | Sources |
|---|---|---|---|
| 1 | title           | {DURATIONS[0]}s | static — framing line |
| 2 | delta_panel     | {DURATIONS[1]}s | `{DELTA_PANEL.relative_to(ROOT)}` |
| 3 | breadth         | {DURATIONS[2]}s | `{BREADTH_PANEL.relative_to(ROOT)}` |
| 4 | grounding       | {DURATIONS[3]}s | `demo_assets/grounding_gate/clean_recording/` |
| 5 | bench           | {DURATIONS[4]}s | `black-box-bench/cases/` (9), `{NONE_BENCH.name}`, `{FALSE_BENCH.name}` |
| 6 | outro           | {DURATIONS[5]}s | `data/costs.jsonl` (live: ${outro_data['total_usd']:.2f}, {outro_data['n_calls']} calls) |

Crossfade: {XFADE}s between beats.

## What this clip claims (and explicitly does NOT)

- **Tied** simple-post-mortem accuracy: 4.6 = 67%, 4.7 = 67%. Not "4.7 better at solving."
- **Calibrated abstention** on under-specified `rtk_heading_break_01`: 4.6 = 0/3, 4.7 = 3/3.
- **Brier under wrong-operator pressure:** 4.6 = 0.239, 4.7 = 0.162 (lower = better).
- **Fine-grain vision:** 10 pt token rendered at 3.84 MP — 4.6 = 0/3, 4.7 = 3/3.
- **Latency:** ~30% faster on 4.7 telemetry/text path.

## How to re-render

```bash
.venv/bin/python scripts/build_opus47_panel.py
.venv/bin/python scripts/build_breadth_montage.py
.venv/bin/python scripts/render_block_credibility_opus47.py
```

## No-final-UI guarantee

This block uses zero `src/black_box/ui/` artifacts. All visuals are generated
from bench JSON + grounding-gate JSON + cost ledger + pre-rendered panels.
"""
    (OUT / "notes.md").write_text(notes)

    shutil.rmtree(tmp)
    print(f"wrote {out_mp4}")
    print(f"wrote {OUT/'preview.png'}")
    print(f"wrote {OUT/'manifest.json'}")
    print(f"wrote {OUT/'notes.md'}")


if __name__ == "__main__":
    main()
