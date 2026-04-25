"""D1 — vision-resolution A/B harness."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_vision_mod():
    spec = importlib.util.spec_from_file_location(
        "_compare_opus_vision", ROOT / "scripts" / "compare_opus_vision.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_render_plot_creates_image_and_token(tmp_path):
    mod = _load_vision_mod()
    out = tmp_path / "vision_plot.png"
    img = mod.render_plot_with_secret(out, secret="ANOM_TS=42.5s")
    assert out.exists()
    assert img.size == (mod.CANVAS_W, mod.CANVAS_H)
    # Sanity: PNG is non-trivial size
    assert out.stat().st_size > 5_000


def test_detect_substring_match():
    mod = _load_vision_mod()
    assert mod._detect("I see a note: ANOM_TS=42.5s.") is True
    assert mod._detect("the annotation reads anom_ts=42.5s") is True
    assert mod._detect("there is a note ANOM_TS and 42.5 seconds") is True
    assert mod._detect("just two PWM curves visible") is False
    assert mod._detect("") is False


def test_resize_preserves_aspect_and_caps_long_side():
    mod = _load_vision_mod()
    from PIL import Image
    img = Image.new("RGB", (2400, 1600), color=(255, 255, 255))
    out = mod._resize_to(img, 1568)
    # Long side capped, aspect preserved
    assert max(out.size) == 1568
    # Aspect preserved within 1px rounding tolerance.
    assert abs(out.size[0] / out.size[1] - 2400 / 1600) < 1e-2
    # No upscaling when already smaller than cap
    out2 = mod._resize_to(img, 4000)
    assert out2.size == (2400, 1600)


def test_aggregate_detection_rate():
    mod = _load_vision_mod()
    rows = [
        mod.VisionResult(model="m", seed=0, detected=True, response_excerpt="x",
                         cost_usd=0.1, wall_time_s=5.0, notes="ok"),
        mod.VisionResult(model="m", seed=1, detected=False, response_excerpt="y",
                         cost_usd=0.1, wall_time_s=5.0, notes="ok"),
        mod.VisionResult(model="m", seed=2, detected=True, response_excerpt="z",
                         cost_usd=0.1, wall_time_s=5.0, notes="ok"),
    ]
    agg = mod._aggregate("m", rows)
    assert agg.n_runs == 3
    assert abs(agg.detection_rate - (2 / 3)) < 1e-9
    assert abs(agg.total_cost_usd - 0.30) < 1e-9


def test_aggregate_empty_rows():
    mod = _load_vision_mod()
    agg = mod._aggregate("m", [])
    assert agg.n_runs == 0
    assert agg.detection_rate == 0.0


def test_dry_run_renders_plot_without_api(tmp_path, monkeypatch):
    res = subprocess.run(
        [sys.executable, "scripts/compare_opus_vision.py", "--dry-run"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0, res.stderr
    assert "Dry-run" in res.stdout
    assert "ANOM_TS" in res.stdout


def test_claude_client_resolution_xl_max_side():
    """ClaudeClient learned a third resolution tier for the D1 vision test."""
    from black_box.analysis.claude_client import ClaudeClient
    assert ClaudeClient.RESOLUTION_MAX_SIDE["thumb"] == 800
    assert ClaudeClient.RESOLUTION_MAX_SIDE["hires"] == 1920
    assert ClaudeClient.RESOLUTION_MAX_SIDE["hires_xl"] == 2400
