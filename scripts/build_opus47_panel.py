"""OPUS 4.7 vs 4.6 — three hero stats. Less text, bigger numbers, faster read."""
from __future__ import annotations
import json, pathlib
import matplotlib.pyplot as plt
from matplotlib import rcParams

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "demo_assets/final_demo_pack/panels/opus47_delta_panel.png"
NONE = ROOT / "data/bench_runs/opus46_vs_opus47_20260425T182237Z.json"
FALSE = ROOT / "data/bench_runs/opus46_vs_opus47_20260425T183141Z.json"
VISION = ROOT / "data/bench_runs/opus_vision_d1_20260425T185628Z.json"

BG = "#0a0c10"; FG = "#e7eaee"; MUTED = "#7a8290"
AMBER = "#ffb840"; TEAL = "#62d4c8"; RED = "#e0625a"

rcParams.update({"font.family": "DejaVu Sans",
                 "savefig.facecolor": BG, "figure.facecolor": BG, "axes.facecolor": BG})

def agg(path, model):
    d = json.loads(path.read_text())
    return next(a for a in d["aggregates"] if a["model"] == model)

a46_n = agg(NONE, "claude-opus-4-6"); a47_n = agg(NONE, "claude-opus-4-7")
a46_f = agg(FALSE, "claude-opus-4-6"); a47_f = agg(FALSE, "claude-opus-4-7")
v = json.loads(VISION.read_text())
v46 = next(a for a in v["aggregates"] if a["model"] == "claude-opus-4-6")
v47 = next(a for a in v["aggregates"] if a["model"] == "claude-opus-4-7")

fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
fig.text(0.5, 0.88, "Opus 4.7 — better judgment, sharper eyes",
         ha="center", va="center", color=FG, fontsize=38, weight="bold")
fig.text(0.5, 0.81, "Same accuracy on solvable bugs. Big wins where it matters.",
         ha="center", va="center", color=MUTED, fontsize=18)

cards = [
    ("Calibrated abstention", "under-specified bugs",
     f"{int(a46_n['abstention_correctness']*100)}%", f"{int(a47_n['abstention_correctness']*100)}%",
     "0% → 100%"),
    ("Brier score (lower = better)", "wrong-operator framing",
     f"{a46_f['brier_score']:.2f}", f"{a47_f['brier_score']:.2f}",
     f"{(1 - a47_f['brier_score']/a46_f['brier_score'])*100:.0f}% better calibrated"),
    ("Fine-grain vision", "10 pt token @ 3.84 MP",
     f"{int(v46['detection_rate']*3)}/3", f"{int(v47['detection_rate']*3)}/3",
     "0 → 3 detections"),
]

g = fig.add_gridspec(1, 3, left=0.05, right=0.95, top=0.68, bottom=0.18, wspace=0.08)

for i, (title, sub, old, new, delta) in enumerate(cards):
    ax = fig.add_subplot(g[0, i])
    ax.set_facecolor("#11151b")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_color(TEAL); s.set_linewidth(2)
    ax.text(0.5, 0.92, title, color=FG, fontsize=18, weight="bold",
            ha="center", va="top", transform=ax.transAxes)
    ax.text(0.5, 0.83, sub, color=MUTED, fontsize=12,
            ha="center", va="top", transform=ax.transAxes)
    ax.text(0.22, 0.50, old, color=MUTED, fontsize=44, weight="bold",
            ha="center", va="center", transform=ax.transAxes)
    ax.text(0.5, 0.50, "→", color=FG, fontsize=36,
            ha="center", va="center", transform=ax.transAxes)
    ax.text(0.78, 0.50, new, color=TEAL, fontsize=52, weight="bold",
            ha="center", va="center", transform=ax.transAxes)
    ax.text(0.22, 0.22, "Opus 4.6", color=MUTED, fontsize=12,
            ha="center", va="center", transform=ax.transAxes)
    ax.text(0.78, 0.22, "Opus 4.7", color=TEAL, fontsize=12, weight="bold",
            ha="center", va="center", transform=ax.transAxes)
    ax.text(0.5, 0.08, delta, color=AMBER, fontsize=14, weight="bold",
            ha="center", va="center", transform=ax.transAxes, style="italic")

fig.text(0.5, 0.07, "n=9–12 runs/model  ·  data/bench_runs/opus46_vs_opus47_*.json",
         ha="center", color=MUTED, fontsize=11)

OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, dpi=100, facecolor=BG)
print("wrote", OUT)
