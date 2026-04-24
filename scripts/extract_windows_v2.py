# SPDX-License-Identifier: MIT
"""v2 extractor: 3 windows (start/middle/end) × 20s × ~1 fps per cam → 20 frames/cam/window."""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from rosbags.highlevel import AnyReader


CAM_TOPICS = [
    "/cam1/image_raw/compressed",
    "/cam3/image_raw/compressed",
    "/cam4/image_raw/compressed",
    "/cam5/image_raw/compressed",
    "/cam6/image_raw/compressed",
]

ROLE = {
    "/cam1/image_raw/compressed": "front_left",
    "/cam5/image_raw/compressed": "front_right",
    "/cam6/image_raw/compressed": "right",
    "/cam4/image_raw/compressed": "rear",
    "/cam3/image_raw/compressed": "left",
}


def sample_window(reader, bag_start_ns, bag_end_ns, win_start_s, win_len_s, frames_per_cam):
    start_ns = int(bag_start_ns + win_start_s * 1e9)
    stop_ns = int(min(bag_end_ns, start_ns + win_len_s * 1e9))
    wanted = [c for c in reader.connections if c.topic in CAM_TOPICS]
    per_cam = {t: [] for t in CAM_TOPICS}
    for conn, t_ns, raw in reader.messages(connections=wanted, start=start_ns, stop=stop_ns):
        msg = reader.deserialize(raw, conn.msgtype)
        per_cam[conn.topic].append((int(t_ns), bytes(msg.data)))
    sampled = {}
    for topic, frames in per_cam.items():
        frames.sort(key=lambda x: x[0])
        n = len(frames)
        if n == 0:
            sampled[topic] = []
            continue
        idxs = np.linspace(0, n - 1, min(frames_per_cam, n)).astype(int)
        sampled[topic] = [frames[i] for i in idxs]
    return sampled, start_ns, stop_ns


def save_window(sampled, start_ns, stop_ns, out_dir, win_name, thumb_big=(800, 600), thumb_small=(400, 300)):
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = {}
    for topic in CAM_TOPICS:
        role = ROLE[topic]
        saved[topic] = []
        for i, (ts, buf) in enumerate(sampled.get(topic, [])):
            arr = np.frombuffer(buf, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                continue
            big = cv2.resize(img, thumb_big, interpolation=cv2.INTER_AREA)
            small = cv2.resize(img, thumb_small, interpolation=cv2.INTER_AREA)
            fb = f"{win_name}__{role}_{i:02d}_t{ts}.png"
            fs = f"{win_name}__{role}_{i:02d}_t{ts}_small.png"
            cv2.imwrite(str(out_dir / fb), big)
            cv2.imwrite(str(out_dir / fs), small)
            saved[topic].append({"t_ns": ts, "file_big": fb, "file_small": fs})
    # Preview montage: first frame per cam (big)
    tiles = []
    for topic in CAM_TOPICS:
        meta = saved.get(topic, [])
        if meta:
            img = cv2.imread(str(out_dir / meta[0]["file_big"]))
        else:
            img = np.zeros((600, 800, 3), dtype=np.uint8)
            cv2.putText(img, f"{ROLE[topic]} MISSING", (50, 300),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        cv2.putText(img, ROLE[topic], (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        tiles.append(img)
    while len(tiles) < 6:
        tiles.append(np.zeros_like(tiles[0]))
    montage = np.vstack([np.hstack(tiles[:3]), np.hstack(tiles[3:6])])
    cv2.imwrite(str(out_dir / f"{win_name}__preview_5up.png"), montage)
    return saved, {"start_ns": start_ns, "stop_ns": stop_ns, "saved": saved}


def run(bag_path: Path, out_dir: Path, frames_per_cam: int = 20, win_len_s: float = 20.0):
    t0 = time.time()
    out_dir.mkdir(parents=True, exist_ok=True)
    with AnyReader([bag_path]) as reader:
        bag_start = reader.start_time
        bag_end = reader.end_time
        duration_s = (bag_end - bag_start) / 1e9

        # 3 windows: start / middle / end (with margins)
        margin = 15.0  # skip first/last 15s
        win_defs = {
            "start": margin,
            "middle": max(margin, duration_s / 2 - win_len_s / 2),
            "end": max(margin, duration_s - margin - win_len_s),
        }
        # Ensure strictly increasing non-overlapping where possible
        all_windows = {}
        for name, ws in win_defs.items():
            print(f"[extract_v2] {name}: [{ws:.1f}s, {ws+win_len_s:.1f}s]", flush=True)
            sampled, start_ns, stop_ns = sample_window(reader, bag_start, bag_end, ws, win_len_s, frames_per_cam)
            saved, meta = save_window(sampled, start_ns, stop_ns, out_dir, name)
            all_windows[name] = {
                "start_s": ws,
                "stop_s": ws + win_len_s,
                "start_ns": start_ns,
                "stop_ns": stop_ns,
                "frames_per_cam": {t: len(saved.get(t, [])) for t in CAM_TOPICS},
                "saved": saved,
            }

    manifest = {
        "bag": str(bag_path),
        "duration_s": duration_s,
        "frames_per_cam_per_window": frames_per_cam,
        "win_len_s": win_len_s,
        "windows": all_windows,
        "wall_s": round(time.time() - t0, 1),
    }
    (out_dir / "windows_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[extract_v2] done in {manifest['wall_s']}s  windows={list(all_windows.keys())}", flush=True)
    return manifest


if __name__ == "__main__":
    bag = Path(sys.argv[1])
    out = Path(sys.argv[2])
    fpc = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    wlen = float(sys.argv[4]) if len(sys.argv) > 4 else 20.0
    run(bag, out, fpc, wlen)
