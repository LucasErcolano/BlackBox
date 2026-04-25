"""#85 — POST /steer/{job_id} smoke."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Re-route DATA_DIR / JOBS_DIR before app import so the queue lives under tmp_path.
    monkeypatch.setenv("BLACKBOX_DATA_ROOT", str(tmp_path))
    import importlib

    import black_box.ui.app as app_mod
    importlib.reload(app_mod)
    # Override paths post-reload — the module computes them at import time.
    app_mod.DATA_DIR = tmp_path
    app_mod.JOBS_DIR = tmp_path / "jobs"
    app_mod.JOBS_DIR.mkdir(parents=True, exist_ok=True)

    yield TestClient(app_mod.app), app_mod


def _write_job(app_mod, job_id: str, stage: str) -> None:
    p = app_mod.JOBS_DIR / f"{job_id}.json"
    p.write_text(json.dumps({"job_id": job_id, "stage": stage}))


def test_steer_rejects_unknown_job(client):
    c, _ = client
    r = c.post("/steer/nope", data={"message": "anything"})
    assert r.status_code == 404


def test_steer_rejects_completed_job(client):
    c, app_mod = client
    _write_job(app_mod, "j1", "done")
    r = c.post("/steer/j1", data={"message": "too late"})
    assert r.status_code == 409


def test_steer_rejects_empty_message(client):
    c, app_mod = client
    _write_job(app_mod, "j1", "analyzing")
    r = c.post("/steer/j1", data={"message": "   "})
    assert r.status_code == 400


def test_steer_rejects_oversized(client):
    c, app_mod = client
    _write_job(app_mod, "j1", "analyzing")
    r = c.post("/steer/j1", data={"message": "x" * 1001})
    assert r.status_code == 400


def test_steer_appends_to_jsonl_and_returns_html(client):
    c, app_mod = client
    _write_job(app_mod, "j1", "analyzing")
    r = c.post(
        "/steer/j1",
        data={"message": "focus on RTK degradation window before the tunnel", "operator": "lucas"},
    )
    assert r.status_code == 200
    assert "steer queued" in r.text
    log = (app_mod.JOBS_DIR / "j1.steer.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 1
    entry = json.loads(log[0])
    assert "RTK degradation" in entry["message"]
    assert entry["operator"] == "lucas"
    assert entry["stage_when_sent"] == "analyzing"


def test_steer_history_renders_after_post(client):
    c, app_mod = client
    _write_job(app_mod, "j1", "analyzing")
    c.post("/steer/j1", data={"message": "first steer"})
    c.post("/steer/j1", data={"message": "second steer"})
    r = c.get("/steer/j1")
    assert r.status_code == 200
    assert "first steer" in r.text and "second steer" in r.text
