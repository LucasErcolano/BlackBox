"""Smoke tests for the synthesis module."""

from __future__ import annotations

import difflib
import json
from pathlib import Path

import numpy as np
import pytest

from black_box.synthesis import (
    build_all_cases,
    gen_bad_gain,
    gen_pid_saturation,
    gen_sensor_timeout,
    materialize_case,
)
from black_box.synthesis.controllers import buggy_sources, clean_sources


EXPECTED_TOPICS = {
    "pid_saturation": {"/odom/pose", "/cmd_vel", "/pwm", "/reference"},
    "sensor_timeout": {"/scan_range", "/imu/accel", "/cmd_vel", "/reference"},
    "bad_gain": {"/odom/pose", "/cmd_vel", "/pwm", "/reference"},
}


def _assert_shapes(tele: dict) -> None:
    lengths = set()
    for topic, ts in tele.items():
        assert set(ts.keys()) >= {"t_ns", "values", "fields"}, topic
        t_ns = ts["t_ns"]
        values = ts["values"]
        fields = ts["fields"]
        assert isinstance(t_ns, np.ndarray) and t_ns.dtype == np.int64
        assert isinstance(values, np.ndarray)
        assert values.ndim == 2
        assert values.shape[0] == t_ns.shape[0]
        assert values.shape[1] == len(fields)
        lengths.add(t_ns.shape[0])
    assert len(lengths) == 1, f"inconsistent timeline lengths: {lengths}"


def test_telemetry_shapes():
    pid = gen_pid_saturation()
    st = gen_sensor_timeout()
    bg = gen_bad_gain()

    assert set(pid.keys()) == EXPECTED_TOPICS["pid_saturation"]
    assert set(st.keys()) == EXPECTED_TOPICS["sensor_timeout"]
    assert set(bg.keys()) == EXPECTED_TOPICS["bad_gain"]

    for tele in (pid, st, bg):
        _assert_shapes(tele)


def test_pid_saturation_signature():
    sat_start, diverge = 12.0, 15.0
    tele = gen_pid_saturation(duration_s=20.0, hz=50.0, sat_start_s=sat_start, diverge_s=diverge)

    pwm = tele["/pwm"]["values"]
    t = tele["/pwm"]["t_ns"].astype(np.float64) * 1e-9

    sat_mask = (t >= sat_start) & (t <= diverge)
    assert sat_mask.sum() > 0
    # PWM is pegged at 255 for all 4 motors in the saturation window
    assert np.all(pwm[sat_mask] >= 255.0 - 1e-6), "PWM did not saturate"

    # Pose error grows monotonically after divergence (sampled)
    pose = tele["/odom/pose"]["values"]
    ref = tele["/reference"]["values"]
    err = np.linalg.norm(pose - ref, axis=1)

    post = t > diverge
    post_err = err[post]
    # subsample to reduce noise effect
    sampled = post_err[::25]
    assert len(sampled) >= 3
    diffs = np.diff(sampled)
    assert (diffs >= -1e-3).mean() > 0.8, "error should be mostly increasing after divergence"
    assert sampled[-1] > sampled[0] + 0.1


def test_controllers_diff_size():
    buggy = buggy_sources()
    clean = clean_sources()
    assert set(buggy.keys()) == set(clean.keys())
    for bug_class, files in buggy.items():
        for fname, buggy_code in files.items():
            clean_code = clean[bug_class][fname]
            diff = list(
                difflib.unified_diff(
                    clean_code.splitlines(keepends=False),
                    buggy_code.splitlines(keepends=False),
                    lineterm="",
                    n=0,
                )
            )
            # Count only +/- lines (ignoring the +++/--- headers)
            change_lines = [
                ln for ln in diff
                if (ln.startswith("+") and not ln.startswith("+++"))
                or (ln.startswith("-") and not ln.startswith("---"))
            ]
            assert 3 <= len(change_lines) <= 20, (
                f"{bug_class}/{fname} diff has {len(change_lines)} change lines "
                f"(want 3..20)"
            )


def test_cases_materialize(tmp_path: Path):
    cases = build_all_cases()
    assert len(cases) == 3
    keys = {c.key for c in cases}
    assert keys == {"pid_saturation_01", "sensor_timeout_01", "bad_gain_01"}

    for case in cases:
        materialize_case(case, tmp_path)
        root = tmp_path / case.key
        assert (root / "ground_truth.json").exists()
        assert (root / "telemetry.npz").exists()
        assert (root / "video_prompts.md").exists()
        assert (root / "README.md").exists()
        # at least one buggy + one clean source file
        buggy_files = list((root / "source" / "buggy").glob("*.py"))
        clean_files = list((root / "source" / "clean").glob("*.py"))
        assert buggy_files and clean_files

        gt = json.loads((root / "ground_truth.json").read_text())
        assert gt["bug_class"] == case.bug_class
        assert "window_s" in gt and len(gt["window_s"]) == 2
        assert isinstance(gt["evidence_hints"], list) and gt["evidence_hints"]
        assert isinstance(gt["patch_hint"], str) and gt["patch_hint"]


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
