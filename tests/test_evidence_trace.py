"""#77 — glass-box evidence trace structure + HTML rendering."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from black_box.reporting.trace import (
    ConfidenceCalibration,
    CostStep,
    DiscardedHypothesis,
    EvidenceItem,
    GateDecision,
    Trace,
    cost_steps_from_jsonl,
    render_trace_html,
    trace_from_artifacts,
)


def test_cost_steps_from_jsonl_filters_by_job_id(tmp_path):
    p = tmp_path / "costs.jsonl"
    p.write_text(
        json.dumps({"job_id": "j1", "prompt_kind": "summary", "cached_input_tokens": 1024, "uncached_input_tokens": 200, "output_tokens": 50, "usd_cost": 0.012}) + "\n" +
        json.dumps({"job_id": "j2", "prompt_kind": "deep", "uncached_input_tokens": 800, "output_tokens": 300, "usd_cost": 0.045}) + "\n" +
        json.dumps({"job_id": "j1", "prompt_kind": "deep", "cached_input_tokens": 1024, "uncached_input_tokens": 50, "output_tokens": 1200, "usd_cost": 0.103}) + "\n"
    )
    rows = cost_steps_from_jsonl(p, "j1")
    assert len(rows) == 2
    assert all(isinstance(r, CostStep) for r in rows)
    assert rows[0].step_name == "summary"
    assert rows[1].usd_cost == 0.103


def test_cost_steps_tolerant_to_missing_or_garbage(tmp_path):
    p = tmp_path / "costs.jsonl"
    p.write_text("not json at all\n" + json.dumps({"job_id": "j1", "usd_cost": 0.01}) + "\n")
    rows = cost_steps_from_jsonl(p, "j1")
    assert len(rows) == 1


def test_trace_from_artifacts_with_manifest(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "costs.jsonl").write_text(
        json.dumps({"job_id": "jobX", "prompt_kind": "deep", "cached_input_tokens": 4096, "output_tokens": 800, "usd_cost": 0.5}) + "\n"
    )
    manifest = {
        "run_provenance": "live",
        "evidence_used": [
            {"kind": "telemetry_window", "source_path": "/mnt/session/uploads/2_sensors.bag::/imu/data", "t_ns": 1700000000_000_000_000, "snippet": "imu freeze 1.4s", "provenance": "live"},
            {"kind": "frame", "source_path": "frames/cam1/00012.jpg", "t_ns": 1700000001_500_000_000, "snippet": "horizon roll 1.8°", "provenance": "live"},
        ],
        "discarded": [
            {"label": "tunnel-induced rtk loss", "reason": "carr_soln=none predates tunnel by 43min", "confidence_at_drop": 0.4},
        ],
        "gate": {"outcome": "pass", "rationale": "min_evidence=2 met across telemetry+frame", "min_evidence": 2},
        "confidence": {"score": 0.86, "raises": ["second clean run on the same bag"], "lowers": ["sensor_timeout window > 30s"]},
    }
    t = trace_from_artifacts("jobX", repo_root=tmp_path, manifest=manifest)
    assert t.run_provenance == "live"
    assert len(t.evidence_used) == 2
    assert t.gate.outcome == "pass"
    assert t.confidence.score == 0.86
    assert t.total_usd() == 0.5


def test_render_trace_html_contains_all_sections():
    t = Trace(
        job_id="jobY",
        run_provenance="replay",
        evidence_used=[EvidenceItem(kind="frame", source_path="f.jpg", t_ns=1, snippet="x")],
        discarded=[DiscardedHypothesis(label="alt", reason="conflicts with telemetry", confidence_at_drop=0.3)],
        gate=GateDecision(outcome="partial", rationale="only 1 frame supports it", min_evidence=2),
        cost_steps=[CostStep(step_name="summary", cached_input_tokens=1024, uncached_input_tokens=200, output_tokens=80, usd_cost=0.02)],
        confidence=ConfidenceCalibration(score=0.62, raises=["second corroborating frame"], lowers=["telemetry refutation"]),
    )
    html = render_trace_html(t)
    for needle in ["Evidence used", "Discarded hypotheses", "Grounding gate", "Per-step cost", "Confidence calibration", "prov-replay", "$0.0200"]:
        assert needle in html


def test_render_trace_html_sober_when_only_costs():
    t = Trace(job_id="jobZ", cost_steps=[CostStep(step_name="x", uncached_input_tokens=100, output_tokens=50, usd_cost=0.005)])
    html = render_trace_html(t)
    assert "No structured evidence manifest available" in html
    assert "Per-step cost" in html
