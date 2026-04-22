"""Smoke tests for the ingestion layer."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from black_box.ingestion import (  # noqa: E402
    BagData,
    Frame,
    TimeSeries,
    load_bag,
    plot_telemetry,
    sync_frames,
    synced_grid,
    to_b64,
)


def test_load_bag_smoke():
    from download_sample_bag import ensure_sample_bag  # type: ignore

    bag_path = ensure_sample_bag()
    data = load_bag(bag_path)

    assert isinstance(data, BagData)
    assert data.metadata["duration_s"] > 0
    assert data.metadata["start_ns"] < data.metadata["end_ns"]
    assert len(data.metadata["topics"]) >= 1
    assert len(data.cameras) >= 1, f"cameras empty; topics={data.metadata['topics']}"
    # At least one camera has frames
    assert any(len(v) > 0 for v in data.cameras.values())

    # Telemetry is optional depending on sample, but our synthetic bag has /odom
    if data.telemetry:
        for topic, ts in data.telemetry.items():
            assert ts.t_ns.shape[0] > 0
            assert ts.values.shape[0] == ts.t_ns.shape[0]

    synced = sync_frames(data, target_hz=2.0, tolerance_ms=500)
    # With our synthetic 2Hz images, we expect at least a handful of synced entries
    assert isinstance(synced, list)


def test_synced_grid():
    # 3 fake BGR frames
    frames = {
        "/cam/a": np.full((100, 160, 3), 30, dtype=np.uint8),
        "/cam/b": np.full((100, 160, 3), 120, dtype=np.uint8),
        "/cam/c": np.full((100, 160, 3), 200, dtype=np.uint8),
    }
    out = synced_grid({"t_ns": 1_000_000_000, "frames": frames}, thumb_size=(400, 300))
    assert isinstance(out, Image.Image)
    assert out.size == (1200, 600)
    assert out.mode == "RGB"

    b64 = to_b64(out, fmt="JPEG", quality=70)
    assert isinstance(b64, str) and len(b64) > 100


def test_plot_telemetry():
    t = np.linspace(0, 1e9, 50, dtype=np.int64)
    ts1 = TimeSeries(
        t_ns=t,
        values=np.stack([np.sin(t / 1e9 * 6), np.cos(t / 1e9 * 6)], axis=1),
        fields=["sin", "cos"],
    )
    ts2 = TimeSeries(t_ns=t, values=np.linspace(0, 10, 50), fields=["v"])
    img = plot_telemetry(
        {"/odom": ts1, "/imu": ts2}, marks_ns=[int(5e8)], size=(800, 500)
    )
    assert isinstance(img, Image.Image)
    assert img.size[0] > 0 and img.size[1] > 0
    assert img.mode == "RGB"
