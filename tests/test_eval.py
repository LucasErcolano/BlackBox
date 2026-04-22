"""Smoke tests for the tier-3 eval runner."""
from __future__ import annotations

import json
from pathlib import Path

from black_box.eval.runner import run_tier3


def _make_case(root: Path, key: str, bug_id: str) -> None:
    case = root / key
    case.mkdir(parents=True)
    (case / "ground_truth.json").write_text(json.dumps({"bug_id": bug_id}))
    # token files so a future real run has something to read
    (case / "telemetry.npz").write_bytes(b"")
    (case / "source").mkdir()
    (case / "buggy").mkdir()


def test_run_tier3_stub_returns_expected_shape(tmp_path: Path):
    _make_case(tmp_path, "case_a", "off_by_one_timer")
    _make_case(tmp_path, "case_b", "frame_drop")

    out = run_tier3(tmp_path, use_claude=False)

    assert set(out.keys()) >= {
        "n_cases", "n_match", "accuracy", "total_cost_usd", "rows", "used_claude",
    }
    assert out["n_cases"] == 2
    # stub echoes ground truth -> perfect match
    assert out["n_match"] == 2
    assert out["accuracy"] == 1.0
    assert out["used_claude"] is False

    keys = {"case_key", "predicted_bug", "ground_truth_bug", "match", "cost_usd", "wall_time_s"}
    for row in out["rows"]:
        assert keys <= set(row.keys())


def test_run_tier3_empty_dir(tmp_path: Path):
    out = run_tier3(tmp_path, use_claude=False)
    assert out["n_cases"] == 0
    assert out["accuracy"] == 0.0
    assert out["rows"] == []


def test_run_tier3_filter_by_case(tmp_path: Path):
    _make_case(tmp_path, "case_a", "x")
    _make_case(tmp_path, "case_b", "y")
    out = run_tier3(tmp_path, use_claude=False, only="case_b")
    assert out["n_cases"] == 1
    assert out["rows"][0]["case_key"] == "case_b"
