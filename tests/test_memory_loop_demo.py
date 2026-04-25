"""#76 — visible memory loop end-to-end smoke."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_memory_loop_demo_run_executes(tmp_path):
    out = tmp_path / "demo_out"
    res = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "memory_loop_demo.py"), "--out", str(out)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert res.returncode == 0, f"stdout={res.stdout!r} stderr={res.stderr!r}"
    assert (out / "run1_summary.json").exists()
    assert (out / "run2_summary.json").exists()
    assert (out / "memory_used_panel.json").exists()


def test_run2_promotes_via_tie_break_with_memory(tmp_path):
    out = tmp_path / "demo_out"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "memory_loop_demo.py"), "--out", str(out)],
        cwd=str(ROOT),
        check=True,
        timeout=30,
    )
    panel = json.loads((out / "memory_used_panel.json").read_text(encoding="utf-8"))
    delta = panel["delta_summary"]
    assert delta["with_memory_top"] == "sensor_timeout"
    assert delta["without_memory_top"] == "calibration_drift"
    assert delta["changed"] is True


def test_memory_panel_renders_html():
    from black_box.reporting.memory_panel import render_memory_used_panel
    panel = {
        "title": "Memory used",
        "subtitle": "From a prior session.",
        "evidence_chain": [
            {
                "from_case": "rtk_alpha",
                "prior_kind": "L3 taxonomy frequency",
                "signature": "rtk_carr_soln_none_persistent → sensor_timeout",
                "effect": "Tie-break promoted sensor_timeout over calibration_drift.",
            }
        ],
        "delta_summary": {
            "without_memory_top": "calibration_drift",
            "with_memory_top": "sensor_timeout",
            "changed": True,
        },
        "primed_prompt_block_preview": "Historical priors for platform `rover_av` ...",
    }
    html = render_memory_used_panel(panel)
    for needle in ["Memory used", "rtk_alpha", "calibration_drift", "sensor_timeout", "✓"]:
        assert needle in html
