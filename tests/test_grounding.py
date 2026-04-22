"""Tests for the deterministic grounding gate."""

from __future__ import annotations

import copy

import pytest

from black_box.analysis.grounding import (
    NO_ANOMALY_PATCH,
    GroundingThresholds,
    _accept_hypothesis,
    ground_post_mortem,
    ground_scenario_mining,
)
from black_box.analysis.schemas import (
    Evidence,
    Hypothesis,
    Moment,
    PostMortemReport,
    ScenarioMiningReport,
    TimelineEvent,
)


def _ev(source: str, snippet: str = "x", topic: str = "/topic") -> Evidence:
    return Evidence(source=source, topic_or_file=topic, snippet=snippet)


def _hyp(
    bug_class: str = "pid_saturation",
    confidence: float = 0.8,
    evidence: list[Evidence] | None = None,
    summary: str = "s",
    patch_hint: str = "clamp",
) -> Hypothesis:
    return Hypothesis(
        bug_class=bug_class,
        confidence=confidence,
        summary=summary,
        evidence=evidence if evidence is not None else [_ev("telemetry"), _ev("code")],
        patch_hint=patch_hint,
    )


def _report(hypotheses: list[Hypothesis], root_cause_idx: int = 0) -> PostMortemReport:
    return PostMortemReport(
        timeline=[TimelineEvent(t_ns=1, label="start", cross_view=False)],
        hypotheses=hypotheses,
        root_cause_idx=root_cause_idx,
        patch_proposal="--- original\n+++ patched\n",
    )


def test_high_confidence_multi_source_accepted():
    h = _hyp(
        confidence=0.9,
        evidence=[_ev("telemetry"), _ev("code"), _ev("camera")],
    )
    out = ground_post_mortem(_report([h]))
    assert len(out.hypotheses) == 1
    assert out.hypotheses[0].confidence == 0.9
    assert out.patch_proposal.startswith("---")
    assert out.root_cause_idx == 0


@pytest.mark.parametrize(
    "confidence,expected",
    [(0.3, False), (0.39, False), (0.4, True), (0.5, True), (0.95, True)],
)
def test_confidence_threshold(confidence, expected):
    h = _hyp(confidence=confidence)
    assert _accept_hypothesis(h, GroundingThresholds()) is expected


def test_single_evidence_rejected():
    h = _hyp(evidence=[_ev("telemetry")])
    out = ground_post_mortem(_report([h]))
    assert out.hypotheses == []
    assert out.patch_proposal == NO_ANOMALY_PATCH


def test_other_bug_class_requires_three_evidence():
    h_two = _hyp(bug_class="other", evidence=[_ev("telemetry"), _ev("code")])
    out = ground_post_mortem(_report([h_two]))
    assert out.hypotheses == []
    assert out.patch_proposal == NO_ANOMALY_PATCH

    h_three = _hyp(
        bug_class="other",
        evidence=[_ev("telemetry"), _ev("code"), _ev("camera")],
    )
    out_ok = ground_post_mortem(_report([h_three]))
    assert len(out_ok.hypotheses) == 1


def test_same_source_evidence_rejected():
    h = _hyp(evidence=[_ev("telemetry", snippet="a"), _ev("telemetry", snippet="b")])
    out = ground_post_mortem(_report([h]))
    assert out.hypotheses == []
    assert out.patch_proposal == NO_ANOMALY_PATCH


def test_all_rejected_yields_no_anomaly_shell():
    hs = [
        _hyp(confidence=0.2),
        _hyp(evidence=[_ev("telemetry")]),
        _hyp(bug_class="other", evidence=[_ev("telemetry"), _ev("code")]),
    ]
    out = ground_post_mortem(_report(hs, root_cause_idx=2))
    assert out.hypotheses == []
    assert out.patch_proposal == NO_ANOMALY_PATCH
    assert out.root_cause_idx == 0
    assert len(out.timeline) == 1


def test_mixed_accept_reject_sorted_by_confidence():
    accepted_low = _hyp(confidence=0.5)
    accepted_high = _hyp(confidence=0.85)
    rejected = _hyp(confidence=0.2)
    out = ground_post_mortem(_report([accepted_low, rejected, accepted_high]))
    assert len(out.hypotheses) == 2
    assert out.hypotheses[0].confidence == 0.85
    assert out.hypotheses[1].confidence == 0.5
    assert out.root_cause_idx == 0
    assert out.patch_proposal.startswith("---")


def test_scenario_mining_drops_info_keeps_anomalous():
    moments = [
        Moment(
            t_ns=1,
            label="routine",
            evidence=[_ev("telemetry")],
            severity="info",
        ),
        Moment(
            t_ns=2,
            label="swerve",
            evidence=[_ev("camera"), _ev("telemetry")],
            severity="anomalous",
        ),
        Moment(
            t_ns=3,
            label="no evidence",
            evidence=[],
            severity="suspicious",
        ),
    ]
    report = ScenarioMiningReport(moments=moments, rationale="raw scan")
    out = ground_scenario_mining(report)
    assert len(out.moments) == 1
    assert out.moments[0].label == "swerve"
    assert "filtered 2 low-evidence moments" in out.rationale


def test_scenario_mining_no_drops_leaves_rationale_unchanged():
    moments = [
        Moment(
            t_ns=1,
            label="swerve",
            evidence=[_ev("camera"), _ev("telemetry")],
            severity="anomalous",
        ),
    ]
    report = ScenarioMiningReport(moments=moments, rationale="clean scan")
    out = ground_scenario_mining(report)
    assert out.rationale == "clean scan"
    assert len(out.moments) == 1


def test_input_immutability():
    h_reject = _hyp(confidence=0.2)
    h_keep = _hyp(confidence=0.9)
    report = _report([h_reject, h_keep])
    snapshot = copy.deepcopy(report.hypotheses)

    out = ground_post_mortem(report)

    assert report.hypotheses == snapshot
    assert len(report.hypotheses) == 2
    assert out is not report
    assert len(out.hypotheses) == 1


def test_custom_thresholds_stricter_confidence():
    h_mid = _hyp(confidence=0.6)
    h_high = _hyp(confidence=0.85)
    strict = GroundingThresholds(min_confidence=0.8)
    out = ground_post_mortem(_report([h_mid, h_high]), thresholds=strict)
    assert len(out.hypotheses) == 1
    assert out.hypotheses[0].confidence == 0.85


def test_custom_thresholds_relaxed_cross_source():
    h = _hyp(evidence=[_ev("telemetry"), _ev("telemetry")])
    relaxed = GroundingThresholds(min_cross_source_evidence=1)
    out = ground_post_mortem(_report([h]), thresholds=relaxed)
    assert len(out.hypotheses) == 1
