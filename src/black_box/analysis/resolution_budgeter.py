"""Adaptive resolution budgeter.

Picks the right image resolution tier per Claude call instead of using a
single hardcoded max-side. The policy weighs three signals:

- **saliency**: how interesting the telemetry window is (0..1). A flagged
  spike gets more pixels than a quiet stretch.
- **ambiguity**: how uncertain the previous model call was (0..1). When
  two hypotheses are near-tied in confidence, we escalate resolution
  before re-calling rather than thrashing on thumbnails.
- **cost budget**: fraction of the per-case token budget already spent.
  When remaining budget is tight, we refuse to escalate regardless of
  saliency/ambiguity — thumbnails still produce useful output; blowing
  the cap does not.

Each decision is a structured record (tier + max_side + rationale) so
callers can log and audit resolution choices.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ResolutionTier = Literal["thumb", "standard", "hires"]

# Per-tier max image side, in pixels. Aspect ratio is preserved on resize.
_TIER_MAX_SIDE: dict[ResolutionTier, int] = {
    "thumb": 800,
    "standard": 1280,
    "hires": 1920,
}


@dataclass(frozen=True)
class ResolutionDecision:
    tier: ResolutionTier
    max_side: int
    rationale: str
    saliency: float
    ambiguity: float
    budget_fraction_remaining: float


@dataclass
class ResolutionBudgeter:
    """Policy object: maps (saliency, ambiguity, budget) -> resolution tier.

    Thresholds are defaulted for a $500 hackathon cap with ~3 cases per
    run; callers can tighten them for stricter token discipline.
    """

    # If less than this fraction of the budget remains, refuse to escalate.
    min_budget_fraction_for_escalation: float = 0.15
    # Saliency + ambiguity thresholds for escalation tiers.
    hires_saliency: float = 0.7
    hires_ambiguity: float = 0.5
    standard_saliency: float = 0.7
    standard_ambiguity: float = 0.7
    # Allow callers to force a floor tier (e.g. always-thumb during dev).
    force_tier: ResolutionTier | None = None
    # History of decisions for this case/session.
    decisions: list[ResolutionDecision] = field(default_factory=list)

    def decide(
        self,
        saliency: float,
        ambiguity: float,
        remaining_budget_usd: float,
        budget_total_usd: float,
    ) -> ResolutionDecision:
        saliency = _clamp01(saliency)
        ambiguity = _clamp01(ambiguity)
        frac = (remaining_budget_usd / budget_total_usd) if budget_total_usd > 0 else 0.0
        frac = _clamp01(frac)

        if self.force_tier is not None:
            decision = ResolutionDecision(
                tier=self.force_tier,
                max_side=_TIER_MAX_SIDE[self.force_tier],
                rationale=f"forced:{self.force_tier}",
                saliency=saliency,
                ambiguity=ambiguity,
                budget_fraction_remaining=frac,
            )
            self.decisions.append(decision)
            return decision

        # Budget guard wins over everything else. A starving case cannot
        # afford full-res calls, no matter how salient or ambiguous.
        if frac < self.min_budget_fraction_for_escalation:
            tier: ResolutionTier = "thumb"
            rationale = f"budget_guard:frac={frac:.2f}<{self.min_budget_fraction_for_escalation:.2f}"
        elif saliency >= self.hires_saliency and ambiguity >= self.hires_ambiguity:
            tier = "hires"
            rationale = f"hires:saliency={saliency:.2f},ambiguity={ambiguity:.2f}"
        elif saliency >= self.standard_saliency or ambiguity >= self.standard_ambiguity:
            tier = "standard"
            rationale = f"standard:saliency={saliency:.2f},ambiguity={ambiguity:.2f}"
        else:
            tier = "thumb"
            rationale = f"thumb:low_signal:saliency={saliency:.2f},ambiguity={ambiguity:.2f}"

        decision = ResolutionDecision(
            tier=tier,
            max_side=_TIER_MAX_SIDE[tier],
            rationale=rationale,
            saliency=saliency,
            ambiguity=ambiguity,
            budget_fraction_remaining=frac,
        )
        self.decisions.append(decision)
        return decision


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return float(x)


# ---------------------------------------------------------------------------
# Signal extractors — small pure functions callers can feed into the
# budgeter. Kept out of the class so they stay testable in isolation and so
# new signals can be added without widening the policy's surface.
# ---------------------------------------------------------------------------
def saliency_from_telemetry_z(z_score: float, threshold: float = 3.0) -> float:
    """Map a telemetry z-score to saliency ∈ [0, 1].

    A z of ``threshold`` maps to 1.0; anything above is clamped.
    """
    if threshold <= 0:
        return 0.0
    return _clamp01(abs(z_score) / threshold)


def ambiguity_from_top_two_confidences(
    confidences: list[float] | tuple[float, ...]
) -> float:
    """Ambiguity = 1 - (top1 - top2). Near-tied candidates -> near 1.

    A single hypothesis (or empty list) is unambiguous -> 0.
    """
    if len(confidences) < 2:
        return 0.0
    sorted_c = sorted((_clamp01(c) for c in confidences), reverse=True)
    return _clamp01(1.0 - (sorted_c[0] - sorted_c[1]))


def legacy_tier_to_string(decision: ResolutionDecision) -> Literal["thumb", "hires"]:
    """Back-compat shim for call sites that still take Literal['thumb','hires'].

    Collapses the middle ``standard`` tier to ``hires`` so we never silently
    downgrade a decision that earned escalation.
    """
    return "thumb" if decision.tier == "thumb" else "hires"
