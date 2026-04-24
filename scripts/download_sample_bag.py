# SPDX-License-Identifier: MIT
"""Fetch (or synthesize) a small rosbag2 sample for Black Box dev/tests.

Strategy:
  1. If ``data/bags/sample/`` already contains a bag, do nothing.
  2. Try a small public rosbag2 download.
  3. On any failure, synthesize a tiny rosbag2 with two fake image topics
     + an odometry topic using rosbags' writer API. This is enough to
     validate the ingestion parser.

Usage:
    python scripts/download_sample_bag.py
"""

from __future__ import annotations

import math
import shutil
import sys
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "data" / "bags" / "sample"


def _already_has_bag(d: Path) -> Path | None:
    if not d.exists():
        return None
    # Rosbag2 layout: directory with metadata.yaml + .db3/.mcap
    if (d / "metadata.yaml").exists():
        return d
    # Raw .db3 / .mcap
    for p in d.iterdir():
        if p.suffix in (".db3", ".mcap", ".bag"):
            return d
    return None


def _try_download() -> Path | None:
    """Attempt to grab a small known-good rosbag2 sample. Returns bag dir or None."""
    # Most small public rosbag2 samples ship as directories with metadata.yaml,
    # which is awkward to fetch as a single file. We attempt a single-file .db3
    # download; if it works we treat it as a ROS2 bag via the file path directly
    # (AnyReader accepts directories; most .db3 blobs need metadata).
    # In practice this branch is unreliable, so we fall through to synthesis.
    candidates = [
        "https://github.com/ros2/rosbag2/raw/humble/rosbag2/test/rosbag2/resources/test.db3",
    ]
    for url in candidates:
        try:
            target = SAMPLE_DIR / Path(url).name
            SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
            print(f"[download] trying {url}")
            urllib.request.urlretrieve(url, target)
            if target.stat().st_size > 1024:
                print(f"[download] got {target} ({target.stat().st_size} bytes)")
                return SAMPLE_DIR
        except Exception as exc:  # noqa: BLE001
            print(f"[download] failed: {exc}")
            continue
    return None


def _synthesize(out_dir: Path) -> Path:
    """Generate a tiny synthetic rosbag2 with 2 image topics + odom."""
    from rosbags.rosbag2 import Writer
    from rosbags.typesys import Stores, get_typestore

    out_dir.mkdir(parents=True, exist_ok=True)
    bag_path = out_dir / "synthetic"
    if bag_path.exists():
        shutil.rmtree(bag_path)

    ts = get_typestore(Stores.ROS2_HUMBLE)

    Image = ts.types["sensor_msgs/msg/Image"]
    Header = ts.types["std_msgs/msg/Header"]
    Time = ts.types["builtin_interfaces/msg/Time"]
    Odometry = ts.types["nav_msgs/msg/Odometry"]
    PoseWithCovariance = ts.types["geometry_msgs/msg/PoseWithCovariance"]
    TwistWithCovariance = ts.types["geometry_msgs/msg/TwistWithCovariance"]
    Pose = ts.types["geometry_msgs/msg/Pose"]
    Twist = ts.types["geometry_msgs/msg/Twist"]
    Point = ts.types["geometry_msgs/msg/Point"]
    Quaternion = ts.types["geometry_msgs/msg/Quaternion"]
    Vector3 = ts.types["geometry_msgs/msg/Vector3"]

    def _make_image(topic_seed: int, frame_idx: int, h: int = 120, w: int = 160) -> bytes:
        rng = np.random.default_rng(topic_seed * 1000 + frame_idx)
        arr = (rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8))
        # simple moving stripe for interpretability
        x = (frame_idx * 8) % w
        arr[:, x : min(w, x + 10), :] = 255
        return arr.tobytes()

    def _stamp(t_ns: int) -> object:
        return Time(sec=t_ns // 1_000_000_000, nanosec=t_ns % 1_000_000_000)

    with Writer(bag_path, version=9) as writer:
        cam_conns = []
        for i, topic in enumerate(("/camera_front/image_raw", "/camera_rear/image_raw")):
            cam_conns.append(
                (
                    topic,
                    writer.add_connection(topic, Image.__msgtype__, typestore=ts),
                    i,
                )
            )
        odom_conn = writer.add_connection("/odom", Odometry.__msgtype__, typestore=ts)

        n_frames = 20  # 2 Hz for 10 s
        start_ns = 1_700_000_000 * 1_000_000_000
        for k in range(n_frames):
            t_ns = start_ns + int(k * 0.5 * 1e9)
            for topic, conn, seed in cam_conns:
                h, w = 120, 160
                header = Header(stamp=_stamp(t_ns), frame_id=topic)
                img = Image(
                    header=header,
                    height=h,
                    width=w,
                    encoding="rgb8",
                    is_bigendian=0,
                    step=w * 3,
                    data=np.frombuffer(_make_image(seed, k, h, w), dtype=np.uint8),
                )
                writer.write(conn, t_ns, ts.serialize_cdr(img, Image.__msgtype__))

        # odom @ 20 Hz
        odom_n = 200
        for k in range(odom_n):
            t_ns = start_ns + int(k * 0.05 * 1e9)
            theta = k * 0.05
            pose = Pose(
                position=Point(x=math.cos(theta), y=math.sin(theta), z=0.0),
                orientation=Quaternion(x=0.0, y=0.0, z=math.sin(theta / 2), w=math.cos(theta / 2)),
            )
            twist = Twist(
                linear=Vector3(x=1.0, y=0.0, z=0.0),
                angular=Vector3(x=0.0, y=0.0, z=0.5),
            )
            cov = np.zeros(36, dtype=np.float64)
            odom = Odometry(
                header=Header(stamp=_stamp(t_ns), frame_id="odom"),
                child_frame_id="base_link",
                pose=PoseWithCovariance(pose=pose, covariance=cov),
                twist=TwistWithCovariance(twist=twist, covariance=cov),
            )
            writer.write(odom_conn, t_ns, ts.serialize_cdr(odom, Odometry.__msgtype__))

    print(f"[synth] wrote synthetic bag: {bag_path}")
    return bag_path


def ensure_sample_bag() -> Path:
    existing = _already_has_bag(SAMPLE_DIR / "synthetic") or _already_has_bag(SAMPLE_DIR)
    if existing:
        print(f"[skip] sample already present at: {existing}")
        return existing

    # Try download, fall back to synthesis
    # (Disabled by default since known URLs are unreliable for MVP.)
    # Uncomment to try the real download first:
    # fetched = _try_download()
    # if fetched:
    #     return fetched

    return _synthesize(SAMPLE_DIR)


def main() -> int:
    path = ensure_sample_bag()
    print(f"SAMPLE_BAG={path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
