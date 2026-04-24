# SPDX-License-Identifier: MIT
"""LIDAR ingestion — PointCloud2 + LaserScan decoders and top-down rendering.

Uses `rosbags` deserialized messages. No ROS runtime. Outputs numpy arrays
plus PIL renderings ready to pass to Claude vision.

Design notes:
- PointCloud2 data is a packed byte buffer; we walk fields by offset/datatype
  rather than relying on sensor_msgs_py (which requires the ROS runtime).
- We downsample aggressively before rendering — 3M-point clouds are too
  expensive to ship whole and the agent only needs structure, not density.
- Top-down projection collapses Z (or uses Z as color) to produce a single
  image the model can read. For boats, water-surface scans are mostly
  planar so 2D works; for terrestrial LIDAR we still get driveable-region
  structure.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image


# PointField datatypes (sensor_msgs/msg/PointField)
_DTYPE_MAP = {
    1: (np.int8, 1),
    2: (np.uint8, 1),
    3: (np.int16, 2),
    4: (np.uint16, 2),
    5: (np.int32, 4),
    6: (np.uint32, 4),
    7: (np.float32, 4),
    8: (np.float64, 8),
}


@dataclass
class LidarScan:
    """Unified scan representation for both PointCloud2 and LaserScan."""

    t_ns: int
    topic: str
    points_xyz: np.ndarray  # (N, 3) float32, meters in sensor frame
    intensity: np.ndarray | None = None  # (N,) float32
    source: str = "pointcloud2"  # or "laserscan"
    meta: dict = field(default_factory=dict)


# -------- PointCloud2 decode -------------------------------------------------


def decode_pointcloud2(msg: Any, max_points: int = 50_000) -> LidarScan | None:
    """Decode a sensor_msgs/msg/PointCloud2 into an XYZ(+I) scan.

    Downsamples uniformly to at most `max_points` points.
    """
    try:
        fields = list(msg.fields)
        point_step = int(msg.point_step)
        width = int(msg.width)
        height = int(msg.height)
        data = bytes(msg.data)
    except AttributeError:
        return None

    n_points = width * height
    if n_points == 0 or not data:
        return None

    # Locate x/y/z/intensity field offsets
    off = {}
    for f in fields:
        name = getattr(f, "name", "")
        if name in ("x", "y", "z", "intensity"):
            off[name] = (
                int(getattr(f, "offset")),
                int(getattr(f, "datatype")),
            )

    if not all(k in off for k in ("x", "y", "z")):
        return None

    # Allocate
    xyz = np.empty((n_points, 3), dtype=np.float32)
    intensity = (
        np.empty(n_points, dtype=np.float32) if "intensity" in off else None
    )

    for i in range(n_points):
        base = i * point_step
        for j, axis in enumerate(("x", "y", "z")):
            o, dt = off[axis]
            np_dtype, size = _DTYPE_MAP.get(dt, (np.float32, 4))
            xyz[i, j] = np.frombuffer(
                data[base + o : base + o + size], dtype=np_dtype
            )[0]
        if intensity is not None:
            o, dt = off["intensity"]
            np_dtype, size = _DTYPE_MAP.get(dt, (np.float32, 4))
            intensity[i] = np.frombuffer(
                data[base + o : base + o + size], dtype=np_dtype
            )[0]

    # Strip NaN/inf (common in raw lidar frames)
    finite = np.isfinite(xyz).all(axis=1)
    xyz = xyz[finite]
    if intensity is not None:
        intensity = intensity[finite]

    # Uniform downsample
    if xyz.shape[0] > max_points:
        idx = np.linspace(0, xyz.shape[0] - 1, max_points, dtype=np.int64)
        xyz = xyz[idx]
        if intensity is not None:
            intensity = intensity[idx]

    t_ns = _header_stamp_ns(msg)
    return LidarScan(
        t_ns=t_ns,
        topic="",
        points_xyz=xyz,
        intensity=intensity,
        source="pointcloud2",
        meta={"width": width, "height": height, "n_points_raw": n_points},
    )


# -------- LaserScan decode ---------------------------------------------------


def decode_laserscan(msg: Any) -> LidarScan | None:
    """Decode a sensor_msgs/msg/LaserScan into an XYZ scan (z=0)."""
    try:
        angle_min = float(msg.angle_min)
        angle_inc = float(msg.angle_increment)
        ranges = np.asarray(msg.ranges, dtype=np.float32)
        range_min = float(msg.range_min)
        range_max = float(msg.range_max)
        intensities = (
            np.asarray(msg.intensities, dtype=np.float32)
            if len(getattr(msg, "intensities", [])) == len(ranges)
            else None
        )
    except AttributeError:
        return None

    if ranges.size == 0:
        return None

    angles = angle_min + np.arange(ranges.size, dtype=np.float32) * angle_inc
    valid = np.isfinite(ranges) & (ranges >= range_min) & (ranges <= range_max)
    r = ranges[valid]
    a = angles[valid]
    xyz = np.stack(
        [r * np.cos(a), r * np.sin(a), np.zeros_like(r)], axis=1
    ).astype(np.float32)
    intensity = intensities[valid] if intensities is not None else None

    t_ns = _header_stamp_ns(msg)
    return LidarScan(
        t_ns=t_ns,
        topic="",
        points_xyz=xyz,
        intensity=intensity,
        source="laserscan",
        meta={
            "n_rays_raw": int(ranges.size),
            "n_rays_valid": int(valid.sum()),
            "angle_min": angle_min,
            "angle_increment": angle_inc,
        },
    )


def _header_stamp_ns(msg: Any) -> int:
    try:
        h = msg.header.stamp
        return int(h.sec) * 1_000_000_000 + int(h.nanosec)
    except AttributeError:
        return 0


# -------- Top-down rendering -------------------------------------------------


def top_down_render(
    scan: LidarScan,
    extent_m: float = 50.0,
    image_size: int = 800,
    color_by: str = "z",
) -> Image.Image:
    """Render XYZ points into a top-down PNG for Claude vision.

    Args:
        extent_m: half-extent of the viewport in meters. Points outside dropped.
        image_size: output resolution (square).
        color_by: "z" (height, blue→red), "intensity", or "range".
    """
    xyz = scan.points_xyz
    if xyz.shape[0] == 0:
        return Image.new("RGB", (image_size, image_size), (10, 10, 10))

    x = xyz[:, 0]
    y = xyz[:, 1]
    z = xyz[:, 2]

    mask = (np.abs(x) <= extent_m) & (np.abs(y) <= extent_m)
    x, y, z = x[mask], y[mask], z[mask]
    intensity = scan.intensity[mask] if scan.intensity is not None else None

    # Map to pixel coords. Ego at center. +X = forward = up in image.
    px = ((y + extent_m) / (2 * extent_m) * (image_size - 1)).astype(np.int32)
    py = ((extent_m - x) / (2 * extent_m) * (image_size - 1)).astype(np.int32)

    # Color channel selection
    if color_by == "intensity" and intensity is not None and intensity.size:
        v = intensity
    elif color_by == "range":
        v = np.sqrt(x * x + y * y)
    else:
        v = z

    if v.size == 0:
        return Image.new("RGB", (image_size, image_size), (10, 10, 10))

    v_min, v_max = float(np.percentile(v, 2)), float(np.percentile(v, 98))
    if v_max <= v_min:
        v_max = v_min + 1e-6
    v_norm = np.clip((v - v_min) / (v_max - v_min), 0.0, 1.0)

    # Blue → cyan → yellow → red colormap, cheap lookup
    r = (np.clip(v_norm * 2 - 0.3, 0, 1) * 255).astype(np.uint8)
    g = (np.clip(1.0 - np.abs(v_norm * 2 - 1.0), 0, 1) * 255).astype(np.uint8)
    b = (np.clip(1.0 - v_norm * 2, 0, 1) * 255).astype(np.uint8)

    img = np.full((image_size, image_size, 3), 10, dtype=np.uint8)
    # Scatter points (no AA, acceptable for forensic glance)
    img[py, px, 0] = r
    img[py, px, 1] = g
    img[py, px, 2] = b

    # Ego marker
    c = image_size // 2
    img[c - 2 : c + 3, c - 2 : c + 3] = (255, 255, 255)

    # Range rings every 10 m (thin dark-grey)
    _draw_range_rings(img, extent_m, image_size, spacing_m=10.0)

    return Image.fromarray(img)


def _draw_range_rings(
    img: np.ndarray, extent_m: float, size: int, spacing_m: float
) -> None:
    c = size // 2
    px_per_m = (size - 1) / (2 * extent_m)
    for r_m in np.arange(spacing_m, extent_m + 1e-6, spacing_m):
        r_px = int(round(r_m * px_per_m))
        if r_px <= 0 or r_px >= c:
            continue
        theta = np.linspace(0, 2 * np.pi, max(64, r_px * 4))
        xs = (c + r_px * np.cos(theta)).astype(np.int32)
        ys = (c + r_px * np.sin(theta)).astype(np.int32)
        ok = (xs >= 0) & (xs < size) & (ys >= 0) & (ys < size)
        img[ys[ok], xs[ok]] = (60, 60, 60)
