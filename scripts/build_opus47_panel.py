"""Render the OPUS 4.7 vs 4.6 'same accuracy, better judgment, more eyes' panel.

Reads canonical bench JSONs and produces a 1920x1080 PNG suitable for a 16:9
demo cut. Numbers come straight from data/bench_runs/*.json — no fabrication.
"""
from __future__ import annotations
import json, pathlib
import matplotlib.pyplot as plt
import matplotlib.patches as mp
from matplotlib import rcParams

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "demo_assets/final_demo_pack/panels/opus47_delta_panel.png"
NONE = ROOT / "data/bench_runs/opus46_vs_opus47_20260425T182237Z.json"
FALSE = ROOT / "data/bench_runs/opus46_vs_opus47_20260425T183141Z.json"
VISION = ROOT / "data/bench_runs/opus_vision_d1_20260425T185628Z.json"

BG = "#0a0c10"
FG = "#e7eaee"
MUTED = "#7a8290"
AMBER = "#ffb840"
TEAL = "#62d4c8"
RED = "#e0625a"

rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.edgecolor": MUTED,
    "axes.labelcolor": FG,
    "xtick.color": FG, "ytick.color": FG,
    "axes.titlecolor": FG,
    "savefig.facecolor": BG,
    "figure.facecolor": BG,
    "axes.facecolor": BG,
})

def agg(path, model):
    d = json.loads(path.read_text())
    return next(a for a in d["aggregates"] if a["model"] == model)

a46_n = agg(NONE, "claude-opus-4-6"); a47_n = agg(NONE, "claude-opus-4-7")
a46_f = agg(FALSE, "claude-opus-4-6"); a47_f = agg(FALSE, "claude-opus-4-7")
v = json.loads(VISION.read_text())
v46 = next(a for a in v["aggregates"] if a["model"] == "claude-opus-4-6")
v47 = next(a for a in v["aggregates"] if a["model"] == "claude-opus-4-7")

fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
fig.suptitle("Same accuracy. Better judgment. More eyes.",
             fontsize=34, color=FG, y=0.955, weight="bold")
fig.text(0.5, 0.905, "Opus 4.7 vs 4.6  ·  closed-taxonomy bench  ·  n=9–12 runs/model",
         ha="center", color=MUTED, fontsize=14)

def panel(ax, title, sub):
    ax.set_facecolor(BG)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(MUTED); ax.spines["bottom"].set_color(MUTED)
    ax.set_title(title, fontsize=15, color=FG, loc="left", pad=14, weight="bold")
    ax.text(0, 1.04, sub, transform=ax.transAxes, color=MUTED, fontsize=10)

def bars(ax, vals, labels, fmts, colors, ymax=None):
    x = list(range(len(vals)))
    b = ax.bar(x, vals, color=colors, width=0.55, edgecolor=BG, linewidth=2)
    ax.set_xticks(x); ax.set_xticklabels(labels, color=FG, fontsize=12)
    if ymax: ax.set_ylim(0, ymax)
    ax.tick_params(axis="y", labelsize=9)
    ax.grid(axis="y", color=MUTED, alpha=0.15)
    for rect, txt in zip(b, fmts):
        ax.text(rect.get_x() + rect.get_width()/2, rect.get_height(),
                txt, ha="center", va="bottom", color=FG, fontsize=13, weight="bold")

# Layout: 2x3 grid
g = fig.add_gridspec(2, 3, left=0.05, right=0.97, top=0.86, bottom=0.07, hspace=0.45, wspace=0.28)

# 1 — Solvable accuracy (tied)
ax = fig.add_subplot(g[0,0])
panel(ax, "Solvable accuracy", "raw bug_class match · operator-mode none · n=12")
bars(ax, [a46_n["solvable_accuracy"], a47_n["solvable_accuracy"]],
     ["4.6","4.7"], ["67%","67%"], [MUTED, AMBER], ymax=1.0)

# 2 — Abstention on under-specified
ax = fig.add_subplot(g[0,1])
panel(ax, "Calibrated abstention", "rtk_heading_break_01 (under-specified) · n=3 each")
bars(ax, [a46_n["abstention_correctness"], a47_n["abstention_correctness"]],
     ["4.6","4.7"], ["0%","100%"], [RED, TEAL], ymax=1.05)

# 3 — Brier under wrong-operator pressure (lower better)
ax = fig.add_subplot(g[0,2])
panel(ax, "Brier ↓ under wrong-operator framing",
      "operator-mode false (adversarial) · n=9 · lower = better calibrated")
bars(ax, [a46_f["brier_score"], a47_f["brier_score"]],
     ["4.6","4.7"], [f'{a46_f["brier_score"]:.3f}', f'{a47_f["brier_score"]:.3f}'],
     [RED, TEAL], ymax=0.30)

# 4 — Vision: detect 10pt token at 3.84 MP
ax = fig.add_subplot(g[1,0])
panel(ax, "Fine-grain vision (10 pt @ 3.84 MP)",
      "D1 secret-token detection · n=3 each")
bars(ax, [v46["detection_rate"], v47["detection_rate"]],
     ["4.6","4.7"], [f'{int(v46["detection_rate"]*3)}/3', f'{int(v47["detection_rate"]*3)}/3'],
     [RED, TEAL], ymax=1.05)

# 5 — Wall time (lower better)
ax = fig.add_subplot(g[1,1])
panel(ax, "Latency ↓ (wall time, total)",
      "operator-mode false · n=9 · ~30% faster")
bars(ax, [a46_f["total_wall_time_s"], a47_f["total_wall_time_s"]],
     ["4.6","4.7"], [f'{a46_f["total_wall_time_s"]:.0f}s', f'{a47_f["total_wall_time_s"]:.0f}s'],
     [MUTED, AMBER], ymax=max(a46_f["total_wall_time_s"], a47_f["total_wall_time_s"])*1.2)

# 6 — Cost (within bounds)
ax = fig.add_subplot(g[1,2])
panel(ax, "Total $ over bench",
      "operator-mode false · n=9 · 4.7 cheaper at parity")
bars(ax, [a46_f["total_cost_usd"], a47_f["total_cost_usd"]],
     ["4.6","4.7"], [f'${a46_f["total_cost_usd"]:.2f}', f'${a47_f["total_cost_usd"]:.2f}'],
     [MUTED, AMBER], ymax=max(a46_f["total_cost_usd"], a47_f["total_cost_usd"])*1.25)

fig.text(0.5, 0.025,
         "source: data/bench_runs/opus46_vs_opus47_*.json + opus_vision_d1_20260425T185628Z.json   ·   "
         "scripts: compare_opus_models.py · compare_opus_vision.py",
         ha="center", color=MUTED, fontsize=9)

OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, dpi=100, facecolor=BG)
print("wrote", OUT)
