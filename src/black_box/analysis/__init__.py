"""Black Box analysis module: Claude-powered forensic diagnostics."""

from .claude_client import ClaudeClient, CostLog
from .schemas import (
    AnalysisVerdict,
    AssetDescriptor,
    CollectorNote,
    Evidence,
    FrameWindow,
    Hypothesis,
    Moment,
    PostMortemReport,
    ScenarioMiningReport,
    SelfEval,
    SessionEvidence,
    SyntheticQAReport,
    TelemetrySignal,
    TimelineEvent,
)
from .roles import (
    AnalystAgent,
    AnalystAgentConfig,
    CollectorAgent,
    CollectorAgentConfig,
    RoleSidechain,
    RoleSidechainConfig,
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
    "AnalysisVerdict",
    "AnalystAgent",
    "AnalystAgentConfig",
    "AssetDescriptor",
    "ClaudeClient",
    "CollectorAgent",
    "CollectorAgentConfig",
    "CollectorNote",
    "CostLog",
    "Evidence",
    "FrameWindow",
    "Hypothesis",
    "Moment",
    "PostMortemReport",
    "ResolutionBudgeter",
    "ResolutionDecision",
    "ResolutionTier",
    "RoleSidechain",
    "RoleSidechainConfig",
    "ScenarioMiningReport",
    "SelfEval",
    "SessionEvidence",
    "SyntheticQAReport",
    "TelemetrySignal",
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
