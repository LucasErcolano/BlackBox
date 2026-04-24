"""Smoke tests for the Black Box FastAPI UI."""
from __future__ import annotations

import io
import json
import re
import time

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
# /report/{job_id} — rendered markdown page + PDF variant (issue #28)
# ---------------------------------------------------------------------------
def test_report_renders_markdown_html(tmp_path, monkeypatch):
    """Default GET serves an HTML shell that renders the MD via marked.js."""
    monkeypatch.setattr(ui_app, "REPORTS_DIR", tmp_path)
    job_id = "renderjob"
    md_body = (
        "# Black Box — Forensic Report\n\n"
        "**Case:** `ui_renderjob`\n\n"
        "> pid_saturation detected at t=1.82s\n"
    )
    (tmp_path / f"{job_id}.md").write_text(md_body)

    client = TestClient(app)
    r = client.get(f"/report/{job_id}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    # marked.js is wired into the page
    assert "marked" in r.text
    # The raw markdown is embedded for client-side rendering
    assert "pid_saturation detected" in r.text
    # Secondary PDF download button is present
    assert f"/report/{job_id}?format=pdf" in r.text
    assert "Download PDF" in r.text


def test_report_pdf_variant_returns_pdf_bytes(tmp_path, monkeypatch):
    """?format=pdf serves pre-built PDF with application/pdf content-type."""
    monkeypatch.setattr(ui_app, "REPORTS_DIR", tmp_path)
    job_id = "pdfjob"
    # Minimal valid PDF header — enough for the route to echo the bytes.
    pdf_bytes = b"%PDF-1.4\n%EOF\n"
    (tmp_path / f"{job_id}.pdf").write_bytes(pdf_bytes)

    client = TestClient(app)
    r = client.get(f"/report/{job_id}?format=pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")


def test_report_pdf_variant_missing_404s(tmp_path, monkeypatch):
    """?format=pdf with no pre-built PDF and no JSON payload -> 404."""
    monkeypatch.setattr(ui_app, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(ui_app, "JOBS_DIR", tmp_path)

    client = TestClient(app)
    r = client.get("/report/nope-not-here?format=pdf")
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


# ---------------------------------------------------------------------------
# P2 progress page — sticky header, stage pills, live $ counter (issue #27)
# ---------------------------------------------------------------------------
def test_status_sticky_header_has_case_and_elapsed(tmp_path, monkeypatch):
    """Sticky header must render the case name + an elapsed-time readout."""
    monkeypatch.setattr(ui_app, "JOBS_DIR", tmp_path)
    job_id = "hdrjob"
    (tmp_path / f"{job_id}.json").write_text(json.dumps({
        "job_id": job_id,
        "stage": "analyzing",
        "label": "Claude is reviewing evidence",
        "progress": 0.4,
        "mode": "post_mortem",
        "upload": "nao_fall.bag",
        "case_name": "nao_fall.bag",
        "created_at": time.time() - 73,  # 1m13s ago
        "reasoning_buffer": ["[analyzing] working..."],
        "has_diff": False,
    }))
    client = TestClient(app)
    r = client.get(f"/status/{job_id}")
    assert r.status_code == 200
    assert "sticky-header" in r.text
    assert "nao_fall.bag" in r.text
    # Elapsed renders as mm:ss and carries the numeric seconds in a data attr.
    assert re.search(r'data-elapsed-seconds="\d+"', r.text)
    assert re.search(r"\d{2}:\d{2}", r.text)


def test_status_stage_pills_render_exactly_one_active(tmp_path, monkeypatch):
    """Three pills (ingest / analyze / report); exactly one is active."""
    monkeypatch.setattr(ui_app, "JOBS_DIR", tmp_path)
    job_id = "pilljob"
    (tmp_path / f"{job_id}.json").write_text(json.dumps({
        "job_id": job_id,
        "stage": "analyzing",
        "label": "Claude is reviewing evidence",
        "progress": 0.4,
        "mode": "post_mortem",
        "upload": "case.bag",
        "case_name": "case.bag",
        "reasoning_buffer": ["[analyzing] ..."],
        "has_diff": False,
    }))
    client = TestClient(app)
    r = client.get(f"/status/{job_id}")
    assert r.status_code == 200
    # All three pill names render.
    for name in ("ingest", "analyze", "report"):
        assert f'data-pill="{name}"' in r.text
    # Exactly one `pill active` badge — not zero, not two.
    active_count = len(re.findall(r'class="pill active"', r.text))
    assert active_count == 1, f"expected 1 active pill, got {active_count}"
    # ...and it's the 'analyze' one for stage='analyzing'.
    assert re.search(r'class="pill active" data-pill="analyze"', r.text)


def test_status_cost_counter_renders_dollar_amount(tmp_path, monkeypatch):
    """Cost counter must render a $ number, with data-source marking empty ledgers."""
    monkeypatch.setattr(ui_app, "JOBS_DIR", tmp_path)
    # Point the cost ledger at an empty tmp dir so the stub render path is covered.
    monkeypatch.setattr(ui_app, "DATA_DIR", tmp_path)
    job_id = "costjob"
    (tmp_path / f"{job_id}.json").write_text(json.dumps({
        "job_id": job_id,
        "stage": "analyzing",
        "label": "Claude is reviewing evidence",
        "progress": 0.4,
        "mode": "post_mortem",
        "upload": "case.bag",
        "case_name": "case.bag",
        "reasoning_buffer": ["[analyzing] ..."],
        "has_diff": False,
    }))
    client = TestClient(app)
    r = client.get(f"/status/{job_id}")
    assert r.status_code == 200
    # Empty ledger → $0.00 with data-source="empty".
    assert 'data-source="empty"' in r.text
    assert "$0.00" in r.text

    # Populate the ledger and reassert — the number must update and source flips.
    (tmp_path / "costs.jsonl").write_text(
        json.dumps({"usd_cost": 1.23, "prompt_kind": "x"}) + "\n"
        + json.dumps({"usd_cost": 0.77, "prompt_kind": "y"}) + "\n"
    )
    r2 = client.get(f"/status/{job_id}")
    assert r2.status_code == 200
    assert 'data-source="session"' in r2.text
    assert "$2.00" in r2.text


def test_index_has_dropzone_and_hero_cards():
    """Landing page must expose the drop zone UX and all three hero case cards."""
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    # Drop zone surface
    assert 'id="dropzone"' in r.text
    assert 'evidence upload' in r.text
    # Existing upload wiring preserved
    assert 'hx-post="/analyze"' in r.text
    assert 'multipart/form-data' in r.text
    # Three hero cards (one per case)
    assert 'hx-get="/case/sanfer_tunnel"' in r.text
    assert 'hx-get="/case/car_1"' in r.text
    assert 'hx-get="/case/boat_lidar"' in r.text
    # marked.js script present for inline markdown render
    assert 'marked.min.js' in r.text


def test_index_has_no_gradients():
    """NTSB aesthetic discipline: no gradient fills in the landing HTML."""
    client = TestClient(app)
    r = client.get("/")
    assert 'linear-gradient' not in r.text
    assert 'radial-gradient' not in r.text


def test_style_css_has_no_gradients():
    """Static stylesheet must stay gradient-free (NTSB discipline)."""
    css = (ui_app.BASE_DIR / "static" / "style.css").read_text()
    assert 'linear-gradient' not in css
    assert 'radial-gradient' not in css


def test_case_route_sanfer():
    client = TestClient(app)
    r = client.get("/case/sanfer_tunnel")
    assert r.status_code == 200
    assert 'sanfer_tunnel' in r.text
    # MD contents pass through as a data attribute for marked.js to parse
    assert 'data-markdown=' in r.text
    assert 'RTCM' in r.text or 'carr_soln' in r.text


def test_case_route_car_1():
    client = TestClient(app)
    r = client.get("/case/car_1")
    assert r.status_code == 200
    assert 'car_1' in r.text
    assert 'data-markdown=' in r.text


def test_case_route_boat_lidar():
    client = TestClient(app)
    r = client.get("/case/boat_lidar")
    assert r.status_code == 200
    assert 'boat_lidar' in r.text
    assert 'data-markdown=' in r.text


def test_case_route_unknown_slug_404s():
    """Slug whitelist must reject arbitrary paths (no file-read primitive)."""
    client = TestClient(app)
    r = client.get("/case/../../../etc/passwd")
    assert r.status_code in (404, 400)
    r = client.get("/case/not_a_real_case")
    assert r.status_code == 404


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


# ---- HITL approve/reject gate (#23) ----------------------------------------

def _seed_patch(tmp_path, monkeypatch, job_id="gatejob"):
    monkeypatch.setattr(ui_app, "PATCHES_DIR", tmp_path)
    (tmp_path / f"{job_id}.json").write_text(json.dumps({
        "file_path": "src/pid.cpp",
        "old": "integral += error;\n",
        "new": "integral += error;\nintegral = clamp(integral, -1, 1);\n",
    }))
    return job_id


def test_diff_pending_shows_approve_and_reject_buttons(tmp_path, monkeypatch):
    job_id = _seed_patch(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.get(f"/diff/{job_id}")
    assert r.status_code == 200
    assert 'data-status="pending"' in r.text
    assert "HUMAN APPROVAL REQUIRED" in r.text
    assert f'action="/decide/{job_id}"' in r.text
    assert 'value="approve"' in r.text
    assert 'value="reject"' in r.text


def test_decide_approve_writes_decision_and_renders_banner(tmp_path, monkeypatch):
    job_id = _seed_patch(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.post(f"/decide/{job_id}", data={"decision": "approve", "note": "looks safe"})
    assert r.status_code == 200
    assert "PATCH APPROVED" in r.text
    assert "looks safe" in r.text
    saved = json.loads((tmp_path / f"{job_id}.decision.json").read_text())
    assert saved["status"] == "approved"
    assert saved["note"] == "looks safe"
    # Subsequent GET /diff reflects the locked state and drops the form.
    r2 = client.get(f"/diff/{job_id}")
    assert 'data-status="approved"' in r2.text
    assert 'action="/decide/' not in r2.text


def test_decide_reject_blocks_and_banners(tmp_path, monkeypatch):
    job_id = _seed_patch(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.post(f"/decide/{job_id}", data={"decision": "reject", "note": "scope too broad"})
    assert r.status_code == 200
    assert "PATCH REJECTED" in r.text
    saved = json.loads((tmp_path / f"{job_id}.decision.json").read_text())
    assert saved["status"] == "rejected"


def test_decide_is_one_shot_and_409s_on_redecision(tmp_path, monkeypatch):
    job_id = _seed_patch(tmp_path, monkeypatch)
    client = TestClient(app)
    client.post(f"/decide/{job_id}", data={"decision": "approve"})
    r = client.post(f"/decide/{job_id}", data={"decision": "reject"})
    assert r.status_code == 409


def test_decide_rejects_invalid_decision_value(tmp_path, monkeypatch):
    job_id = _seed_patch(tmp_path, monkeypatch)
    client = TestClient(app)
    r = client.post(f"/decide/{job_id}", data={"decision": "maybe"})
    assert r.status_code == 400


def test_decide_404s_when_patch_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ui_app, "PATCHES_DIR", tmp_path)
    client = TestClient(app)
    r = client.post("/decide/no-such-job", data={"decision": "approve"})
    assert r.status_code == 404
