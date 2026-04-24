# SPDX-License-Identifier: MIT
"""Boat-lidar topic-traffic strip plot.

Raw rosbag2 sqlite3 is corrupt; rosbags can't open it. We reconstruct the
finding directly from metadata.yaml: /lidar_points n=4168 @ ~10 Hz vs
/lidar_imu n=0 over 416.76 s. The bug IS the absence — a BEV point-cloud
render would hide it. Two horizontal lanes make it unmissable.

Outputs:
  demo_assets/bag_footage/boat_lidar/topic_traffic.png
  demo_assets/bag_footage/boat_lidar/topic_traffic_sweep.mp4
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import imageio_ffmpeg
import matplotlib.pyplot as plt
import numpy as np

OUT_DIR = Path("demo_assets/bag_footage/boat_lidar")
DURATION_S = 416.76
N_LIDAR = 4168
HZ_LIDAR = N_LIDAR / DURATION_S  # ~10.0
SWEEP_FRAMES = 30
SWEEP_FPS = 4


def render(playhead_s: float | None, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(14, 4.2), dpi=150)
    ax.set_xlim(0, DURATION_S)
    ax.set_ylim(-0.5, 2.5)
    ax.set_yticks([0, 1, 2])
    ax.set_yticklabels(["/lidar_imu\n(Imu)", "/lidar_points\n(PointCloud2)", "/rosout\n(Log)"],
                       fontsize=10)
    ax.set_xlabel("session time (s)   —   duration 416.76 s")
    ax.set_title("boat_lidar — per-topic message traffic (rosbag2 metadata)",
                 fontsize=12, loc="left")

    lidar_ts = np.linspace(0, DURATION_S, N_LIDAR, endpoint=False)
    # Plot only every 5th sample — 4168 ticks on a 14-in fig turns into a solid bar.
    ax.scatter(lidar_ts[::5], np.full(len(lidar_ts[::5]), 1.0),
               s=2.0, c="#2b8a3e", alpha=0.85, marker="|", linewidths=0.8)

    # /rosout: 9 messages, sparse. Place at roughly even stride for illustration.
    rosout_ts = np.linspace(10, DURATION_S - 10, 9)
    ax.scatter(rosout_ts, np.full(9, 2.0), s=60, c="#495057", marker="|", linewidths=1.2)

    # /lidar_imu: nothing. Draw the lane as a flat empty band + explicit label.
    ax.axhline(0, color="#ced4da", linewidth=0.6, zorder=0)
    ax.text(DURATION_S / 2, -0.3, "SILENT — 0 messages over entire session",
            ha="center", va="top", fontsize=11, color="#c92a2a", weight="bold")

    ax.text(5, 1.35, f"n=4168  @  {HZ_LIDAR:.2f} Hz  nominal",
            fontsize=9, color="#2b8a3e")
    ax.text(5, 2.3, "n=9 (sparse log)", fontsize=8, color="#495057")

    if playhead_s is not None:
        ax.axvline(playhead_s, color="#1971c2", linewidth=2, alpha=0.9, zorder=5)
        ax.text(playhead_s, 2.6, f"t = {playhead_s:5.1f}s",
                ha="center", fontsize=9, color="#1971c2",
                bbox=dict(facecolor="white", edgecolor="#1971c2", pad=2))

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.text(0.99, -0.22,
            "reconstructed from metadata.yaml — raw db3 is corrupt (sqlite integrity fail); "
            "recovered.sql dump 27 GB, not re-imported",
            transform=ax.transAxes, ha="right", fontsize=7, color="#868e96", style="italic")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    render(None, OUT_DIR / "topic_traffic.png")
    print(f"wrote {OUT_DIR / 'topic_traffic.png'}")

    staging = OUT_DIR / "_sweep"
    staging.mkdir(exist_ok=True)
    for p in staging.glob("*.png"):
        p.unlink()
    for i in range(SWEEP_FRAMES):
        t = DURATION_S * (i + 1) / SWEEP_FRAMES
        render(t, staging / f"f_{i:04d}.png")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out_mp4 = OUT_DIR / "topic_traffic_sweep.mp4"
    cmd = [
        ffmpeg, "-y",
        "-framerate", str(SWEEP_FPS),
        "-i", str(staging / "f_%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "20", "-preset", "slow",
        "-movflags", "+faststart",
        str(out_mp4),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-1500:])
        return r.returncode
    print(f"wrote {out_mp4} ({out_mp4.stat().st_size / 1024:.0f} KB)")
    for p in staging.glob("*.png"):
        p.unlink()
    staging.rmdir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
