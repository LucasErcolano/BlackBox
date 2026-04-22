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

__all__ = [
    "BagData",
    "Frame",
    "TimeSeries",
    "load_bag",
    "sync_frames",
    "frames_at",
    "synced_grid",
    "plot_telemetry",
    "to_b64",
    "thumb",
]
