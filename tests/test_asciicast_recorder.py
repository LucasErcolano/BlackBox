"""#88 — asciinema cast recorder regression."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_recorder_produces_v2_cast(tmp_path):
    out = tmp_path / "test.cast"
    res = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "record_batch_asciicast.py"),
         "--out", str(out)],
        cwd=str(ROOT),
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0, res.stderr
    lines = out.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    assert header["version"] == 2
    assert header.get("provenance") == "offline"
    # Each subsequent line must parse as [t, "o", text].
    for line in lines[1:]:
        ev = json.loads(line)
        assert isinstance(ev, list) and len(ev) == 3
        assert ev[1] == "o"


def test_committed_cast_exists():
    cast = ROOT / "docs" / "recordings" / "offline_batch.cast"
    assert cast.exists(), "committed offline_batch.cast missing — run scripts/record_batch_asciicast.py"
    header = json.loads(cast.read_text(encoding="utf-8").splitlines()[0])
    assert header["version"] == 2
