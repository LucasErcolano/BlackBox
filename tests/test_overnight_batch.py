"""Tests for scripts/overnight_batch.py.

Exercises the stub path, budget gate, manifest schema, and table
rendering. Never calls the Claude SDK — live coverage is the operator's
job (see ``OVERNIGHT_BATCH.md``).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "overnight_batch.py"


def _load_module():
    # Register in sys.modules before exec so @dataclass can introspect
    # via cls.__module__ (fixed-by / workaround for cpython 3.13 change).
    spec = importlib.util.spec_from_file_location("overnight_batch", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["overnight_batch"] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()


def _make_synth_case(root: Path, key: str, bug: str, window=(10.0, 15.0)) -> Path:
    case = root / key
    case.mkdir(parents=True)
    gt: dict = {"bug_class": bug, "window_s": list(window)}
    (case / "ground_truth.json").write_text(json.dumps(gt))
    return case


def _make_skeleton_case(root: Path, key: str) -> Path:
    case = root / key
    case.mkdir(parents=True)
    gt = {"bug_class": "unknown", "status": "skeleton_awaiting_bag"}
    (case / "ground_truth.json").write_text(json.dumps(gt))
    return case


# ---------------------------------------------------------------------------
# discover_cases
# ---------------------------------------------------------------------------
def test_discover_cases_synthetic_plus_skeleton(tmp_path: Path):
    _make_synth_case(tmp_path, "a", "pid_saturation")
    _make_skeleton_case(tmp_path, "b")
    # Non-case directory should be ignored.
    (tmp_path / "not_a_case").mkdir()

    cases = mod.discover_cases(tmp_path)
    assert [c.name for c in cases] == ["a", "b"]


def test_discover_cases_only_filter(tmp_path: Path):
    _make_synth_case(tmp_path, "a", "pid_saturation")
    _make_synth_case(tmp_path, "b", "sensor_timeout")
    cases = mod.discover_cases(tmp_path, only="b")
    assert len(cases) == 1
    assert cases[0].name == "b"


# ---------------------------------------------------------------------------
# stub_predict — synthetic vs skeleton
# ---------------------------------------------------------------------------
def test_stub_predict_synthetic_matches(tmp_path: Path):
    case = _make_synth_case(tmp_path, "a", "pid_saturation")
    gt = mod.load_gt(case)
    row = mod.stub_predict(case, gt)
    assert row.predicted_bug == "pid_saturation"
    assert row.bug_class_match is True
    assert row.status == "ok"
    assert row.source == "stub"
    assert row.cost_usd == 0.0


def test_stub_predict_skeleton_is_skip(tmp_path: Path):
    case = _make_skeleton_case(tmp_path, "sk")
    gt = mod.load_gt(case)
    row = mod.stub_predict(case, gt)
    assert row.predicted_bug == "unknown"
    assert row.bug_class_match is False
    assert row.status == "skeleton"


def test_stub_predict_honors_accepted_classes(tmp_path: Path):
    case = tmp_path / "rtk"
    case.mkdir()
    gt = {
        "bug_class": "other",
        "scoring": {"bug_class_match": ["other", "sensor_timeout"]},
    }
    (case / "ground_truth.json").write_text(json.dumps(gt))
    loaded = mod.load_gt(case)
    row = mod.stub_predict(case, loaded)
    assert row.predicted_bug == "other"
    assert row.bug_class_match is True


# ---------------------------------------------------------------------------
# cumulative_cost_usd
# ---------------------------------------------------------------------------
def test_cumulative_cost_missing_file(tmp_path: Path):
    assert mod.cumulative_cost_usd(tmp_path / "nope.jsonl") == 0.0


def test_cumulative_cost_sums_valid_ignores_bad(tmp_path: Path):
    path = tmp_path / "costs.jsonl"
    path.write_text(
        json.dumps({"usd_cost": 0.5}) + "\n"
        + "not-json\n"
        + json.dumps({"usd_cost": 1.25}) + "\n"
        + json.dumps({"other_field": 99.0}) + "\n"  # no usd_cost key
    )
    total = mod.cumulative_cost_usd(path)
    assert total == pytest.approx(1.75)


# ---------------------------------------------------------------------------
# End-to-end main() in dry-run mode
# ---------------------------------------------------------------------------
def test_main_dry_run_writes_manifest_and_table(tmp_path: Path, capsys):
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    _make_synth_case(case_dir, "a", "pid_saturation")
    _make_skeleton_case(case_dir, "b")

    out_dir = tmp_path / "batch_2026-04-23_dryrun"
    rc = mod.main([
        "--dry-run",
        "--case-dir", str(case_dir),
        "--out-dir", str(out_dir),
    ])
    assert rc == 0

    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["mode"] == "dry-run"
    assert manifest["model"] == "claude-opus-4-7"
    assert manifest["batch_id"] == out_dir.name
    assert manifest["n_cases"] == 2
    # Synthetic matches, skeleton does not.
    assert manifest["n_match"] == 1
    assert manifest["spent_usd"] == 0.0

    # Table files exist and carry the issue-25 column headers.
    table_txt = (out_dir / "table.txt").read_text()
    for col in ["case", "wall-s", "$", "bug_class_match", "top-hyp confidence"]:
        assert col in table_txt
    table_md = (out_dir / "table.md").read_text()
    assert "| case |" in table_md
    assert "bug_class_match" in table_md

    # Per-case JSONs flushed.
    assert (out_dir / "a.json").exists()
    assert (out_dir / "b.json").exists()


def test_main_only_filter_runs_single_case(tmp_path: Path):
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    _make_synth_case(case_dir, "a", "pid_saturation")
    _make_synth_case(case_dir, "b", "sensor_timeout")
    out_dir = tmp_path / "batch"
    rc = mod.main([
        "--dry-run", "--only", "a",
        "--case-dir", str(case_dir),
        "--out-dir", str(out_dir),
    ])
    assert rc == 0
    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["n_cases"] == 1
    assert manifest["rows"][0]["case_key"] == "a"


def test_main_empty_case_dir_exits_nonzero(tmp_path: Path):
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    rc = mod.main([
        "--dry-run",
        "--case-dir", str(case_dir),
        "--out-dir", str(tmp_path / "out"),
    ])
    assert rc == 1


# ---------------------------------------------------------------------------
# Budget gate — live mode with a baseline that would cross the cap.
# ---------------------------------------------------------------------------
def test_budget_gate_skips_cases_when_baseline_exceeds_cap(tmp_path: Path, monkeypatch):
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    _make_synth_case(case_dir, "a", "pid_saturation")
    _make_synth_case(case_dir, "b", "sensor_timeout")

    # Point the module's COSTS_PATH at a file that already sits at $49,
    # so adding the $2 per-case ceiling crosses a $50 cap.
    fake_costs = tmp_path / "costs.jsonl"
    fake_costs.write_text(json.dumps({"usd_cost": 49.0}) + "\n")
    monkeypatch.setattr(mod, "COSTS_PATH", fake_costs)

    out_dir = tmp_path / "out"
    # Live mode (no --dry-run) triggers the gate; claude path is not
    # reached because the gate fires first.
    rc = mod.main([
        "--case-dir", str(case_dir),
        "--out-dir", str(out_dir),
        "--budget-usd", "50",
    ])
    assert rc == 0
    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["mode"] == "live"
    assert manifest["spent_usd"] == 0.0
    assert all(r["status"] == "skipped_budget" for r in manifest["rows"])
    assert all(r["source"] == "skipped" for r in manifest["rows"])


# ---------------------------------------------------------------------------
# render_table / render_markdown_table
# ---------------------------------------------------------------------------
def test_render_table_headers_present():
    row = mod.CaseRow(
        case_key="a",
        ground_truth_bug="pid_saturation",
        predicted_bug="pid_saturation",
        bug_class_match=True,
        confidence=0.77,
        cost_usd=0.12,
        wall_time_s=22.5,
        status="ok",
        source="claude",
    )
    text = mod.render_table([row])
    assert "case" in text
    assert "wall-s" in text
    assert "bug_class_match" in text
    assert "top-hyp confidence" in text
    assert "OK" in text

    md = mod.render_markdown_table([row])
    assert md.startswith("| case | wall-s | $ | bug_class_match | top-hyp confidence |")
    assert "| a |" in md


def test_empty_rows_tables_safe():
    assert mod.render_table([]) == "(no cases)"
    assert mod.render_markdown_table([]) == "(no cases)"
