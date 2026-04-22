"""Deterministic grounding gate for Claude analysis output.

Runs AFTER Claude emits a report, BEFORE rendering. Filters hypotheses /
moments that lack sufficient evidence so the tool fails closed (empty) rather
than fabricating a confident-but-ungrounded bug.
"""

from __future__ import annotations

from dataclasses import dataclass

from .schemas import Hypothesis, Moment, PostMortemReport, ScenarioMiningReport


@dataclass(frozen=True)
class GroundingThresholds:
    min_confidence: float = 0.4
    min_evidence_per_hypothesis: int = 2
    min_evidence_for_other: int = 3
    min_cross_source_evidence: int = 2
    min_moment_evidence: int = 1
    drop_info_moments: bool = True


NO_ANOMALY_PATCH = "No anomaly detected with sufficient evidence to support a scoped fix."


def _accept_hypothesis(
    h: Hypothesis,
    thresholds: GroundingThresholds,
    available_sources: int = 2,
) -> bool:
    if h.confidence < thresholds.min_confidence:
        return False
    if len(h.evidence) < thresholds.min_evidence_per_hypothesis:
        return False
    if h.bug_class == "other" and len(h.evidence) < thresholds.min_evidence_for_other:
        return False
    required = min(thresholds.min_cross_source_evidence, available_sources)
    distinct_sources = {e.source for e in h.evidence}
    if len(distinct_sources) < required:
        return False
    return True


def _accept_moment(m: Moment, thresholds: GroundingThresholds) -> bool:
    if len(m.evidence) < thresholds.min_moment_evidence:
        return False
    if thresholds.drop_info_moments and m.severity == "info":
        return False
    return True


def ground_post_mortem(
    report: PostMortemReport,
    thresholds: GroundingThresholds | None = None,
) -> PostMortemReport:
    t = thresholds or GroundingThresholds()
    all_sources = {e.source for h in report.hypotheses for e in h.evidence}
    available = max(1, len(all_sources))
    accepted = [
        h for h in report.hypotheses if _accept_hypothesis(h, t, available_sources=available)
    ]

    if not accepted:
        return report.model_copy(
            update={
                "hypotheses": [],
                "root_cause_idx": 0,
                "patch_proposal": NO_ANOMALY_PATCH,
            }
        )

    ranked = sorted(accepted, key=lambda h: h.confidence, reverse=True)
    return report.model_copy(update={"hypotheses": ranked, "root_cause_idx": 0})


def ground_scenario_mining(
    report: ScenarioMiningReport,
    thresholds: GroundingThresholds | None = None,
) -> ScenarioMiningReport:
    t = thresholds or GroundingThresholds()
    original_count = len(report.moments)
    kept = [m for m in report.moments if _accept_moment(m, t)]
    dropped = original_count - len(kept)

    rationale = report.rationale
    if dropped > 0:
        rationale = f"{rationale} (filtered {dropped} low-evidence moments)"

    return report.model_copy(update={"moments": kept, "rationale": rationale})
