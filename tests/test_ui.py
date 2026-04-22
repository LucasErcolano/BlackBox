"""Smoke tests for the Black Box FastAPI UI."""
from __future__ import annotations

import io

from fastapi.testclient import TestClient

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


def test_status_unknown_job_404s():
    client = TestClient(app)
    r = client.get("/status/does-not-exist")
    assert r.status_code == 404


def test_report_missing_404s():
    client = TestClient(app)
    r = client.get("/report/does-not-exist")
    assert r.status_code == 404
