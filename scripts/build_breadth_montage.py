"""Contact-sheet montage proving generalization: sanfer + car_1 + boat_lidar + clean.
Pulls real frames + report headlines from data/final_runs and demo_assets.
"""
from __future__ import annotations
import json, pathlib, textwrap
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.patches import FancyBboxPatch
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "demo_assets/final_demo_pack/panels/breadth_montage.png"

BG = "#0a0c10"; FG = "#e7eaee"; MUTED = "#7a8290"; AMBER = "#ffb840"; TEAL = "#62d4c8"

rcParams.update({"font.family": "DejaVu Sans",
                 "savefig.facecolor": BG, "figure.facecolor": BG, "axes.facecolor": BG})

cells = [
    ("sanfer_tunnel", "Lincoln MKZ · 1h drive",
     "RTK heading break — operator's tunnel theory refuted",
     "data/final_runs/sanfer_tunnel/bundle/frames/frame_02606.5s_dense.jpg",
     TEAL, "Tier 1"),
    ("car_1", "Cam-lidar campus run",
     "Tier-2 mining: window flagged, low confidence — honest",
     "demo_assets/bag_footage/car_1/frame_0045s.jpg",
     AMBER, "Tier 2"),
    ("boat_lidar", "Unmanned surface vessel",
     "/lidar_imu silent stream → sensor_timeout @ 0.95",
     None, AMBER, "Tier 1"),
    ("clean_recording", "Synthetic clean bag",
     "Grounding gate fires → hypotheses=[], NO_ANOMALY_PATCH",
     None, MUTED, "Tier 2"),
]

fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
fig.suptitle("Generalization across platforms", fontsize=30, color=FG, y=0.95, weight="bold")
fig.text(0.5, 0.90, "Same pipeline. Different robots. Honest verdicts.",
         ha="center", color=MUTED, fontsize=15)

g = fig.add_gridspec(2, 2, left=0.04, right=0.96, top=0.85, bottom=0.06,
                     hspace=0.18, wspace=0.06)
positions = [(0,0),(0,1),(1,0),(1,1)]

for (case, sub, line, frame, color, tier), (r,c) in zip(cells, positions):
    ax = fig.add_subplot(g[r,c])
    ax.set_facecolor("#11151b")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(color); s.set_linewidth(2)
    fp = ROOT / frame if frame else None
    if fp and fp.exists():
        img = Image.open(fp)
        ax.imshow(img, aspect="auto", extent=(0,1,0.25,1))
    else:
        ax.text(0.5, 0.65, "[ telemetry-only ]", color=MUTED, fontsize=22,
                ha="center", va="center", transform=ax.transAxes, style="italic")
    ax.set_xlim(0,1); ax.set_ylim(0,1)
    ax.text(0.02, 0.20, case, color=FG, fontsize=20, weight="bold", transform=ax.transAxes)
    ax.text(0.02, 0.14, sub, color=MUTED, fontsize=13, transform=ax.transAxes)
    ax.text(0.02, 0.05, line, color=color, fontsize=14, transform=ax.transAxes, weight="bold")
    ax.text(0.98, 0.94, tier, color=color, fontsize=12, weight="bold",
            ha="right", va="top", transform=ax.transAxes,
            bbox=dict(facecolor=BG, edgecolor=color, boxstyle="round,pad=0.4"))

OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, dpi=100, facecolor=BG)
print("wrote", OUT)
