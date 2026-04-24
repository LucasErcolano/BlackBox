# SPDX-License-Identifier: MIT
"""Pydantic v2 schemas for Black Box forensic analysis."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    """Source evidence linking to a hypothesis."""
    source: Literal["camera", "telemetry", "code", "timeline"]
    topic_or_file: str
    t_ns: int | None = None
    snippet: str  # short human-readable


# Frozen closed-set bug taxonomy. Source of truth: CLAUDE.md + root README.
# Exactly 7 entries. Do NOT add, remove, or rename without updating
# CLAUDE.md, README.md, and src/black_box/analysis/prompts.py in the same PR.
BugClass = Literal[
    "pid_saturation",
    "sensor_timeout",
    "state_machine_deadlock",
    "bad_gain_tuning",
    "missing_null_check",
    "calibration_drift",
    "latency_spike",
]


class Hypothesis(BaseModel):
    """Single bug hypothesis with confidence and supporting evidence.

    ``bug_class`` is a closed Literal of exactly 7 entries. Any value outside
    the set raises ``pydantic.ValidationError`` at parse time — no silent
    coercion, no fallback bucket. See ``BugClass`` above.
    """
    bug_class: BugClass
    confidence: float  # 0..1
    summary: str
    evidence: list[Evidence]
    patch_hint: str  # natural language description of scoped fix


class TimelineEvent(BaseModel):
    """Timestamped event observable across analysis."""
    t_ns: int
    label: str
    cross_view: bool  # true if observable across multiple cameras


class PostMortemReport(BaseModel):
    """Full forensic analysis with timeline and ranked hypotheses."""
    timeline: list[TimelineEvent]
    hypotheses: list[Hypothesis]  # ranked, highest confidence first
    root_cause_idx: int  # index into hypotheses
    patch_proposal: str  # unified diff-style text or pseudo-patch


class Moment(BaseModel):
    """Anomalous moment detected during scenario mining."""
    t_ns: int
    label: str
    evidence: list[Evidence]
    severity: Literal["info", "suspicious", "anomalous"]


class ScenarioMiningReport(BaseModel):
    """Detection of anomalous moments (0..5). Empty = nothing detected."""
    moments: list[Moment]
    rationale: str


class SelfEval(BaseModel):
    """Ground-truth comparison for synthetic QA."""
    model_config = ConfigDict(populate_by_name=True)
    predicted_bug: str = Field(validation_alias="predicted_bug", alias_priority=1)
    ground_truth_bug: str = Field(validation_alias="ground_truth_bug", alias_priority=1)
    match: bool
    notes: str = ""

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        if isinstance(obj, dict):
            obj = dict(obj)
            for src, dst in [
                ("predicted_bug_class", "predicted_bug"),
                ("ground_truth_bug_class", "ground_truth_bug"),
            ]:
                if src in obj and dst not in obj:
                    obj[dst] = obj[src]
        return super().model_validate(obj, *args, **kwargs)


class SyntheticQAReport(BaseModel):
    """Hypothesis + self-evaluation against ground truth."""
    hypotheses: list[Hypothesis]
    self_eval: SelfEval
