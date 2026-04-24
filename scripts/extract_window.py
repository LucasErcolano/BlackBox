# SPDX-License-Identifier: MIT
"""Extract a time window of frames from 5 cameras in a ROS1 bag.

Streams once through [start_ns, stop_ns), samples N frames per camera evenly spaced,
decodes with cv2.imdecode, resizes to 800x600, saves as PNG.
"""
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


def extract(bag_path: Path, out_dir: Path, window_start_s: float, window_len_s: float, n_per_cam: int = 8, thumb: tuple[int, int] = (800, 600)) -> dict:
    t0 = time.time()
    out_dir.mkdir(parents=True, exist_ok=True)
    # ingest all frames of each cam in window, then downsample
    per_cam: dict[str, list[tuple[int, bytes]]] = {t: [] for t in CAM_TOPICS}

    with AnyReader([bag_path]) as reader:
        bag_start = reader.start_time
        start_ns = int(bag_start + window_start_s * 1e9)
        stop_ns = int(start_ns + window_len_s * 1e9)
        wanted_conns = [c for c in reader.connections if c.topic in CAM_TOPICS]
        found = {c.topic for c in wanted_conns}
        missing = set(CAM_TOPICS) - found
        if missing:
            print(f"[extract] WARN missing topics: {missing}", flush=True)

        for conn, t_ns, raw in reader.messages(connections=wanted_conns, start=start_ns, stop=stop_ns):
            msg = reader.deserialize(raw, conn.msgtype)
            per_cam[conn.topic].append((int(t_ns), bytes(msg.data)))

    # Sample evenly and decode
    saved: dict[str, list[dict]] = {}
    for topic in CAM_TOPICS:
        frames = per_cam.get(topic, [])
        if not frames:
            saved[topic] = []
            continue
        frames.sort(key=lambda x: x[0])
        n = len(frames)
        if n <= n_per_cam:
            sample = frames
        else:
            idxs = np.linspace(0, n - 1, n_per_cam).astype(int)
            sample = [frames[i] for i in idxs]

        role = ROLE.get(topic, topic.replace("/", "_"))
        saved[topic] = []
        for i, (ts, buf) in enumerate(sample):
            arr = np.frombuffer(buf, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                print(f"[extract] decode failed {topic} i={i}", flush=True)
                continue
            h, w = img.shape[:2]
            img_t = cv2.resize(img, thumb, interpolation=cv2.INTER_AREA) if (w, h) != thumb else img
            fname = f"{role}_{i:02d}_t{ts}.png"
            fpath = out_dir / fname
            cv2.imwrite(str(fpath), img_t)
            saved[topic].append({"t_ns": ts, "file": fname, "orig_hw": [h, w]})

    # Build preview 5-up montage: first frame per camera
    tiles = []
    for topic in CAM_TOPICS:
        meta = saved.get(topic, [])
        if meta:
            img = cv2.imread(str(out_dir / meta[0]["file"]))
        else:
            img = np.zeros((600, 800, 3), dtype=np.uint8)
            cv2.putText(img, f"{ROLE.get(topic, topic)} MISSING", (50, 300),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
        cv2.putText(img, ROLE.get(topic, topic), (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        tiles.append(img)
    # Pad to 6 for 3x2 grid
    while len(tiles) < 6:
        tiles.append(np.zeros_like(tiles[0]))
    row1 = np.hstack(tiles[:3])
    row2 = np.hstack(tiles[3:6])
    montage = np.vstack([row1, row2])
    cv2.imwrite(str(out_dir / "preview_5up.png"), montage)

    manifest = {
        "bag": str(bag_path),
        "window_start_s": window_start_s,
        "window_len_s": window_len_s,
        "n_per_cam_requested": n_per_cam,
        "frames_per_cam": {t: len(saved.get(t, [])) for t in CAM_TOPICS},
        "saved": {t: saved.get(t, []) for t in CAM_TOPICS},
        "wall_s": round(time.time() - t0, 1),
    }
    (out_dir / "frames_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[extract] done in {manifest['wall_s']}s  per_cam={manifest['frames_per_cam']}", flush=True)
    return manifest


if __name__ == "__main__":
    bag = Path(sys.argv[1])
    out = Path(sys.argv[2])
    ws = float(sys.argv[3]) if len(sys.argv) > 3 else 470.0
    wl = float(sys.argv[4]) if len(sys.argv) > 4 else 30.0
    n = int(sys.argv[5]) if len(sys.argv) > 5 else 8
    extract(bag, out, ws, wl, n)
