"""Smoke tests for the Black Box FastAPI UI."""
from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient

from black_box.ui import app as ui_app
from black_box.ui.app import app


def test_index_renders():
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "Black Box" in r.text
    assert "hx-post" in r.text  # HTMX form wired


def test_analyze_creates_job():
    client = TestClient(app)
    dummy = io.BytesIO(b"fake-bag-bytes")
    r = client.post(
        "/analyze",
        files={"file": ("run.bag", dummy, "application/octet-stream")},
        data={"mode": "post_mortem"},
    )
    assert r.status_code == 200
    # progress fragment carries the job id in its polling URL
    assert "/status/" in r.text
    assert "stage-label" in r.text or "progress-card" in r.text


def test_status_renders_reasoning_buffer(tmp_path, monkeypatch):
    """Status fragment should render every line of the streaming buffer."""
    monkeypatch.setattr(ui_app, "JOBS_DIR", tmp_path)
    job_id = "bufjob"
    (tmp_path / f"{job_id}.json").write_text(json.dumps({
        "job_id": job_id,
        "stage": "analyzing",
        "label": "Claude is reviewing evidence",
        "progress": 0.5,
        "mode": "post_mortem",
        "reasoning_buffer": [
            "[analyzing] Pulled 5-camera composite.",
            "[analyzing] IMU pitch slope = -0.42 rad/s.",
        ],
        "has_diff": False,
    }))
    client = TestClient(app)
    r = client.get(f"/status/{job_id}")
    assert r.status_code == 200
    assert "5-camera composite" in r.text
    assert "-0.42 rad/s" in r.text
    # Cursor is present while streaming
    assert "cursor" in r.text


def test_status_done_state_shows_diff_and_report_links(tmp_path, monkeypatch):
    monkeypatch.setattr(ui_app, "JOBS_DIR", tmp_path)
    job_id = "donejob"
    (tmp_path / f"{job_id}.json").write_text(json.dumps({
        "job_id": job_id,
        "stage": "done",
        "label": "Complete",
        "progress": 1.0,
        "mode": "post_mortem",
        "reasoning_buffer": ["[done] Root cause: pid_saturation."],
        "has_diff": True,
    }))
    client = TestClient(app)
    r = client.get(f"/status/{job_id}")
    assert r.status_code == 200
    assert f"/diff/{job_id}" in r.text
    assert f"/report/{job_id}" in r.text


def test_diff_route_renders_patch(tmp_path, monkeypatch):
    monkeypatch.setattr(ui_app, "PATCHES_DIR", tmp_path)
    job_id = "diffjob"
    (tmp_path / f"{job_id}.json").write_text(json.dumps({
        "file_path": "src/pid.cpp",
        "old": "integral += error;\n",
        "new": "integral += error;\nintegral = clamp(integral, -1, 1);\n",
    }))
    client = TestClient(app)
    r = client.get(f"/diff/{job_id}")
    assert r.status_code == 200
    assert "src/pid.cpp" in r.text
    assert "clamp(integral" in r.text
    assert "BLACK BOX — FORENSIC DIFF" in r.text


def test_diff_route_404_for_missing_patch():
    client = TestClient(app)
    r = client.get("/diff/no-such-job")
    assert r.status_code == 404


def test_status_unknown_job_404s():
    client = TestClient(app)
    r = client.get("/status/does-not-exist")
    assert r.status_code == 404


def test_report_missing_404s():
    client = TestClient(app)
    r = client.get("/report/does-not-exist")
    assert r.status_code == 404
