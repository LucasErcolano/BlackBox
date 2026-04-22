"""NAO6 adapter scaffold tests — uses the synthetic fall fixture."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from black_box.platforms.nao6 import NAO6Adapter
from black_box.platforms.nao6._fixture import generate_fall_fixture


ANGLE_KEY = "InertialSensor/AngleY/Sensor/Value"


@pytest.fixture
def fixture_dir(tmp_path: Path) -> Path:
    return tmp_path / "nao6_fall"


@pytest.fixture
def artifacts(fixture_dir: Path) -> dict[str, Path]:
    return generate_fall_fixture(fixture_dir)


def test_ingest_dual_camera(artifacts: dict[str, Path]) -> None:
    result = NAO6Adapter().ingest(
        case_key="nao6_fall_synth_001",
        top_video=artifacts["top_video"],
        bottom_video=artifacts["bottom_video"],
        telemetry_csv=artifacts["telemetry_csv"],
        controller_source=artifacts["controller_source"],
        synthetic=True,
    )

    assert result["platform"] == "nao6"
    assert result["case_key"] == "nao6_fall_synth_001"

    assert 2.5 < result["duration_s"] < 3.5

    frames = result["frames"]
    assert len(frames) > 0
    for f in frames:
        assert isinstance(f, Image.Image)

    # Parallel timestamp list
    assert len(result["frame_timestamps_ns"]) == len(frames)

    # Telemetry present + fall is in the data
    assert ANGLE_KEY in result["time_series"]
    angle_series = result["time_series"][ANGLE_KEY]
    assert angle_series[-1][1] > 0.5

    # Non-numeric state key must have been skipped without error
    assert "BalanceController/State" not in result["time_series"]

    # Controller source loaded (single file)
    assert len(result["code_blobs"]) == 1
    assert "controller.py" in result["code_blobs"]

    # Dual camera metadata
    meta = result["metadata"]
    assert meta["synthetic"] is True
    assert set(meta["cameras_used"]) == {"top", "bottom"}
    assert len(meta["camera_order"]) == len(frames)
    assert set(meta["camera_order"]) == {"top", "bottom"}


def test_ingest_single_camera(artifacts: dict[str, Path]) -> None:
    result = NAO6Adapter().ingest(
        case_key="nao6_fall_synth_top_only",
        top_video=artifacts["top_video"],
        bottom_video=None,
        telemetry_csv=artifacts["telemetry_csv"],
        controller_source=artifacts["controller_source"],
    )

    assert result["platform"] == "nao6"
    assert result["metadata"]["cameras_used"] == ["top"]
    assert set(result["metadata"]["camera_order"]) == {"top"}
    assert len(result["frames"]) > 0


def test_non_float_rows_skipped(artifacts: dict[str, Path]) -> None:
    # BalanceController/State has string values; adapter must not raise.
    result = NAO6Adapter().ingest(
        case_key="nao6_nonfloat",
        top_video=artifacts["top_video"],
        telemetry_csv=artifacts["telemetry_csv"],
        controller_source=artifacts["controller_source"],
    )
    numeric_keys = set(result["time_series"].keys())
    assert ANGLE_KEY in numeric_keys
    assert "BalanceController/State" not in numeric_keys


def test_canonical_dict_keys(artifacts: dict[str, Path]) -> None:
    result = NAO6Adapter().ingest(
        case_key="nao6_keys",
        top_video=artifacts["top_video"],
        telemetry_csv=artifacts["telemetry_csv"],
        controller_source=artifacts["controller_source"],
    )
    expected = {
        "case_key",
        "platform",
        "duration_s",
        "frames",
        "frame_timestamps_ns",
        "time_series",
        "code_blobs",
        "metadata",
    }
    assert expected <= set(result.keys())
