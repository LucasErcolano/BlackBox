"""Tests for the adaptive resolution budgeter."""
from __future__ import annotations

import pytest

from black_box.analysis.resolution_budgeter import (
    ResolutionBudgeter,
    ambiguity_from_top_two_confidences,
    legacy_tier_to_string,
    saliency_from_telemetry_z,
)


def test_low_signal_picks_thumb():
    b = ResolutionBudgeter()
    d = b.decide(saliency=0.1, ambiguity=0.1, remaining_budget_usd=500, budget_total_usd=500)
    assert d.tier == "thumb"
    assert d.max_side == 800
    assert d.rationale.startswith("thumb:low_signal")


def test_high_saliency_high_ambiguity_picks_hires():
    b = ResolutionBudgeter()
    d = b.decide(saliency=0.9, ambiguity=0.8, remaining_budget_usd=500, budget_total_usd=500)
    assert d.tier == "hires"
    assert d.max_side == 1920


def test_high_saliency_alone_picks_standard():
    b = ResolutionBudgeter()
    d = b.decide(saliency=0.8, ambiguity=0.1, remaining_budget_usd=500, budget_total_usd=500)
    assert d.tier == "standard"
    assert d.max_side == 1280


def test_high_ambiguity_alone_picks_standard():
    b = ResolutionBudgeter()
    d = b.decide(saliency=0.1, ambiguity=0.9, remaining_budget_usd=500, budget_total_usd=500)
    assert d.tier == "standard"


def test_budget_guard_blocks_escalation():
    """Starving case cannot escalate, even with maximal saliency+ambiguity."""
    b = ResolutionBudgeter()
    d = b.decide(saliency=1.0, ambiguity=1.0, remaining_budget_usd=10, budget_total_usd=500)
    assert d.tier == "thumb"
    assert "budget_guard" in d.rationale


def test_force_tier_overrides_policy():
    b = ResolutionBudgeter(force_tier="thumb")
    d = b.decide(saliency=1.0, ambiguity=1.0, remaining_budget_usd=500, budget_total_usd=500)
    assert d.tier == "thumb"
    assert d.rationale == "forced:thumb"

    b2 = ResolutionBudgeter(force_tier="hires")
    d2 = b2.decide(saliency=0.0, ambiguity=0.0, remaining_budget_usd=1, budget_total_usd=500)
    assert d2.tier == "hires"


def test_decisions_log_accumulates():
    b = ResolutionBudgeter()
    for _ in range(3):
        b.decide(saliency=0.5, ambiguity=0.5, remaining_budget_usd=500, budget_total_usd=500)
    assert len(b.decisions) == 3


def test_inputs_are_clamped_to_unit_interval():
    b = ResolutionBudgeter()
    d = b.decide(saliency=5.0, ambiguity=-1.0, remaining_budget_usd=1000, budget_total_usd=500)
    assert d.saliency == 1.0
    assert d.ambiguity == 0.0
    assert d.budget_fraction_remaining == 1.0


# ---------------------------------------------------------------------------
# Signal extractors
# ---------------------------------------------------------------------------
def test_saliency_from_z_threshold():
    assert saliency_from_telemetry_z(0.0) == 0.0
    assert saliency_from_telemetry_z(1.5, threshold=3.0) == 0.5
    assert saliency_from_telemetry_z(3.0, threshold=3.0) == 1.0
    # clamps above threshold
    assert saliency_from_telemetry_z(10.0, threshold=3.0) == 1.0
    # symmetric on sign
    assert saliency_from_telemetry_z(-3.0, threshold=3.0) == 1.0
    # bad threshold guard
    assert saliency_from_telemetry_z(5.0, threshold=0.0) == 0.0


def test_ambiguity_from_top_two():
    # Strong single winner -> unambiguous.
    assert ambiguity_from_top_two_confidences([0.9, 0.1, 0.1]) == pytest.approx(0.2)
    # Near-tie -> highly ambiguous.
    assert ambiguity_from_top_two_confidences([0.55, 0.50]) == pytest.approx(0.95)
    # Perfect tie -> maximally ambiguous.
    assert ambiguity_from_top_two_confidences([0.5, 0.5]) == pytest.approx(1.0)
    # Single or empty -> unambiguous.
    assert ambiguity_from_top_two_confidences([0.9]) == 0.0
    assert ambiguity_from_top_two_confidences([]) == 0.0


def test_legacy_tier_shim_collapses_standard_to_hires():
    b = ResolutionBudgeter()
    d_low = b.decide(saliency=0.0, ambiguity=0.0, remaining_budget_usd=500, budget_total_usd=500)
    d_std = b.decide(saliency=0.8, ambiguity=0.1, remaining_budget_usd=500, budget_total_usd=500)
    d_hi = b.decide(saliency=0.9, ambiguity=0.9, remaining_budget_usd=500, budget_total_usd=500)
    assert legacy_tier_to_string(d_low) == "thumb"
    assert legacy_tier_to_string(d_std) == "hires"
    assert legacy_tier_to_string(d_hi) == "hires"
