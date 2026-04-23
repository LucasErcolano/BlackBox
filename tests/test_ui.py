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


# ---------------------------------------------------------------------------
# Real-pipeline dispatch
# ---------------------------------------------------------------------------
def test_real_pipeline_disabled_by_default(monkeypatch):
    """No env flags -> stub. Guards demo day against accidental live calls."""
    monkeypatch.delenv("BLACKBOX_REAL_PIPELINE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert ui_app._real_pipeline_enabled() is False


def test_real_pipeline_disabled_without_key(monkeypatch):
    monkeypatch.setenv("BLACKBOX_REAL_PIPELINE", "1")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert ui_app._real_pipeline_enabled() is False


def test_real_pipeline_enabled_when_both_set(monkeypatch):
    monkeypatch.setenv("BLACKBOX_REAL_PIPELINE", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert ui_app._real_pipeline_enabled() is True


def test_fmt_stream_event_variants():
    """The real-pipeline formatter must cover every type emitted by session.stream()."""
    assert ui_app._fmt_stream_event({"type": "reasoning"}) == "[reasoning] (thinking...)"

    tool_line = ui_app._fmt_stream_event(
        {"type": "tool_call", "payload": {"name": "bash", "input": {"command": "ls"}}}
    )
    assert tool_line is not None and tool_line.startswith("[tool:bash]")

    result_line = ui_app._fmt_stream_event(
        {"type": "tool_result", "payload": {"text": "ok\nfine", "is_error": False}}
    )
    assert result_line is not None and "ok" in result_line and "⏎" in result_line

    err_line = ui_app._fmt_stream_event(
        {"type": "tool_result", "payload": {"text": "boom", "is_error": True}}
    )
    assert err_line is not None and err_line.startswith("[result] ERR ")

    asst_line = ui_app._fmt_stream_event(
        {"type": "assistant", "payload": {"text": "done."}}
    )
    assert asst_line == "[assistant] done."

    # chatty / unknown events filtered out
    assert ui_app._fmt_stream_event({"type": "status", "payload": {"state": "span.tool_use"}}) is None
    assert ui_app._fmt_stream_event({"type": "unknown"}) is None


def test_analyze_routes_to_stub_by_default(monkeypatch, tmp_path):
    """POST /analyze with no real-pipeline env must schedule the stub worker."""
    monkeypatch.setattr(ui_app, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(ui_app, "JOBS_DIR", tmp_path)
    monkeypatch.delenv("BLACKBOX_REAL_PIPELINE", raising=False)

    scheduled: list[tuple] = []

    def _fake_add_task(self, fn, *args, **kwargs):
        scheduled.append((fn.__name__, args, kwargs))

    # FastAPI BackgroundTasks is instantiated per request — patch it where the
    # app imports it.
    import fastapi
    orig = fastapi.BackgroundTasks.add_task
    fastapi.BackgroundTasks.add_task = _fake_add_task  # type: ignore[assignment]
    try:
        client = TestClient(app)
        r = client.post(
            "/analyze",
            files={"file": ("run.bag", io.BytesIO(b"fake"), "application/octet-stream")},
            data={"mode": "post_mortem"},
        )
    finally:
        fastapi.BackgroundTasks.add_task = orig  # type: ignore[assignment]

    assert r.status_code == 200
    assert len(scheduled) == 1
    assert scheduled[0][0] == "_run_pipeline_stub"


def test_analyze_routes_to_real_pipeline_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setattr(ui_app, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(ui_app, "JOBS_DIR", tmp_path)
    monkeypatch.setenv("BLACKBOX_REAL_PIPELINE", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    scheduled: list[tuple] = []

    def _fake_add_task(self, fn, *args, **kwargs):
        scheduled.append((fn.__name__, args, kwargs))

    import fastapi
    orig = fastapi.BackgroundTasks.add_task
    fastapi.BackgroundTasks.add_task = _fake_add_task  # type: ignore[assignment]
    try:
        client = TestClient(app)
        r = client.post(
            "/analyze",
            files={"file": ("run.bag", io.BytesIO(b"fake"), "application/octet-stream")},
            data={"mode": "post_mortem"},
        )
    finally:
        fastapi.BackgroundTasks.add_task = orig  # type: ignore[assignment]

    assert r.status_code == 200
    assert len(scheduled) == 1
    assert scheduled[0][0] == "_run_pipeline_real"
