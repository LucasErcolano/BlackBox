"""Edge case tests for black_box.analysis.windows.

Closes #34 (P3 coverage gaps). `from_timeline` is the pivot function for the
two-pass sampler — if it drifts, we re-run Claude over garbage windows and
burn budget. These tests pin down the empty / missing-key / span override /
absolute-ns-offset behaviors plus adjacent helpers' boundary cases.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from black_box.analysis.windows import (
    Window,
    dump,
    from_error_bursts,
    from_flag_transitions,
    from_gaps,
    from_timeline,
    load,
    merge_overlapping,
    top_k,
)


# -------- Window dataclass --------------------------------------------------


def test_window_start_end_ns_arithmetic():
    w = Window(center_ns=int(10e9), span_s=4.0, label="x")
    assert w.start_ns == int(8e9)
    assert w.end_ns == int(12e9)


def test_window_to_dict_round_trip_via_load(tmp_path: Path):
    """dump/load round-trip preserves every field exactly."""
    windows = [
        Window(center_ns=1_000_000_000, span_s=5.0, label="alpha", priority=0.5),
        Window(center_ns=2_500_000_000, span_s=7.5, label="beta", priority=0.9),
    ]
    p = tmp_path / "w.json"
    dump(windows, p)
    loaded = load(p)
    assert loaded == windows


# -------- from_timeline edge cases ------------------------------------------


def test_from_timeline_empty_analysis():
    assert from_timeline({}) == []
    assert from_timeline({"timeline": []}) == []
    assert from_timeline({"timeline": None}) == []


def test_from_timeline_missing_timeline_key():
    assert from_timeline({"other": "noise"}) == []


def test_from_timeline_default_priority_and_span():
    analysis = {"timeline": [{"t_ns": 5_000_000_000, "label": "one"}]}
    ws = from_timeline(analysis, default_span_s=45.0)
    assert len(ws) == 1
    assert ws[0].span_s == 45.0
    # no cross_view flag -> priority 0.5
    assert ws[0].priority == 0.5


def test_from_timeline_cross_view_bumps_priority():
    analysis = {"timeline": [
        {"t_ns": 1_000, "label": "xv", "cross_view": True},
        {"t_ns": 2_000, "label": "normal", "cross_view": False},
    ]}
    ws = from_timeline(analysis)
    assert ws[0].priority == 0.7
    assert ws[1].priority == 0.5


def test_from_timeline_keeps_cross_view_only_filter():
    analysis = {"timeline": [
        {"t_ns": 1, "label": "a", "cross_view": True},
        {"t_ns": 2, "label": "b"},
        {"t_ns": 3, "label": "c", "cross_view": True},
    ]}
    ws = from_timeline(analysis, keep_cross_view_only=True)
    assert [w.label for w in ws] == ["a", "c"]


def test_from_timeline_bag_start_ns_offset():
    """bag_start_ns is added to every relative t_ns in the timeline."""
    bag_start = 1_700_000_000_000_000_000  # ~2023 in absolute ns
    analysis = {"timeline": [
        {"t_ns": 5_000_000_000, "label": "rel+5s"},
        {"t_ns": 10_000_000_000, "label": "rel+10s"},
    ]}
    ws = from_timeline(analysis, bag_start_ns=bag_start)
    assert ws[0].center_ns == bag_start + 5_000_000_000
    assert ws[1].center_ns == bag_start + 10_000_000_000


def test_from_timeline_entry_level_span_overrides_default():
    analysis = {"timeline": [
        {"t_ns": 0, "label": "short", "span_s": 2.5},
        {"t_ns": 1, "label": "default"},
    ]}
    ws = from_timeline(analysis, default_span_s=30.0)
    assert ws[0].span_s == 2.5
    assert ws[1].span_s == 30.0


def test_from_timeline_missing_t_ns_defaults_to_zero():
    analysis = {"timeline": [{"label": "no-t"}]}
    ws = from_timeline(analysis, bag_start_ns=500)
    assert ws[0].center_ns == 500  # 0 + bag_start


def test_from_timeline_truncates_long_labels():
    long_label = "x" * 500
    analysis = {"timeline": [{"t_ns": 0, "label": long_label}]}
    ws = from_timeline(analysis)
    assert len(ws[0].label) == 200


def test_from_timeline_strips_and_stringifies_label():
    analysis = {"timeline": [{"t_ns": 0, "label": "  trim me  "}]}
    ws = from_timeline(analysis)
    assert ws[0].label == "trim me"


def test_from_timeline_span_s_none_falls_back_to_default():
    """Explicit span_s=None must not override the default."""
    analysis = {"timeline": [{"t_ns": 0, "label": "n", "span_s": None}]}
    ws = from_timeline(analysis, default_span_s=12.0)
    assert ws[0].span_s == 12.0


# -------- adjacent detectors: edge cases ------------------------------------


def test_from_flag_transitions_empty_and_mismatched():
    assert from_flag_transitions(np.array([]), np.array([]), "x") == []
    # length mismatch -> defensive empty
    t = np.array([0, 1], dtype=np.int64)
    v = np.array(["a"])
    assert from_flag_transitions(t, v, "x") == []


def test_from_flag_transitions_respects_max_transitions():
    t = np.arange(10, dtype=np.int64) * int(1e9)
    vals = np.array([i % 2 for i in range(10)])  # flips every step
    ws = from_flag_transitions(t, vals, label_prefix="p", max_transitions=3)
    assert len(ws) == 3


def test_from_gaps_empty_short_array():
    assert from_gaps(np.array([0], dtype=np.int64), min_gap_s=1.0, label="x") == []


def test_from_gaps_span_is_at_least_gap_plus_ten():
    """span_s = max(span_s, dt + 10.0) guarantees the window covers the gap."""
    t = np.array([0, 1, 100], dtype=np.int64) * int(1e9)  # 99s gap
    ws = from_gaps(t, min_gap_s=10.0, label="g", span_s=5.0)
    assert len(ws) == 1
    assert ws[0].span_s >= 99.0 + 10.0 - 0.01


def test_from_error_bursts_empty_input():
    assert from_error_bursts(np.array([], dtype=np.int64)) == []


def test_from_error_bursts_below_threshold_returns_empty():
    # 3 events spread across different 5s buckets -> no bucket >= 5
    t = (np.array([0, 10, 20]) * int(1e9)).astype(np.int64)
    assert from_error_bursts(t, bucket_s=5.0, min_errors_per_bucket=5) == []


# -------- merge_overlapping + top_k boundaries ------------------------------


def test_merge_overlapping_empty_input():
    assert merge_overlapping([]) == []


def test_merge_overlapping_non_overlapping_kept_separate():
    ws = [
        Window(center_ns=int(10e9), span_s=2.0, label="a", priority=0.5),
        Window(center_ns=int(100e9), span_s=2.0, label="b", priority=0.5),
    ]
    merged = merge_overlapping(ws, merge_gap_s=1.0)
    assert len(merged) == 2
    assert merged[0].label == "a"
    assert merged[1].label == "b"


def test_merge_overlapping_exact_boundary_merges():
    """Adjacent windows (gap == merge_gap_s) must merge (boundary inclusive)."""
    w1 = Window(center_ns=0, span_s=2.0, label="a", priority=0.5)  # end = 1e9
    w2 = Window(center_ns=int(3e9), span_s=2.0, label="b", priority=0.5)  # start = 2e9
    merged = merge_overlapping([w1, w2], merge_gap_s=1.0)
    assert len(merged) == 1
    assert "a" in merged[0].label and "b" in merged[0].label


def test_merge_overlapping_preserves_order_when_input_scrambled():
    w_late = Window(center_ns=int(100e9), span_s=2.0, label="late", priority=0.5)
    w_early = Window(center_ns=int(5e9), span_s=2.0, label="early", priority=0.5)
    merged = merge_overlapping([w_late, w_early], merge_gap_s=0.5)
    assert [w.label for w in merged] == ["early", "late"]


def test_top_k_zero_returns_empty():
    ws = [Window(1, 1, "a", 0.5)]
    assert top_k(ws, 0) == []


def test_top_k_larger_than_list_returns_all():
    ws = [Window(1, 1, "a", 0.5), Window(2, 1, "b", 0.9)]
    out = top_k(ws, 10)
    assert len(out) == 2
    assert out[0].priority == 0.9
