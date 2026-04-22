"""Extract hi-res frames from specific cameras in a specific window (hero material)."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import cv2
import numpy as np
from rosbags.highlevel import AnyReader


def run(bag_path: Path, out_dir: Path, cameras: list[str], win_start_s: float, win_len_s: float, n_per_cam: int = 10):
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = {c: [] for c in cameras}
    with AnyReader([bag_path]) as reader:
        bag_start = reader.start_time
        start_ns = int(bag_start + win_start_s * 1e9)
        stop_ns = int(start_ns + win_len_s * 1e9)
        wanted = [c for c in reader.connections if c.topic in cameras]
        per_cam_raw = {c: [] for c in cameras}
        for conn, t_ns, raw in reader.messages(connections=wanted, start=start_ns, stop=stop_ns):
            msg = reader.deserialize(raw, conn.msgtype)
            per_cam_raw[conn.topic].append((int(t_ns), bytes(msg.data)))
        for topic, frames in per_cam_raw.items():
            frames.sort(key=lambda x: x[0])
            n = len(frames)
            if n == 0: continue
            idxs = np.linspace(0, n - 1, min(n_per_cam, n)).astype(int)
            for i, k in enumerate(idxs):
                ts, buf = frames[k]
                arr = np.frombuffer(buf, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is None: continue
                # Cap at ~3.75 MP = 2500x1500 region (Anthropic hires max useful)
                h, w = img.shape[:2]
                max_side = 1920
                if max(w, h) > max_side:
                    scale = max_side / max(w, h)
                    img = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_AREA)
                role = topic.replace("/", "_").strip("_")
                fname = f"{role}_{i:02d}_t{ts}.png"
                cv2.imwrite(str(out_dir / fname), img)
                saved[topic].append({"t_ns": ts, "file": fname, "hw": list(img.shape[:2])})
    (out_dir / "hires_manifest.json").write_text(json.dumps({
        "bag": str(bag_path),
        "win_start_s": win_start_s,
        "win_len_s": win_len_s,
        "cameras": cameras,
        "saved": saved,
    }, indent=2))
    total = sum(len(v) for v in saved.values())
    print(f"[hires] saved {total} frames  cams={ {c: len(v) for c,v in saved.items()} }")


if __name__ == "__main__":
    bag = Path(sys.argv[1])
    out = Path(sys.argv[2])
    cams = sys.argv[3].split(",")
    ws = float(sys.argv[4])
    wl = float(sys.argv[5])
    n = int(sys.argv[6]) if len(sys.argv) > 6 else 10
    run(bag, out, cams, ws, wl, n)
