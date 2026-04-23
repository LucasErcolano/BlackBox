"""Tests for scripts/snapshot_controllers.py."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "snapshot_controllers.py"
CONTROLLERS_DIR = REPO_ROOT / "src" / "black_box" / "platforms" / "nao6" / "controllers"


def test_snapshot_produces_valid_manifest_and_copies(tmp_path: Path) -> None:
    out_dir = tmp_path / "nao6_case"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--case-key",
            "test_case",
            "--out",
            str(out_dir),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"snapshot script failed: stdout={result.stdout} stderr={result.stderr}"
    )

    assert out_dir.is_dir()
    snapshot_dir = out_dir / "controllers_snapshot"
    assert snapshot_dir.is_dir()

    manifest_path = out_dir / "snapshot_manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text())

    for key in ("case_key", "timestamp_utc", "git_sha", "python_version", "controllers"):
        assert key in manifest, f"missing manifest key: {key}"
    assert manifest["case_key"] == "test_case"
    assert isinstance(manifest["controllers"], list)
    assert len(manifest["controllers"]) >= 3

    source_files = {p.name for p in CONTROLLERS_DIR.glob("*.py")}
    copied_files = {p.name for p in snapshot_dir.glob("*.py")}
    assert source_files.issubset(copied_files), (
        f"not all controllers copied: missing {source_files - copied_files}"
    )

    for entry in manifest["controllers"]:
        for key in ("filename", "sha256", "size_bytes", "line_count"):
            assert key in entry, f"manifest entry missing {key}: {entry}"
        copied_path = snapshot_dir / entry["filename"]
        assert copied_path.is_file()
        recomputed = hashlib.sha256(copied_path.read_bytes()).hexdigest()
        assert recomputed == entry["sha256"], (
            f"sha256 mismatch for {entry['filename']}: "
            f"manifest={entry['sha256']} actual={recomputed}"
        )
        assert entry["size_bytes"] == copied_path.stat().st_size


def test_snapshot_prints_summary_line(tmp_path: Path) -> None:
    out_dir = tmp_path / "summary_case"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--case-key",
            "summary_case",
            "--out",
            str(out_dir),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "snapshotted" in result.stdout
    assert "controllers" in result.stdout
    assert str(out_dir) in result.stdout
