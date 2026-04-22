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

__all__ = [
    "ClaudeClient",
    "CostLog",
    "Evidence",
    "Hypothesis",
    "Moment",
    "PostMortemReport",
    "ScenarioMiningReport",
    "SelfEval",
    "SyntheticQAReport",
    "TimelineEvent",
    "post_mortem_prompt",
    "scenario_mining_prompt",
    "synthetic_qa_prompt",
]
