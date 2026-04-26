"""Generalization montage: 4 platforms, one pipeline. Minimal text per cell."""
from __future__ import annotations
import pathlib
import matplotlib.pyplot as plt
from matplotlib import rcParams
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "demo_assets/final_demo_pack/panels/breadth_montage.png"

BG = "#0a0c10"; FG = "#e7eaee"; MUTED = "#7a8290"
AMBER = "#ffb840"; TEAL = "#62d4c8"

rcParams.update({"font.family": "DejaVu Sans",
                 "savefig.facecolor": BG, "figure.facecolor": BG, "axes.facecolor": BG})

cells = [
    ("Lincoln MKZ",     "RTK heading break",      "demo_assets/bag_footage/sanfer_tunnel/frame_02634.1s_dense.jpg", TEAL),
    ("Campus shuttle",  "low-confidence window",  "demo_assets/bag_footage/car_1/frame_0045s.jpg",                  AMBER),
    ("USV (boat)",      "sensor_timeout @ 0.95",  None,                                                              AMBER),
    ("Clean bag",       "no_anomaly (honest)",    None,                                                              MUTED),
]

fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
fig.text(0.5, 0.92, "Same pipeline. Four robots.",
         ha="center", va="center", color=FG, fontsize=38, weight="bold")
fig.text(0.5, 0.86, "Honest verdicts, every time.",
         ha="center", va="center", color=MUTED, fontsize=18)

g = fig.add_gridspec(2, 2, left=0.05, right=0.95, top=0.78, bottom=0.06, hspace=0.10, wspace=0.05)
positions = [(0,0),(0,1),(1,0),(1,1)]

for (name, verdict, frame, color), (r,c) in zip(cells, positions):
    ax = fig.add_subplot(g[r,c])
    ax.set_facecolor("#11151b")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_color(color); s.set_linewidth(2)
    fp = ROOT / frame if frame else None
    if fp and fp.exists():
        ax.imshow(Image.open(fp), aspect="auto", extent=(0,1,0.18,1))
    else:
        ax.text(0.5, 0.6, "telemetry only", color=MUTED, fontsize=22,
                ha="center", va="center", transform=ax.transAxes, style="italic")
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    ax.text(0.03, 0.10, name, color=FG, fontsize=24, weight="bold", transform=ax.transAxes)
    ax.text(0.97, 0.10, verdict, color=color, fontsize=20, weight="bold",
            ha="right", transform=ax.transAxes)

OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, dpi=100, facecolor=BG)
print("wrote", OUT)
