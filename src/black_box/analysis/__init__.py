# SPDX-License-Identifier: MIT
"""Black Box analysis module: Claude-powered forensic diagnostics."""

from .claude_client import ClaudeClient, CostLog
from .schemas import (
    Evidence,
    Hypothesis,
    Moment,
    PostMortemReport,
    ScenarioMiningReport,
    SelfEval,
    SyntheticQAReport,
    TimelineEvent,
)
from .prompts import (
    post_mortem_prompt,
    scenario_mining_prompt,
    synthetic_qa_prompt,
)
from .prompts_generic import (
    visual_mining_prompt as visual_mining_prompt_generic,
    window_summary_prompt as window_summary_prompt_generic,
    MiningReport as GenericMiningReport,
    WindowSummary as GenericWindowSummary,
)
from .resolution_budgeter import (
    ResolutionBudgeter,
    ResolutionDecision,
    ResolutionTier,
    ambiguity_from_top_two_confidences,
    legacy_tier_to_string,
    saliency_from_telemetry_z,
)

__all__ = [
    "ClaudeClient",
    "CostLog",
    "Evidence",
    "Hypothesis",
    "Moment",
    "PostMortemReport",
    "ResolutionBudgeter",
    "ResolutionDecision",
    "ResolutionTier",
    "ScenarioMiningReport",
    "SelfEval",
    "SyntheticQAReport",
    "TimelineEvent",
    "ambiguity_from_top_two_confidences",
    "legacy_tier_to_string",
    "post_mortem_prompt",
    "saliency_from_telemetry_z",
    "scenario_mining_prompt",
    "synthetic_qa_prompt",
    "visual_mining_prompt_generic",
    "window_summary_prompt_generic",
    "GenericMiningReport",
    "GenericWindowSummary",
]
