"""Operator-claim vs Black Box-refutation. Two big quotes, one verdict strip."""
from __future__ import annotations
import pathlib
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.patches import FancyBboxPatch

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "demo_assets/final_demo_pack/panels/operator_vs_blackbox.png"

BG = "#0a0c10"; FG = "#e7eaee"; MUTED = "#7a8290"
AMBER = "#ffb840"; RED = "#e0625a"; TEAL = "#62d4c8"

rcParams.update({"font.family": "DejaVu Sans",
                 "savefig.facecolor": BG, "figure.facecolor": BG, "axes.facecolor": BG})

fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
ax = fig.add_axes([0,0,1,1]); ax.set_axis_off()
ax.set_xlim(0,1920); ax.set_ylim(0,1080)

ax.text(960, 1010, "Operator says one thing. The data says another.",
        color=FG, fontsize=38, weight="bold", ha="center", va="center")
ax.text(960, 950, "sanfer_sanisidro · 1h cam-lidar bag",
        color=MUTED, fontsize=18, ha="center", va="center")

def card(x, w, color, label, headline, subline):
    box = FancyBboxPatch((x, 220), w, 640,
                         boxstyle="round,pad=10,rounding_size=18",
                         linewidth=2, edgecolor=color, facecolor="#11151b")
    ax.add_patch(box)
    ax.text(x + w/2, 800, label, color=color, fontsize=18, weight="bold",
            ha="center", va="center")
    ax.text(x + w/2, 580, headline, color=FG, fontsize=44, weight="bold",
            ha="center", va="center")
    ax.text(x + w/2, 400, subline, color=color, fontsize=20,
            ha="center", va="center", style="italic")

card(60, 880, RED, "OPERATOR HYPOTHESIS",
     "Tunnel killed GPS.",
     "blame the environment")

card(980, 880, TEAL, "BLACK BOX (Opus 4.7)",
     "RTK broke at t = 0.24 s.",
     "43 minutes before the tunnel")

ax.annotate("", xy=(975, 540), xytext=(945, 540),
            arrowprops=dict(arrowstyle="->", color=AMBER, lw=4))

ax.text(960, 130,
        "confidence on operator narrative: 0.05    ·    top alternative: sensor_timeout @ 0.60",
        ha="center", color=AMBER, fontsize=18, weight="bold")
ax.text(960, 80,
        "data/final_runs/sanfer_tunnel/report.md  ·  hyp #5 REFUTED",
        ha="center", color=MUTED, fontsize=12, style="italic")

OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, dpi=100, facecolor=BG)
print("wrote", OUT)
