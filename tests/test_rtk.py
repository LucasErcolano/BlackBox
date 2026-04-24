"""Unit tests for scripts/rtk.py — the Rust Token Killer stdout filter."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# scripts/ is not on the package path by default.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import rtk  # noqa: E402


# ---------------------------------------------------------------------------
# ANSI strip
# ---------------------------------------------------------------------------


def test_strip_ansi_colors():
    text = "\x1b[31mERROR\x1b[0m: bad thing\n"
    assert rtk.strip_ansi(text) == "ERROR: bad thing\n"


def test_strip_ansi_cursor_moves():
    # CSI sequences for cursor movement + clear line.
    text = "\x1b[2K\x1b[1Aprogress: 50%\n"
    assert rtk.strip_ansi(text) == "progress: 50%\n"


def test_strip_ansi_osc_title_set():
    # OSC (window title) terminated by BEL.
    text = "\x1b]0;window title\x07payload\n"
    assert rtk.strip_ansi(text) == "payload\n"


def test_filter_text_strips_ansi_end_to_end():
    raw = "\x1b[33mWARN\x1b[0m line\n\x1b[31mERR\x1b[0m line\n"
    out, stats = rtk.filter_text(raw)
    assert "\x1b" not in out
    assert "WARN line" in out and "ERR line" in out
    assert stats.stdout_bytes_filtered < stats.stdout_bytes_original


# ---------------------------------------------------------------------------
# Repeat collapsing
# ---------------------------------------------------------------------------


def test_collapse_repeats_three_or_more():
    raw = "\n".join(["WARN: rosbags deprecation"] * 5) + "\n"
    out, stats = rtk.filter_text(raw)
    assert "WARN: rosbags deprecation" in out
    assert "(repeated 5x)" in out
    assert stats.repeated_runs_collapsed == 1
    # Only ONE representative line kept, plus the marker.
    assert out.count("WARN: rosbags deprecation") == 1


def test_collapse_repeats_preserves_two_in_a_row():
    # Runs of length 2 should NOT be collapsed (overhead > savings).
    raw = "same line\nsame line\nother\n"
    out, stats = rtk.filter_text(raw)
    assert out.count("same line") == 2
    assert "repeated" not in out
    assert stats.repeated_runs_collapsed == 0


def test_collapse_repeats_multiple_runs():
    raw = (
        "A\nA\nA\nA\n"
        "B\n"
        "C\nC\nC\n"
    )
    out, stats = rtk.filter_text(raw)
    assert stats.repeated_runs_collapsed == 2
    assert "(repeated 4x)" in out
    assert "(repeated 3x)" in out


# ---------------------------------------------------------------------------
# Stack frame dedupe
# ---------------------------------------------------------------------------


def test_dedupe_python_frames_across_retries():
    raw = (
        "Traceback (most recent call last):\n"
        '  File "a.py", line 10, in run\n'
        "    do_it()\n"
        '  File "b.py", line 20, in do_it\n'
        "    raise ValueError(1)\n"
        "ValueError: 1\n"
        "Retrying...\n"
        "Traceback (most recent call last):\n"
        '  File "a.py", line 10, in run\n'
        "    do_it()\n"
        '  File "b.py", line 20, in do_it\n'
        "    raise ValueError(1)\n"
        "ValueError: 1\n"
    )
    out, stats = rtk.filter_text(raw)
    # Both original frame pairs replaced by a (deduped) marker on second pass.
    assert stats.frames_deduped == 2
    assert out.count('File "a.py", line 10, in run (deduped)') == 1
    assert out.count('File "b.py", line 20, in do_it (deduped)') == 1
    # Body lines from the retry copy should be gone.
    assert out.count("do_it()") == 1
    assert out.count("raise ValueError(1)") == 1


# ---------------------------------------------------------------------------
# Byte budget cap
# ---------------------------------------------------------------------------


def test_budget_caps_large_output():
    # Use UNIQUE lines so the dedupe pass doesn't compress away the bulk
    # before the budget cap runs. Each line ~30 B, 2000 lines ≈ 60 KB.
    raw = "".join(f"line {i:05d} token-{i}-unique\n" for i in range(2000))
    out, stats = rtk.filter_text(raw, budget_bytes=4096)
    assert stats.truncated is True
    assert stats.stdout_bytes_filtered <= 4096
    assert "truncated" in out


def test_budget_skipped_when_under_cap():
    raw = "small output\n"
    out, stats = rtk.filter_text(raw, budget_bytes=4096)
    assert stats.truncated is False
    assert out == raw


# ---------------------------------------------------------------------------
# Combined: rosbags-style spam from a real ingestion flow
# ---------------------------------------------------------------------------


def test_combined_reduction_over_80_percent_on_rosbags_spam():
    """Synthetic fixture mimicking a real rosbag scan: 500 duplicate WARNs,
    a repeated traceback, and ANSI color wrappers. Must compress ≥80%.
    """
    warn = "\x1b[33mWARN\x1b[0m rosbags.highlevel: deprecated type map entry foo_msgs/Bar\n"
    traceback = (
        "Traceback (most recent call last):\n"
        '  File "reader.py", line 42, in open_bag\n'
        "    reader._load()\n"
        '  File "reader.py", line 88, in _load\n'
        "    raise RuntimeError('bad header')\n"
        "RuntimeError: bad header\n"
    )
    raw = warn * 500 + traceback * 4 + "\x1b[32mOK\x1b[0m done\n"
    out, stats = rtk.filter_text(raw, budget_bytes=16 * 1024)
    assert stats.reduction_ratio >= 0.80, (
        f"expected >=80% reduction, got {stats.reduction_ratio:.1%}: "
        f"{stats.stdout_bytes_original} -> {stats.stdout_bytes_filtered}"
    )
    assert stats.repeated_runs_collapsed >= 1
    assert stats.frames_deduped >= 1
    assert "\x1b" not in out
    # Still human-readable: the WARN text and OK message survive.
    assert "deprecated type map entry" in out
    assert "OK done" in out


# ---------------------------------------------------------------------------
# Subprocess wrapper + costs.jsonl logging
# ---------------------------------------------------------------------------


def test_run_logs_stdout_bytes_saved_to_costs_file(tmp_path, monkeypatch):
    costs = tmp_path / "costs.jsonl"
    monkeypatch.setattr(rtk, "_costs_path", lambda: costs)

    # Emit a lot of duplicate lines so the filter has something to compress.
    script = 'python3 -c "print(\\"noisy line\\" * 1);' + \
             ''.join(['print(\\"dup\\");' for _ in range(200)]) + '"'
    result = rtk.run(script, apply_filter=True, budget_bytes=4096)
    assert result.returncode == 0
    assert costs.exists()

    records = [json.loads(line) for line in costs.read_text().splitlines()]
    rtk_records = [r for r in records if r.get("kind") == "rtk"]
    assert rtk_records, "no rtk record written"
    rec = rtk_records[-1]
    assert "stdout_bytes_saved" in rec
    assert rec["stdout_bytes_saved"] > 0
    assert rec["reduction_ratio"] > 0.0


def test_run_with_no_rtk_passthrough(tmp_path, monkeypatch):
    """`apply_filter=False` leaves stdout unchanged but still logs a zero-savings row."""
    costs = tmp_path / "costs.jsonl"
    monkeypatch.setattr(rtk, "_costs_path", lambda: costs)
    result = rtk.run(["python3", "-c", "print('hello')"], apply_filter=False)
    assert "hello" in result.stdout
    assert result.stats_stdout.stdout_bytes_saved == 0
    rec = json.loads(costs.read_text().splitlines()[-1])
    assert rec["kind"] == "rtk"
    assert rec["stdout_bytes_saved"] == 0
