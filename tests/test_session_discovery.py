"""Unit tests for session discovery + window extraction."""
from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pytest

from black_box.ingestion.session import discover_session_assets
from black_box.analysis.windows import (
    Window,
    from_flag_transitions,
    from_gaps,
    from_error_bursts,
    from_timeline,
    merge_overlapping,
    top_k,
)
from black_box.ingestion.frame_sampler import _targets_ns


def _touch(path: Path, size: int = 0, mtime: float | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        if size:
            f.write(b"\0" * size)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


# -------- session discovery -------------------------------------------------


def test_single_bag_no_prefix(tmp_path: Path):
    b = _touch(tmp_path / "run.bag", size=1024)
    assets = discover_session_assets(b)
    assert assets.bags == [b]
    assert assets.session_key is None


def test_numeric_prefix_groups_siblings(tmp_path: Path):
    # Two sessions in the same dir: 2_* (heaviest) and 3_*
    _touch(tmp_path / "2_sensors.bag", size=10 * 1024)
    _touch(tmp_path / "2_cam.bag", size=100 * 1024)
    _touch(tmp_path / "3_sensors.bag", size=5 * 1024)
    assets = discover_session_assets(tmp_path)
    assert assets.session_key == "2"
    assert [p.name for p in assets.bags] == ["2_cam.bag", "2_sensors.bag"]


def test_force_session_key(tmp_path: Path):
    _touch(tmp_path / "2_sensors.bag", size=1024)
    _touch(tmp_path / "3_sensors.bag", size=1024)
    a = discover_session_assets(tmp_path, session_key="3")
    assert a.session_key == "3"
    assert [p.name for p in a.bags] == ["3_sensors.bag"]


def test_peripheral_filename_date_filter(tmp_path: Path):
    # Session bags at t0; a stale webm whose filename says 60 days earlier
    now = time.time()
    _touch(tmp_path / "2_sensors.bag", size=1024, mtime=now)
    _touch(tmp_path / "2_audio.wav", size=512, mtime=now)
    stale = tmp_path / "2026-01-01-oldrecording.webm"
    _touch(stale, size=256, mtime=now)  # copy-mtime in window, but filename says Jan
    a = discover_session_assets(tmp_path)
    assert [p.name for p in a.audio] == ["2_audio.wav"]
    # webm filename date falls outside +/-1-day window of session bags
    assert all(p.name != stale.name for p in a.video)


def test_ros_logs_opt_in_and_filtered_by_uuid(tmp_path: Path):
    now = time.time()
    _touch(tmp_path / "2_sensors.bag", size=1024, mtime=now)
    ros_log_root = tmp_path / "ros_logs" / "log"
    # Historical UUIDv1 (stamped last year) should NOT be in window.
    hist_uuid = "00860510-79e4-11f0-a4f0-a1fdd8400543"  # aug 2025
    _touch(ros_log_root / hist_uuid / "stdout.log", size=64, mtime=now)
    a = discover_session_assets(tmp_path, include_ros_logs=True)
    assert a.ros_logs == []


# -------- windows -----------------------------------------------------------


def test_from_flag_transitions():
    t = np.array([0, 1, 2, 3, 4, 5], dtype=np.int64) * int(1e9)
    vals = np.array(["off", "off", "on", "on", "off", "off"])
    ws = from_flag_transitions(t, vals, label_prefix="rtk", span_s=4.0)
    assert len(ws) == 2
    assert ws[0].center_ns == 2 * int(1e9)
    assert ws[1].center_ns == 4 * int(1e9)


def test_from_gaps_picks_largest():
    t = np.array([0, 1, 2, 20, 21, 30, 31], dtype=np.int64) * int(1e9)
    ws = from_gaps(t, min_gap_s=3.0, label="missing", max_gaps=2)
    assert len(ws) == 2
    # largest gap (2 -> 20 = 18s) first
    assert "18" in ws[0].label or "18.0" in ws[0].label


def test_from_error_bursts():
    # 10 errors within a 5s bucket around t=100s
    t = np.array([100, 100.5, 101, 101.5, 102, 102.5, 103, 103.5, 104, 104.5]) * int(1e9)
    ws = from_error_bursts(t.astype(np.int64), bucket_s=5.0, min_errors_per_bucket=5)
    assert len(ws) == 1
    assert 95 * 1e9 <= ws[0].center_ns <= 110 * 1e9


def test_from_timeline_honors_cross_view():
    analysis = {"timeline": [
        {"t_ns": 1_000_000_000, "label": "a", "cross_view": True},
        {"t_ns": 2_000_000_000, "label": "b", "cross_view": False},
    ]}
    all_ = from_timeline(analysis)
    assert len(all_) == 2
    xv = from_timeline(analysis, keep_cross_view_only=True)
    assert len(xv) == 1
    assert xv[0].label == "a"


def test_merge_overlapping_collapses_near_duplicates():
    ws = [
        Window(center_ns=int(10e9), span_s=20.0, label="x", priority=0.5),
        Window(center_ns=int(14e9), span_s=20.0, label="y", priority=0.8),
        Window(center_ns=int(100e9), span_s=10.0, label="z", priority=0.3),
    ]
    merged = merge_overlapping(ws, merge_gap_s=2.0)
    assert len(merged) == 2
    # kept the higher priority
    assert merged[0].priority == 0.8
    assert "x" in merged[0].label and "y" in merged[0].label


def test_top_k():
    ws = [Window(1, 1, "a", 0.1), Window(2, 1, "b", 0.9), Window(3, 1, "c", 0.5)]
    assert [w.label for w in top_k(ws, 2)] == ["b", "c"]


# -------- frame sampler target math ----------------------------------------


def test_targets_mix_baseline_and_dense():
    start, end = 0, int(100e9)
    ws = [Window(center_ns=int(50e9), span_s=10.0, label="mid", priority=0.8)]
    targets = _targets_ns(start, end, ws, dense_stride_s=2.0, baseline_n=5)
    # 5 baseline + ~6 dense (2s stride across 10s window) minus overlap dedup
    assert 6 <= len(targets) <= 12
    # at least one target inside the window and labeled win:*
    inside = [t for t in targets if 44e9 <= t[0] <= 56e9]
    assert any(lab.startswith("win:") for _, lab in inside)
