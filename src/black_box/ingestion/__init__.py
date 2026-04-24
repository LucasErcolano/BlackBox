# SPDX-License-Identifier: MIT
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
from .session import (
    SessionAssets,
    discover_session_assets,
    discover_session_bags,
    describe_session,
)
from .frame_sampler import sample_frames
from .manifest import (
    Manifest,
    TopicInfo,
    build_manifest,
    manifest_to_prompt_block,
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
    "SessionAssets",
    "discover_session_assets",
    "discover_session_bags",
    "describe_session",
    "sample_frames",
    "Manifest",
    "TopicInfo",
    "build_manifest",
    "manifest_to_prompt_block",
]
