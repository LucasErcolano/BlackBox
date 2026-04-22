"""Typed record schemas for the 4 memory layers. Pydantic v2."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CaseRecord(BaseModel):
    """L1 — per-case session scratchpad entry."""
    case_key: str
    kind: Literal["hypothesis", "evidence", "steering", "note"]
    t_logged: str = Field(default_factory=_utc_now)
    payload: dict


class PlatformPrior(BaseModel):
    """L2 — per-platform prior tying a signal signature to a bug class."""
    platform: str
    signature: str  # short human-readable pattern, e.g. "angle_y_ramp_over_0.25"
    bug_class: str  # one of the closed 7-class taxonomy + "other"
    confidence: float = Field(ge=0.0, le=1.0)
    hits: int = 1
    t_logged: str = Field(default_factory=_utc_now)
    source_case: str | None = None


class TaxonomyCount(BaseModel):
    """L3 — global tally of a bug_class occurrence with its signature."""
    bug_class: str
    signature: str
    count: int = 1
    t_logged: str = Field(default_factory=_utc_now)


class EvalRecord(BaseModel):
    """L4 — synthetic QA outcome for self-eval calibration."""
    case_key: str
    predicted_bug: str
    ground_truth_bug: str
    match: bool
    notes: str = ""
    t_logged: str = Field(default_factory=_utc_now)
