"""Pydantic v2 schemas for Black Box forensic analysis."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated


class Evidence(BaseModel):
    """Source evidence linking to a hypothesis."""
    source: Literal["camera", "telemetry", "code", "timeline"]
    topic_or_file: str
    t_ns: int | None = None
    snippet: str  # short human-readable


class Hypothesis(BaseModel):
    """Single bug hypothesis with confidence and supporting evidence."""
    bug_class: Literal[
        "pid_saturation",
        "sensor_timeout",
        "state_machine_deadlock",
        "bad_gain_tuning",
        "missing_null_check",
        "calibration_drift",
        "latency_spike",
        "sensor_dropout",
        "config_error",
        "degraded_state_estimation",
        "communication_failure",
        "other",
    ]
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


# ---------------------------------------------------------------------------
# Role segregation — Collector -> Analyst sidechain (P5-I)
#
# These types are the ONLY thing that crosses the trust boundary between the
# read-only Collector agent and the hypothesis-emitting Analyst agent. Every
# string here is treated by the Analyst as DATA, never instruction. The
# Analyst prompt wraps them in <untrusted> tags so a prompt-injection payload
# hidden in (e.g.) a filename or rosbag comment cannot steer the Analyst.
#
# Design rules:
#   * No `Dict[str, Any]`. Every leaf must be a Literal, bounded str, int,
#     float, or bool so the boundary is not a free-text channel.
#   * String lengths are capped — both to resist very long injection prompts
#     and to keep the handoff cacheable.
#   * Closed-set enums (`AssetKind`, `TelemetrySource`) mirror what the
#     Collector is allowed to observe. No room for a Collector to invent a
#     "new kind" of evidence.
# ---------------------------------------------------------------------------

AssetKind = Literal["bag", "audio", "video", "log", "chrony", "ros_log", "other"]
TelemetrySource = Literal["rosbag_topic", "log_line", "chrony_offset", "file_meta"]

# Bounded strings so a 50 KB "IGNORE PRIOR INSTRUCTIONS ..." blob cannot ride
# the handoff unchallenged. The Analyst treats each as data regardless, but
# capping length also keeps the serialized payload cheap to cache.
SafeShort = Annotated[str, StringConstraints(strip_whitespace=True, max_length=256)]
SafeMedium = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2048)]
SafeLong = Annotated[str, StringConstraints(strip_whitespace=True, max_length=8192)]


class AssetDescriptor(BaseModel):
    """One file or bag that the Collector observed inside the session root."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: AssetKind
    # Relative path inside the session root; absolute paths are rejected so
    # we cannot leak arbitrary filesystem locations across the boundary.
    relpath: SafeShort
    size_bytes: int = Field(ge=0)
    mtime_epoch: float = Field(ge=0.0)


class TelemetrySignal(BaseModel):
    """A structured numeric/enum observation extracted by the Collector.

    Example: PID integrator peak over window W; dropped-frame count on
    camera_front; state-machine state at t=12.3s. Values are numeric or
    short enums; no free-text from raw logs.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: TelemetrySource
    topic_or_file: SafeShort
    # Short machine-readable key, NOT a sentence. e.g. "pid.integral_peak".
    metric: Annotated[str, StringConstraints(
        strip_whitespace=True, max_length=64, pattern=r"^[a-zA-Z0-9_./:-]+$"
    )]
    value: float
    t_ns: int | None = None


class FrameWindow(BaseModel):
    """A time window the Collector flagged as worth the Analyst's attention."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    t_start_ns: int = Field(ge=0)
    t_end_ns: int = Field(ge=0)
    reason_code: Literal[
        "telemetry_spike",
        "sensor_dropout",
        "state_transition",
        "operator_tag",
        "session_boundary",
    ]
    # Optional numeric salience score; no free-text rationale.
    salience: float | None = Field(default=None, ge=0.0, le=1.0)


class CollectorNote(BaseModel):
    """Opaque, tag-coded note the Collector may attach.

    Kept deliberately narrow: `code` is an enum, `detail` is a capped string
    that the Analyst prompt wraps in <untrusted> and treats as data. No
    Collector free-text reaches the Analyst outside this channel.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Literal[
        "missing_asset",
        "truncated_bag",
        "clock_skew",
        "operator_label",
        "unparseable_line",
    ]
    detail: SafeMedium = ""


class SessionEvidence(BaseModel):
    """Typed handoff from Collector -> Analyst.

    This is the ONLY payload the Analyst sees. No raw file handles, no
    free-text prompt fragments, no tool_use authority crosses this boundary.
    Every string field is treated by the Analyst as untrusted data.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    session_root: SafeShort
    session_key: SafeShort | None = None
    case_key: SafeShort
    assets: list[AssetDescriptor] = Field(default_factory=list, max_length=4096)
    telemetry: list[TelemetrySignal] = Field(default_factory=list, max_length=8192)
    windows: list[FrameWindow] = Field(default_factory=list, max_length=64)
    notes: list[CollectorNote] = Field(default_factory=list, max_length=64)
    # Numeric bag/session duration; NOT a human-readable string.
    duration_ns: int | None = Field(default=None, ge=0)


class AnalysisVerdict(BaseModel):
    """Analyst output. Strict pydantic so downstream wiring can't be spoofed."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_key: SafeShort
    report: PostMortemReport
    # If the Analyst detected an attempted prompt injection in the evidence
    # (e.g. a filename containing "IGNORE PRIOR INSTRUCTIONS"), it MUST set
    # this flag and MUST NOT comply with the embedded instruction. The
    # adversarial test asserts this.
    injection_detected: bool = False
    # Short, closed-set reason the Analyst used to justify `injection_detected`.
    # None when no injection was seen. NOT a chain-of-thought dump.
    injection_reason: Literal[
        "none",
        "suspicious_filename",
        "suspicious_log_line",
        "suspicious_note",
        "suspicious_metric_name",
    ] = "none"
