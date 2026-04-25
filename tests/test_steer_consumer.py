# SPDX-License-Identifier: MIT
"""Live-worker steering consumer (#129).

PR #105 shipped the producer side: POST /steer/{job_id} writes to a
JSONL audit. This file proves the consumer side: between agent-stream
events, the live worker drains new steer entries and forwards them to
ForensicSession.steer().
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


class _FakeSession:
    """Drop-in for ForensicSession in _run_pipeline_real."""

    def __init__(self) -> None:
        self.session_id = "fake_session"
        self.steers: list[str] = []
        self._events: list[dict] = [
            {"type": "agent.thinking", "text": "checking carrier-phase timeline"},
            {"type": "agent.tool_call", "name": "read_telemetry"},
            {"type": "agent.thinking", "text": "examining REL_POS_VALID flag"},
            {"type": "agent.message", "text": "done"},
        ]

    def stream(self):
        for ev in self._events:
            yield ev

    def steer(self, message: str) -> None:
        self.steers.append(message)

    def finalize(self) -> dict:
        return {
            "hypotheses": [{"bug_class": "sensor_timeout"}],
            "patch_proposal": "",
        }


class _FakeAgent:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.session = _FakeSession()

    def open_session(self, *, bag_path: Path, case_key: str):
        return self.session


def test_live_worker_drains_steer_jsonl_into_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from black_box.ui import app as ui_app

    monkeypatch.setattr(ui_app, "JOBS_DIR", tmp_path)
    monkeypatch.setattr(ui_app, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(ui_app, "PATCHES_DIR", tmp_path)

    fake_agent = _FakeAgent()
    monkeypatch.setattr(
        "black_box.analysis.managed_agent.ForensicAgent",
        lambda *a, **kw: fake_agent,
    )
    monkeypatch.setattr(
        "black_box.analysis.managed_agent.ForensicAgentConfig",
        lambda *a, **kw: object(),
    )
    monkeypatch.setattr(
        "black_box.reporting.build_report",
        lambda **kw: kw["out_pdf"].write_text("# stub report"),
    )

    from black_box.ingestion.manifest import Manifest, TopicInfo
    monkeypatch.setattr(
        "black_box.ingestion.manifest.build_manifest",
        lambda *a, **kw: Manifest(
            root=tmp_path,
            session_key="fake",
            bags=[tmp_path / "fake.bag"],
            duration_s=1.0,
            t_start_ns=0,
            t_end_ns=10**9,
            cameras=[TopicInfo(topic="/cam1", msgtype="sensor_msgs/Image", count=10, kind="camera")],
        ),
    )

    job_id = "jobsteer"
    upload = tmp_path / "fake.bag"
    upload.write_bytes(b"")

    steer_path = tmp_path / f"{job_id}.steer.jsonl"
    steer_path.write_text(
        json.dumps({"message": "focus on RTK degradation window before the tunnel", "ts": 0}) + "\n"
    )

    ui_app._run_pipeline_real(job_id, upload, "post_mortem")

    assert fake_agent.session.steers == ["focus on RTK degradation window before the tunnel"], (
        f"expected one steer forwarded; got {fake_agent.session.steers}"
    )
    status = json.loads((tmp_path / f"{job_id}.json").read_text())
    buf = "\n".join(status["reasoning_buffer"])
    assert "[steer] -> agent: focus on RTK degradation" in buf, buf


def test_live_worker_no_steer_file_no_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from black_box.ui import app as ui_app

    monkeypatch.setattr(ui_app, "JOBS_DIR", tmp_path)
    monkeypatch.setattr(ui_app, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(ui_app, "PATCHES_DIR", tmp_path)

    fake_agent = _FakeAgent()
    monkeypatch.setattr(
        "black_box.analysis.managed_agent.ForensicAgent",
        lambda *a, **kw: fake_agent,
    )
    monkeypatch.setattr(
        "black_box.analysis.managed_agent.ForensicAgentConfig",
        lambda *a, **kw: object(),
    )
    monkeypatch.setattr(
        "black_box.reporting.build_report",
        lambda **kw: kw["out_pdf"].write_text("# stub report"),
    )

    from black_box.ingestion.manifest import Manifest, TopicInfo
    monkeypatch.setattr(
        "black_box.ingestion.manifest.build_manifest",
        lambda *a, **kw: Manifest(
            root=tmp_path,
            session_key="fake",
            bags=[tmp_path / "fake.bag"],
            duration_s=1.0,
            t_start_ns=0,
            t_end_ns=10**9,
            cameras=[TopicInfo(topic="/cam1", msgtype="sensor_msgs/Image", count=10, kind="camera")],
        ),
    )

    job_id = "jobnone"
    upload = tmp_path / "fake.bag"
    upload.write_bytes(b"")

    ui_app._run_pipeline_real(job_id, upload, "post_mortem")

    assert fake_agent.session.steers == []


def test_live_worker_drains_steer_added_mid_stream(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Steer file written after stream starts is still picked up before stream ends."""
    from black_box.ui import app as ui_app

    monkeypatch.setattr(ui_app, "JOBS_DIR", tmp_path)
    monkeypatch.setattr(ui_app, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr(ui_app, "PATCHES_DIR", tmp_path)

    job_id = "jobmid"
    steer_path = tmp_path / f"{job_id}.steer.jsonl"

    class _MidStreamSession(_FakeSession):
        def __init__(self, steer_target: Path) -> None:
            super().__init__()
            self._target = steer_target

        def stream(self):
            for i, ev in enumerate(self._events):
                if i == 1:
                    self._target.write_text(
                        json.dumps({"message": "look at the second window", "ts": 1}) + "\n"
                    )
                yield ev

    fake_agent = _FakeAgent()
    fake_agent.session = _MidStreamSession(steer_path)
    monkeypatch.setattr(
        "black_box.analysis.managed_agent.ForensicAgent",
        lambda *a, **kw: fake_agent,
    )
    monkeypatch.setattr(
        "black_box.analysis.managed_agent.ForensicAgentConfig",
        lambda *a, **kw: object(),
    )
    monkeypatch.setattr(
        "black_box.reporting.build_report",
        lambda **kw: kw["out_pdf"].write_text("# stub report"),
    )

    from black_box.ingestion.manifest import Manifest, TopicInfo
    monkeypatch.setattr(
        "black_box.ingestion.manifest.build_manifest",
        lambda *a, **kw: Manifest(
            root=tmp_path,
            session_key="fake",
            bags=[tmp_path / "fake.bag"],
            duration_s=1.0,
            t_start_ns=0,
            t_end_ns=10**9,
            cameras=[TopicInfo(topic="/cam1", msgtype="sensor_msgs/Image", count=10, kind="camera")],
        ),
    )

    upload = tmp_path / "fake.bag"
    upload.write_bytes(b"")
    ui_app._run_pipeline_real(job_id, upload, "post_mortem")

    assert fake_agent.session.steers == ["look at the second window"], (
        f"steer added mid-stream should be drained; got {fake_agent.session.steers}"
    )
