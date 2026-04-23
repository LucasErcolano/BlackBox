"""Smoke tests for the tiered eval runner."""
from __future__ import annotations

import json
from pathlib import Path

from black_box.eval.runner import run_tier, run_tier3


def _make_case(
    root: Path,
    key: str,
    bug_class: str,
    window_s: tuple[float, float] | None = (10.0, 15.0),
    patch_target: dict[str, str] | None = None,
) -> None:
    case = root / key
    case.mkdir(parents=True)
    gt: dict = {"bug_class": bug_class}
    if window_s is not None:
        gt["window_s"] = list(window_s)
    if patch_target is not None:
        gt["patch_target"] = patch_target
    (case / "ground_truth.json").write_text(json.dumps(gt))
    (case / "telemetry.npz").write_bytes(b"")
    (case / "source").mkdir()
    (case / "buggy").mkdir()


# ---------------------------------------------------------------------------
# Tier-3 (original surface)
# ---------------------------------------------------------------------------
def test_run_tier3_stub_returns_expected_shape(tmp_path: Path):
    _make_case(tmp_path, "case_a", "pid_saturation")
    _make_case(tmp_path, "case_b", "sensor_timeout")

    out = run_tier3(tmp_path, use_claude=False)

    assert set(out.keys()) >= {
        "tier", "n_cases", "n_match", "accuracy", "total_cost_usd", "rows", "used_claude",
    }
    assert out["tier"] == 3
    assert out["n_cases"] == 2
    assert out["n_match"] == 2
    assert out["accuracy"] == 1.0
    assert out["used_claude"] is False

    keys = {"case_key", "predicted_bug", "ground_truth_bug", "match", "cost_usd", "wall_time_s", "source"}
    for row in out["rows"]:
        assert keys <= set(row.keys())
        assert row["source"] == "stub"


def test_run_tier3_empty_dir(tmp_path: Path):
    out = run_tier3(tmp_path, use_claude=False)
    assert out["n_cases"] == 0
    assert out["accuracy"] == 0.0
    assert out["rows"] == []


def test_run_tier3_filter_by_case(tmp_path: Path):
    _make_case(tmp_path, "case_a", "pid_saturation")
    _make_case(tmp_path, "case_b", "bad_gain_tuning")
    out = run_tier3(tmp_path, use_claude=False, only="case_b")
    assert out["n_cases"] == 1
    assert out["rows"][0]["case_key"] == "case_b"


def test_tier3_rejects_unknown_ground_truth(tmp_path: Path):
    """Unknown GT must not count as a match even if the stub echoes it."""
    case = tmp_path / "blank"
    case.mkdir(parents=True)
    (case / "ground_truth.json").write_text(json.dumps({}))
    out = run_tier3(tmp_path, use_claude=False)
    assert out["n_cases"] == 1
    assert out["n_match"] == 0
    assert out["accuracy"] == 0.0


# ---------------------------------------------------------------------------
# Tier-1 (forensic post-mortem, bench-scorer compatible)
# ---------------------------------------------------------------------------
def test_run_tier1_stub_scores_bug_window_patch(tmp_path: Path):
    patch_target = {"file": "src/pid.py", "function": "PIDController.step"}
    _make_case(tmp_path, "case_a", "pid_saturation",
               window_s=(12.0, 18.0), patch_target=patch_target)

    out = run_tier(1, tmp_path, use_claude=False)

    assert out["tier"] == 1
    assert out["n_cases"] == 1
    assert out["total_score"] == 2.0
    assert out["max_score"] == 2.0
    row = out["rows"][0]
    assert row["bug_score"] == 1.0
    assert row["window_score"] == 0.5
    assert row["patch_score"] == 0.5
    assert row["total_score"] == 2.0
    assert row["match"] is True


def test_tier1_partial_credit_when_window_misses():
    from black_box.eval.runner import _score_tier1

    gt = {
        "bug_class": "pid_saturation",
        "window_s": [12.0, 18.0],
        "patch_target": {"file": "src/pid.py", "function": "step"},
    }
    row = {
        "predicted_bug": "pid_saturation",
        "predicted_window": [30.0, 35.0],  # disjoint
        "predicted_patch": {"file": "src/pid.py", "function": "step"},
    }
    scored = _score_tier1(row, gt)
    assert scored["bug_score"] == 1.0
    assert scored["window_score"] == 0.0
    assert scored["patch_score"] == 0.5
    assert scored["total_score"] == 1.5


# ---------------------------------------------------------------------------
# Tier-2 (scenario mining)
# ---------------------------------------------------------------------------
def test_run_tier2_stub_finds_bug_window_as_moment(tmp_path: Path):
    _make_case(tmp_path, "case_a", "pid_saturation", window_s=(12.0, 18.0))
    out = run_tier(2, tmp_path, use_claude=False)

    assert out["tier"] == 2
    assert out["n_cases"] == 1
    row = out["rows"][0]
    assert row["predicted_moments"]
    assert row["match"] is True


def test_tier2_no_moments_is_not_a_match():
    from black_box.eval.runner import _score_tier2

    gt = {"bug_class": "pid_saturation", "window_s": [12.0, 18.0]}
    row = {"predicted_moments": []}
    scored = _score_tier2(row, gt)
    assert scored["match"] is False


def test_unknown_tier_raises(tmp_path: Path):
    import pytest

    with pytest.raises(ValueError):
        run_tier(9, tmp_path, use_claude=False)
