"""Operator-claim vs BlackBox-refutation side-by-side card. 1920x1080."""
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

ax.text(960, 1010, "sanfer_sanisidro · 1h cam-lidar bag · ROS1",
        color=MUTED, fontsize=18, ha="center")
ax.text(960, 960, "Operator says one thing. The data says another.",
        color=FG, fontsize=34, weight="bold", ha="center")

def card(x, w, color, badge, badge_label, title, body, footer):
    box = FancyBboxPatch((x, 130), w, 760,
                         boxstyle="round,pad=10,rounding_size=18",
                         linewidth=2, edgecolor=color, facecolor="#11151b")
    ax.add_patch(box)
    bx = FancyBboxPatch((x+30, 800), 220, 50,
                        boxstyle="round,pad=4,rounding_size=10",
                        edgecolor=color, facecolor=color, linewidth=0)
    ax.add_patch(bx)
    ax.text(x+140, 825, badge_label, color=BG, fontsize=18, weight="bold",
            ha="center", va="center")
    ax.text(x+30, 760, badge, color=color, fontsize=15, weight="bold")
    ax.text(x+30, 700, title, color=FG, fontsize=24, weight="bold",
            wrap=True)
    for i, ln in enumerate(body):
        ax.text(x+30, 620 - i*46, ln, color=FG, fontsize=18)
    ax.text(x+30, 170, footer, color=MUTED, fontsize=14, style="italic")

card(60, 880, RED, "OPERATOR HYPOTHESIS", "BLAMED",
     '"Tunnel ingress caused the\nGPS failure at 02:57:11."',
     ["• Tunnel entry → GPS dropout",
      "• Sensor occlusion is the cause",
      "• Recommend: reroute around tunnels",
      "",
      "Implied fix: avoid the tunnel."],
     "Source: operator handoff note")

card(980, 880, TEAL, "BLACK BOX (Opus 4.7)", "REFUTED",
     "RTK heading subsystem broken from\nt = 0.24 s — 43 min before tunnel.",
     ["• carr_soln = 'none' for 18133/18133 msgs",
      "• rel_pos_heading_valid = 0 for entire 1 h",
      "• /odometry/filtered never published",
      "• DBW enabled = 0 (manual drive throughout)",
      "• Tunnel only exposed pre-existing fault."],
     "Source: data/final_runs/sanfer_tunnel/report.md  ·  hyp #5 conf 0.05 REFUTED")

ax.annotate("", xy=(975, 510), xytext=(945, 510),
            arrowprops=dict(arrowstyle="->", color=AMBER, lw=4))

ax.text(960, 90, "Confidence on operator narrative: 0.05  ·  Top alternative: sensor_timeout @ 0.60  ·  Patch: scoped UART/RTCM3 config diff",
        ha="center", color=AMBER, fontsize=15)

OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, dpi=100, facecolor=BG)
print("wrote", OUT)
