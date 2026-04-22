"""Ingestion layer: bag -> typed data -> renderable payloads."""

from .rosbag_reader import (
    BagData,
    Frame,
    TimeSeries,
    load_bag,
    sync_frames,
)
from .render import (
    frames_at,
    synced_grid,
    plot_telemetry,
    to_b64,
    thumb,
)
from .lidar import (
    LidarScan,
    decode_laserscan,
    decode_pointcloud2,
    top_down_render,
)

__all__ = [
    "BagData",
    "Frame",
    "TimeSeries",
    "LidarScan",
    "load_bag",
    "sync_frames",
    "frames_at",
    "synced_grid",
    "plot_telemetry",
    "to_b64",
    "thumb",
    "decode_laserscan",
    "decode_pointcloud2",
    "top_down_render",
]
