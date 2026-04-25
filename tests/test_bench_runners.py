"""#78 — Tier-1 / Tier-2 batch runners + markdown table emission."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_tier1_offline_runs_over_real_cases():
    res = subprocess.run(
        [sys.executable, "-m", "black_box.eval.runner", "--tier", "1",
         "--case-dir", "black-box-bench/cases"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert res.returncode == 0
    assert "tier=1" in res.stdout
    assert "match=" in res.stdout


def test_tier2_offline_runs_over_real_cases():
    res = subprocess.run(
        [sys.executable, "-m", "black_box.eval.runner", "--tier", "2",
         "--case-dir", "black-box-bench/cases"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert res.returncode == 0
    assert "tier=2" in res.stdout


def test_tier1_writes_markdown_table(tmp_path):
    out = tmp_path / "results.md"
    res = subprocess.run(
        [sys.executable, "-m", "black_box.eval.runner", "--tier", "1",
         "--case-dir", "black-box-bench/cases", "--write-md", str(out)],
        cwd=str(ROOT),
        check=True,
        timeout=60,
        capture_output=True, text=True,
    )
    md = out.read_text(encoding="utf-8")
    assert "| Case |" in md and "Match / Miss / Error" in md
    assert "tier-1 forensic" in md


def test_rtk_heading_break_01_is_green_in_offline_tier1():
    """Acceptance: #78 calls out rtk_heading_break_01 must run green or be a tracked fail."""
    from black_box.eval.runner import run_tier
    summary = run_tier(1, ROOT / "black-box-bench" / "cases")
    rows = {r["case_key"]: r for r in summary["rows"]}
    assert "rtk_heading_break_01" in rows
    row = rows["rtk_heading_break_01"]
    # It must either match or be explicitly skeleton — silent failure is the bug.
    assert row["match"] or row.get("skeleton"), row


def test_public_asset_fetch_idempotent_with_cache(tmp_path, monkeypatch):
    from black_box.eval.public_data import PublicAsset, fetch_asset

    # Pre-populate cached file so fetch_asset must NOT re-download.
    case_dir = tmp_path / "case_x"
    case_dir.mkdir()
    cached = case_dir / "data.bin"
    cached.write_bytes(b"hello")
    asset = PublicAsset(case_key="case_x", url="http://example.invalid/data.bin")

    def _fail(*a, **kw):
        raise AssertionError("fetch_asset re-downloaded a cached file")

    monkeypatch.setattr("urllib.request.urlopen", _fail)
    out = fetch_asset(asset, tmp_path)
    assert out == cached and out.read_bytes() == b"hello"
