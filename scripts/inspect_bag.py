# SPDX-License-Identifier: MIT
"""Inspect a ROS1 bag: topics, types, counts, duration. Emit manifest JSON."""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path
from collections import defaultdict

from rosbags.rosbag1 import Reader


def inspect(bag_path: Path, out_json: Path) -> dict:
    t0 = time.time()
    with Reader(bag_path) as r:
        counts: dict[str, int] = defaultdict(int)
        types: dict[str, str] = {}
        first_ns: dict[str, int] = {}
        last_ns: dict[str, int] = {}
        start_ns = r.start_time
        end_ns = r.end_time
        for c in r.connections:
            types[c.topic] = c.msgtype
        for conn, ts, _raw in r.messages():
            counts[conn.topic] += 1
            if conn.topic not in first_ns:
                first_ns[conn.topic] = ts
            last_ns[conn.topic] = ts

        duration_s = (end_ns - start_ns) / 1e9
        topics = []
        for t, n in sorted(counts.items()):
            dur = (last_ns[t] - first_ns[t]) / 1e9 if n > 1 else 0.0
            hz = n / dur if dur > 0 else 0.0
            topics.append({
                "topic": t,
                "msgtype": types.get(t, "?"),
                "count": n,
                "hz": round(hz, 2),
            })

    manifest = {
        "bag": str(bag_path),
        "start_ns": start_ns,
        "end_ns": end_ns,
        "duration_s": round(duration_s, 2),
        "topics": topics,
        "inspect_wall_s": round(time.time() - t0, 1),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    bag = Path(sys.argv[1])
    out = Path(sys.argv[2])
    m = inspect(bag, out)
    print(f"[inspect] duration={m['duration_s']:.1f}s topics={len(m['topics'])} wall={m['inspect_wall_s']}s")
    for t in m["topics"]:
        print(f"  {t['topic']:60s} {t['msgtype']:40s} n={t['count']:6d}  hz={t['hz']}")
