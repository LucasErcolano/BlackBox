# SPDX-License-Identifier: MIT
"""Sparse extract /cam1/image_raw/compressed from the 364 GB sanfer 2_cam-lidar.bag.

Filters to the cam1 connection and decodes ~N frames at uniform time stride.
Stops iteration after the last target is hit. Writes JPGs to
data/final_runs/sanfer_tunnel/bundle/frames/ and mirrors into
demo_assets/bag_footage/sanfer_tunnel/.
"""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from rosbags.highlevel import AnyReader

BAG = Path("/mnt/hdd/sanfer_sanisidro/2_cam-lidar.bag")
TOPIC = "/cam1/image_raw/compressed"
N_FRAMES = 30

OUT_BUNDLE = Path("data/final_runs/sanfer_tunnel/bundle/frames")
OUT_DEMO = Path("demo_assets/bag_footage/sanfer_tunnel")


def main() -> int:
    if not BAG.exists():
        print(f"missing bag: {BAG}", file=sys.stderr)
        return 2

    OUT_BUNDLE.mkdir(parents=True, exist_ok=True)
    OUT_DEMO.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    with AnyReader([BAG]) as reader:
        conns = [c for c in reader.connections if c.topic == TOPIC]
        if not conns:
            print(f"topic {TOPIC} not in bag; available:", file=sys.stderr)
            for c in reader.connections:
                print(f"  {c.topic}  {c.msgtype}  n={c.msgcount}", file=sys.stderr)
            return 3

        start_ns = int(reader.start_time)
        end_ns = int(reader.end_time)
        dur_s = (end_ns - start_ns) / 1e9
        targets_ns = np.linspace(start_ns, end_ns, N_FRAMES, dtype=np.int64)
        print(f"bag {BAG.name}  dur={dur_s:.1f}s  topic_conns={len(conns)}  "
              f"total_msgs={sum(c.msgcount for c in conns)}  targets={N_FRAMES}")

        next_i = 0
        written = 0
        last_progress = time.time()

        for conn, t_ns, raw in reader.messages(connections=conns):
            if next_i >= len(targets_ns):
                break
            if t_ns < targets_ns[next_i]:
                if time.time() - last_progress > 30:
                    elapsed_bag_s = (t_ns - start_ns) / 1e9
                    wall = time.time() - t0
                    print(f"  ... bag t={elapsed_bag_s:6.1f}s / {dur_s:.0f}s "
                          f"wall={wall:5.0f}s  written={written}/{N_FRAMES}")
                    last_progress = time.time()
                continue

            try:
                msg = reader.deserialize(raw, conn.msgtype)
            except Exception as e:
                print(f"  deserialize fail @ t={t_ns}: {e}", file=sys.stderr)
                next_i += 1
                continue

            buf = np.frombuffer(bytes(msg.data), dtype=np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if img is None:
                next_i += 1
                continue

            t_rel_s = int(round((t_ns - start_ns) / 1e9))
            name = f"frame_{t_rel_s:04d}s.jpg"
            out_a = OUT_BUNDLE / name
            cv2.imwrite(str(out_a), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
            shutil.copy2(out_a, OUT_DEMO / name)
            written += 1
            wall = time.time() - t0
            print(f"  [{written:2d}/{N_FRAMES}] t={t_rel_s:4d}s  "
                  f"{img.shape[1]}x{img.shape[0]}  "
                  f"jpg={out_a.stat().st_size//1024}KB  wall={wall:.0f}s")
            next_i += 1

    wall = time.time() - t0
    print(f"done. wrote {written} frames in {wall:.0f}s -> {OUT_BUNDLE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
