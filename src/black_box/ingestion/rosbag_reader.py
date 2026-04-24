# SPDX-License-Identifier: MIT
"""Read ROS1/ROS2 bags with the pure-python `rosbags` library.

Exposes a small typed surface (BagData, Frame, TimeSeries) plus
`load_bag` and `sync_frames` used by the synthesis + render pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np

try:  # optional — only needed for CompressedImage decode
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore

from rosbags.highlevel import AnyReader

from .lidar import LidarScan, decode_laserscan, decode_pointcloud2


# -------- types --------------------------------------------------------------


@dataclass
class Frame:
    t_ns: int
    image: np.ndarray  # HxWx3 BGR uint8
    topic: str


@dataclass
class TimeSeries:
    t_ns: np.ndarray
    values: np.ndarray  # (N,) or (N, D)
    fields: list[str] = field(default_factory=list)


@dataclass
class BagData:
    cameras: dict[str, list[Frame]]
    telemetry: dict[str, "TimeSeries"]
    metadata: dict
    lidar: dict[str, list[LidarScan]] = field(default_factory=dict)

    def sync_frames(
        self, target_hz: float = 2.0, tolerance_ms: int = 50
    ) -> list[dict]:
        return sync_frames(self, target_hz=target_hz, tolerance_ms=tolerance_ms)


# -------- topic detection ----------------------------------------------------


_IMAGE_MSGTYPES = {"sensor_msgs/msg/Image", "sensor_msgs/Image"}
_COMPRESSED_MSGTYPES = {
    "sensor_msgs/msg/CompressedImage",
    "sensor_msgs/CompressedImage",
}
_POINTCLOUD_MSGTYPES = {
    "sensor_msgs/msg/PointCloud2",
    "sensor_msgs/PointCloud2",
}
_LASERSCAN_MSGTYPES = {
    "sensor_msgs/msg/LaserScan",
    "sensor_msgs/LaserScan",
}


def _is_lidar_msgtype(msgtype: str) -> bool:
    return msgtype in _POINTCLOUD_MSGTYPES or msgtype in _LASERSCAN_MSGTYPES

_TELEMETRY_REGEX = re.compile(
    r"(odom|imu|cmd_vel|pose|twist|gps|fix|joint_states|pwm|battery)",
    re.IGNORECASE,
)


def _is_camera_msgtype(msgtype: str) -> bool:
    return msgtype in _IMAGE_MSGTYPES or msgtype in _COMPRESSED_MSGTYPES


# -------- image decoding -----------------------------------------------------


def _decode_image(msg: Any) -> np.ndarray | None:
    """Decode a sensor_msgs/Image into HxWx3 BGR uint8."""
    encoding = getattr(msg, "encoding", "").lower()
    h, w = int(msg.height), int(msg.width)
    data = np.frombuffer(bytes(msg.data), dtype=np.uint8)
    if encoding in ("rgb8",):
        arr = data.reshape(h, w, 3)
        return arr[:, :, ::-1].copy()  # -> BGR
    if encoding in ("bgr8",):
        return data.reshape(h, w, 3).copy()
    if encoding in ("mono8", "8uc1"):
        gray = data.reshape(h, w)
        return np.stack([gray] * 3, axis=-1)
    if encoding in ("rgba8",):
        arr = data.reshape(h, w, 4)[:, :, :3]
        return arr[:, :, ::-1].copy()
    if encoding in ("bgra8",):
        return data.reshape(h, w, 4)[:, :, :3].copy()
    if encoding in ("yuv422", "yuv422_yuy2", "uyvy"):
        if cv2 is None:
            return None
        yuv = data.reshape(h, w, 2)
        try:
            return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_YUY2)
        except Exception:
            return None
    # Fallback: try to reshape as 3-channel
    if data.size == h * w * 3:
        return data.reshape(h, w, 3).copy()
    if data.size == h * w:
        gray = data.reshape(h, w)
        return np.stack([gray] * 3, axis=-1)
    return None


def _decode_compressed(msg: Any) -> np.ndarray | None:
    if cv2 is None:
        return None
    buf = np.frombuffer(bytes(msg.data), dtype=np.uint8)
    try:
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


# -------- telemetry extraction ----------------------------------------------


def _extract_scalar_vector(msg: Any) -> tuple[list[str], list[float]] | None:
    """Best-effort: flatten common telemetry messages to (fields, values)."""
    t = getattr(msg, "__msgtype__", "")
    try:
        if t.endswith("/Imu"):
            ang = msg.angular_velocity
            lin = msg.linear_acceleration
            o = msg.orientation
            return (
                ["ang_x", "ang_y", "ang_z", "lin_x", "lin_y", "lin_z", "ox", "oy", "oz", "ow"],
                [ang.x, ang.y, ang.z, lin.x, lin.y, lin.z, o.x, o.y, o.z, o.w],
            )
        if t.endswith("/Odometry"):
            p = msg.pose.pose.position
            tw = msg.twist.twist
            return (
                ["px", "py", "pz", "lin_x", "lin_y", "lin_z", "ang_z"],
                [p.x, p.y, p.z, tw.linear.x, tw.linear.y, tw.linear.z, tw.angular.z],
            )
        if t.endswith("/Twist") or t.endswith("/TwistStamped"):
            tw = msg.twist if hasattr(msg, "twist") else msg
            return (
                ["lin_x", "lin_y", "lin_z", "ang_x", "ang_y", "ang_z"],
                [tw.linear.x, tw.linear.y, tw.linear.z, tw.angular.x, tw.angular.y, tw.angular.z],
            )
        if t.endswith("/PoseStamped") or t.endswith("/Pose"):
            p = msg.pose.position if hasattr(msg, "pose") else msg.position
            return (["px", "py", "pz"], [p.x, p.y, p.z])
        if t.endswith("/NavSatFix"):
            return (
                ["lat", "lon", "alt"],
                [msg.latitude, msg.longitude, msg.altitude],
            )
        if t.endswith("/JointState"):
            names = list(msg.name) if len(msg.name) else [f"j{i}" for i in range(len(msg.position))]
            return (list(names), list(msg.position))
        # Float32/Float64
        if t.endswith("/Float32") or t.endswith("/Float64"):
            return (["data"], [float(msg.data)])
    except Exception:
        return None
    return None


# -------- main loader --------------------------------------------------------


def _auto_topics(
    reader: AnyReader,
    camera_topics: list[str] | None,
    telemetry_topics: list[str] | None,
    lidar_topics: list[str] | None = None,
) -> tuple[set[str], set[str], set[str]]:
    cams: set[str] = set()
    tele: set[str] = set()
    lid: set[str] = set()
    for conn in reader.connections:
        topic = conn.topic
        msgtype = conn.msgtype
        if camera_topics is not None:
            if topic in camera_topics:
                cams.add(topic)
        else:
            if _is_camera_msgtype(msgtype):
                cams.add(topic)
        if lidar_topics is not None:
            if topic in lidar_topics:
                lid.add(topic)
        else:
            if _is_lidar_msgtype(msgtype):
                lid.add(topic)
        if telemetry_topics is not None:
            if topic in telemetry_topics:
                tele.add(topic)
        else:
            if (
                _TELEMETRY_REGEX.search(topic)
                and not _is_camera_msgtype(msgtype)
                and not _is_lidar_msgtype(msgtype)
            ):
                tele.add(topic)
    return cams, tele, lid


def load_bag(
    path: str | Path,
    camera_topics: list[str] | None = None,
    telemetry_topics: list[str] | None = None,
    lidar_topics: list[str] | None = None,
    max_frames_per_cam: int = 300,
    max_scans_per_lidar: int = 600,
) -> BagData:
    path = Path(path)
    # AnyReader wants a sequence of paths
    paths: list[Path]
    if path.is_dir() or path.suffix in (".db3", ".mcap"):
        paths = [path]
    else:
        paths = [path]

    cameras: dict[str, list[Frame]] = {}
    lidar: dict[str, list[LidarScan]] = {}
    # Telemetry accumulators: topic -> (list[t_ns], list[row], fields)
    tele_acc: dict[str, tuple[list[int], list[list[float]], list[str]]] = {}

    with AnyReader(paths) as reader:
        cam_set, tele_set, lid_set = _auto_topics(
            reader, camera_topics, telemetry_topics, lidar_topics
        )
        cam_counts: dict[str, int] = {t: 0 for t in cam_set}
        lid_counts: dict[str, int] = {t: 0 for t in lid_set}

        # Filter connections we care about
        wanted = [
            c
            for c in reader.connections
            if c.topic in cam_set or c.topic in tele_set or c.topic in lid_set
        ]

        for conn, t_ns, raw in reader.messages(connections=wanted):
            topic = conn.topic
            if topic in cam_set:
                if cam_counts[topic] >= max_frames_per_cam:
                    continue
                try:
                    msg = reader.deserialize(raw, conn.msgtype)
                except Exception:
                    continue
                if conn.msgtype in _COMPRESSED_MSGTYPES:
                    img = _decode_compressed(msg)
                else:
                    img = _decode_image(msg)
                if img is None:
                    continue
                cameras.setdefault(topic, []).append(Frame(t_ns=int(t_ns), image=img, topic=topic))
                cam_counts[topic] += 1
            elif topic in lid_set:
                if lid_counts[topic] >= max_scans_per_lidar:
                    continue
                try:
                    msg = reader.deserialize(raw, conn.msgtype)
                except Exception:
                    continue
                if conn.msgtype in _POINTCLOUD_MSGTYPES:
                    scan = decode_pointcloud2(msg)
                else:
                    scan = decode_laserscan(msg)
                if scan is None:
                    continue
                scan.topic = topic
                if scan.t_ns == 0:
                    scan.t_ns = int(t_ns)
                lidar.setdefault(topic, []).append(scan)
                lid_counts[topic] += 1
            elif topic in tele_set:
                try:
                    msg = reader.deserialize(raw, conn.msgtype)
                except Exception:
                    continue
                sv = _extract_scalar_vector(msg)
                if sv is None:
                    continue
                fields_, vals = sv
                if topic not in tele_acc:
                    tele_acc[topic] = ([], [], fields_)
                acc_t, acc_v, acc_f = tele_acc[topic]
                # Pad/truncate to match registered width
                if len(vals) < len(acc_f):
                    vals = list(vals) + [0.0] * (len(acc_f) - len(vals))
                elif len(vals) > len(acc_f):
                    vals = list(vals[: len(acc_f)])
                acc_t.append(int(t_ns))
                acc_v.append(list(vals))

        start_ns = int(reader.start_time)
        end_ns = int(reader.end_time)
        duration_s = (end_ns - start_ns) / 1e9
        topics_list = [
            {"topic": c.topic, "msgtype": c.msgtype, "msgcount": c.msgcount}
            for c in reader.connections
        ]

    # Sort frames
    for topic in cameras:
        cameras[topic].sort(key=lambda f: f.t_ns)
    for topic in lidar:
        lidar[topic].sort(key=lambda s: s.t_ns)

    telemetry: dict[str, TimeSeries] = {}
    for topic, (ts, vs, fs) in tele_acc.items():
        if not ts:
            continue
        arr = np.asarray(vs, dtype=float)
        if arr.ndim == 2 and arr.shape[1] == 1:
            arr = arr[:, 0]
        telemetry[topic] = TimeSeries(
            t_ns=np.asarray(ts, dtype=np.int64), values=arr, fields=fs
        )

    metadata = {
        "duration_s": duration_s,
        "start_ns": start_ns,
        "end_ns": end_ns,
        "topics": topics_list,
    }
    return BagData(
        cameras=cameras, telemetry=telemetry, metadata=metadata, lidar=lidar
    )


# -------- synchronization ----------------------------------------------------


def _nearest_index(sorted_ts: np.ndarray, target: int) -> int:
    i = int(np.searchsorted(sorted_ts, target))
    if i <= 0:
        return 0
    if i >= len(sorted_ts):
        return len(sorted_ts) - 1
    before = sorted_ts[i - 1]
    after = sorted_ts[i]
    return i - 1 if abs(before - target) <= abs(after - target) else i


def sync_frames(
    bag: BagData, target_hz: float = 2.0, tolerance_ms: int = 50
) -> list[dict]:
    if not bag.cameras:
        return []
    tol_ns = int(tolerance_ms * 1_000_000)
    start = bag.metadata["start_ns"]
    end = bag.metadata["end_ns"]
    step = int(1e9 / max(target_hz, 1e-6))
    if step <= 0:
        return []

    cam_ts = {topic: np.asarray([f.t_ns for f in frames], dtype=np.int64)
              for topic, frames in bag.cameras.items()}

    out: list[dict] = []
    t = start
    while t <= end:
        window = {}
        ok = True
        for topic, frames in bag.cameras.items():
            ts = cam_ts[topic]
            if len(ts) == 0:
                ok = False
                break
            idx = _nearest_index(ts, t)
            if abs(int(ts[idx]) - t) > tol_ns:
                ok = False
                break
            window[topic] = frames[idx].image
        if ok and window:
            out.append({"t_ns": int(t), "frames": window})
        t += step
    return out
