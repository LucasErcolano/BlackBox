"""Tests for NAO6 synthetic fall-fixture variants.

Each scenario must emit a 4-file artifact set the adapter can consume.
We verify: file existence, CSV schema + sample counts, the intentional
bug_class tag in each controller.py, and that each MP4 decodes to 30
non-empty frames at 320x240.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import pytest

from black_box.platforms.nao6._fixture import (
    generate_lateral_tip_fixture,
    generate_stumble_recovery_fail_fixture,
)


EXPECTED_KEYS = {"top_video", "bottom_video", "telemetry_csv", "controller_source"}
EXPECTED_FRAMES = 30
EXPECTED_SAMPLES_PER_NUMERIC_KEY = 300


# ---- helpers ---------------------------------------------------------------


def _count_samples_per_key(csv_path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    with csv_path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            counts[row["key"]] += 1
    return counts


def _video_frames(path: Path) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(path))
    try:
        assert cap.isOpened(), f"VideoCapture failed to open {path}"
        frames: list[np.ndarray] = []
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame)
        return frames
    finally:
        cap.release()


def _assert_valid_video(path: Path) -> None:
    frames = _video_frames(path)
    assert len(frames) == EXPECTED_FRAMES, f"{path.name}: got {len(frames)} frames, expected {EXPECTED_FRAMES}"
    assert any(int(np.count_nonzero(f)) > 0 for f in frames), f"{path.name}: all frames are empty"
    h, w = frames[0].shape[:2]
    assert (w, h) == (320, 240), f"{path.name}: got {(w, h)}, expected (320, 240)"


# ---- lateral tip -----------------------------------------------------------


@pytest.fixture
def lateral_artifacts(tmp_path: Path) -> dict[str, Path]:
    return generate_lateral_tip_fixture(tmp_path / "lateral")


def test_lateral_emits_all_four_files(lateral_artifacts: dict[str, Path]) -> None:
    assert set(lateral_artifacts.keys()) == EXPECTED_KEYS
    for p in lateral_artifacts.values():
        assert p.exists(), f"missing {p}"
        assert p.stat().st_size > 0, f"empty file {p}"


def test_lateral_telemetry_keys_and_counts(lateral_artifacts: dict[str, Path]) -> None:
    counts = _count_samples_per_key(lateral_artifacts["telemetry_csv"])
    assert counts["InertialSensor/AngleX/Sensor/Value"] == EXPECTED_SAMPLES_PER_NUMERIC_KEY
    assert counts["GyrX"] == EXPECTED_SAMPLES_PER_NUMERIC_KEY
    assert counts["AccZ"] == EXPECTED_SAMPLES_PER_NUMERIC_KEY
    assert counts["BalanceController/State"] == EXPECTED_SAMPLES_PER_NUMERIC_KEY
    # The pitch-axis key is specifically NOT present in a lateral scenario.
    assert "InertialSensor/AngleY/Sensor/Value" not in counts


def test_lateral_controller_has_bug_class_tag(lateral_artifacts: dict[str, Path]) -> None:
    src = lateral_artifacts["controller_source"].read_text(encoding="utf-8")
    assert "bug_class: bad_gain_tuning" in src


def test_lateral_videos_decode(lateral_artifacts: dict[str, Path]) -> None:
    _assert_valid_video(lateral_artifacts["top_video"])
    _assert_valid_video(lateral_artifacts["bottom_video"])


# ---- stumble + recovery-fail ----------------------------------------------


@pytest.fixture
def stumble_artifacts(tmp_path: Path) -> dict[str, Path]:
    return generate_stumble_recovery_fail_fixture(tmp_path / "stumble")


def test_stumble_emits_all_four_files(stumble_artifacts: dict[str, Path]) -> None:
    assert set(stumble_artifacts.keys()) == EXPECTED_KEYS
    for p in stumble_artifacts.values():
        assert p.exists(), f"missing {p}"
        assert p.stat().st_size > 0, f"empty file {p}"


def test_stumble_telemetry_keys_and_counts(stumble_artifacts: dict[str, Path]) -> None:
    counts = _count_samples_per_key(stumble_artifacts["telemetry_csv"])
    assert counts["InertialSensor/AngleY/Sensor/Value"] == EXPECTED_SAMPLES_PER_NUMERIC_KEY
    assert counts["GyrY"] == EXPECTED_SAMPLES_PER_NUMERIC_KEY
    assert counts["AccZ"] == EXPECTED_SAMPLES_PER_NUMERIC_KEY
    assert counts["BalanceController/State"] == EXPECTED_SAMPLES_PER_NUMERIC_KEY


def test_stumble_state_transitions_exist(stumble_artifacts: dict[str, Path]) -> None:
    """State sequence should visit standing -> teetering -> recovering -> fell,
    and 'recovering' must never transition back to 'standing'."""
    states_in_order: list[str] = []
    with stumble_artifacts["telemetry_csv"].open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["key"] == "BalanceController/State":
                states_in_order.append(row["value"])

    # All four labels present
    seen = set(states_in_order)
    assert {"standing", "teetering", "recovering", "fell"} <= seen

    # Once 'recovering' appears, 'standing' must not reappear.
    first_recovering = states_in_order.index("recovering")
    assert "standing" not in states_in_order[first_recovering:]


def test_stumble_controller_has_bug_class_tag(stumble_artifacts: dict[str, Path]) -> None:
    src = stumble_artifacts["controller_source"].read_text(encoding="utf-8")
    assert "bug_class: state_machine_deadlock" in src


def test_stumble_videos_decode(stumble_artifacts: dict[str, Path]) -> None:
    _assert_valid_video(stumble_artifacts["top_video"])
    _assert_valid_video(stumble_artifacts["bottom_video"])
