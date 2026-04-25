# SPDX-License-Identifier: MIT
"""Glass-box evidence trace for forensic reports.

Pulls together the existing audit substrate — evidence, kept/discarded
hypotheses, grounding-gate decision, per-step cost from
``data/costs.jsonl``, artifact provenance (live | replay | sample),
confidence + what would change it — and exposes:

- ``Trace`` (pydantic) — structured audit shape used by both HTML and PDF
  renderers and by tests as a stable contract.
- ``render_trace_html(trace)`` — sober HTMX-friendly fragment slotted
  into the report page.
- ``trace_from_artifacts(job_id)`` — helper that reads costs.jsonl plus
  a manifest if present and assembles a Trace ready to render.

This module reads what already exists. It does **not** invent new
analyses (per #77 out-of-scope clause). When a piece is unavailable
(e.g. no manifest yet), the corresponding section renders a sober
placeholder rather than a fabricated row.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Literal, Optional

from pydantic import BaseModel, Field


Provenance = Literal["live", "replay", "sample"]


class EvidenceItem(BaseModel):
    kind: Literal["frame", "telemetry_window", "audio_excerpt", "chrony_log", "code_snippet"]
    source_path: str
    t_ns: Optional[int] = None
    snippet: str = ""
    provenance: Provenance = "live"


class DiscardedHypothesis(BaseModel):
    label: str
    reason: str
    confidence_at_drop: float = 0.0


class GateDecision(BaseModel):
    outcome: Literal["pass", "fail", "partial"]
    rationale: str
    min_evidence: int = 2


class CostStep(BaseModel):
    step_name: str
    cached_input_tokens: int = 0
    uncached_input_tokens: int = 0
    output_tokens: int = 0
    usd_cost: float = 0.0


class ConfidenceCalibration(BaseModel):
    score: float
    raises: list[str] = Field(default_factory=list)
    lowers: list[str] = Field(default_factory=list)


class Trace(BaseModel):
    job_id: str
    run_provenance: Provenance = "live"
    evidence_used: list[EvidenceItem] = Field(default_factory=list)
    discarded: list[DiscardedHypothesis] = Field(default_factory=list)
    gate: Optional[GateDecision] = None
    cost_steps: list[CostStep] = Field(default_factory=list)
    confidence: Optional[ConfidenceCalibration] = None

    def total_usd(self) -> float:
        return round(sum(s.usd_cost for s in self.cost_steps), 4)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def cost_steps_from_jsonl(
    path: Path,
    job_id: str,
) -> list[CostStep]:
    """Parse ``data/costs.jsonl`` and return rows tagged with this job_id.

    Falls back to an empty list when the ledger is missing/unreadable.
    Tolerant to historic schema variation: we only require ``usd_cost``
    and at least one token field.
    """
    out: list[CostStep] = []
    if not path.exists():
        return out
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(row.get("job_id") or row.get("case_key") or "") != job_id:
                continue
            out.append(
                CostStep(
                    step_name=str(row.get("prompt_kind") or row.get("step") or "unknown"),
                    cached_input_tokens=int(row.get("cached_input_tokens") or 0),
                    uncached_input_tokens=int(
                        row.get("uncached_input_tokens")
                        or row.get("input_tokens")
                        or 0
                    ),
                    output_tokens=int(row.get("output_tokens") or 0),
                    usd_cost=float(row.get("usd_cost") or 0.0),
                )
            )
    except OSError:
        pass
    return out


def trace_from_artifacts(
    job_id: str,
    repo_root: Path,
    manifest: Optional[dict[str, Any]] = None,
) -> Trace:
    """Assemble a Trace from on-disk artifacts.

    The optional ``manifest`` is a free-shape dict the agent finalizer
    writes alongside the report containing structured evidence rows. When
    absent, only cost-ledger data populates the trace and the renderers
    show sober placeholders for the rest.
    """
    costs = cost_steps_from_jsonl(repo_root / "data" / "costs.jsonl", job_id)
    trace = Trace(job_id=job_id, cost_steps=costs)

    if not manifest:
        return trace

    if "evidence_used" in manifest:
        trace.evidence_used = [EvidenceItem(**e) for e in manifest["evidence_used"]]
    if "discarded" in manifest:
        trace.discarded = [DiscardedHypothesis(**d) for d in manifest["discarded"]]
    if "gate" in manifest:
        trace.gate = GateDecision(**manifest["gate"])
    if "confidence" in manifest:
        trace.confidence = ConfidenceCalibration(**manifest["confidence"])
    if "run_provenance" in manifest:
        trace.run_provenance = manifest["run_provenance"]
    return trace


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------
_PROV_BADGE = {
    "live": '<span class="prov prov-live">live</span>',
    "replay": '<span class="prov prov-replay">replay</span>',
    "sample": '<span class="prov prov-sample">sample</span>',
}


def _row(label: str, body: str) -> str:
    return f'<tr><th scope="row">{label}</th><td>{body}</td></tr>'


def _esc(s: Any) -> str:
    from html import escape

    return escape(str(s))


def render_trace_html(trace: Trace) -> str:
    sections: list[str] = []
    sections.append(
        f'<header class="trace-head"><h2>Audit trace</h2>'
        f'<span class="trace-job">job <code>{_esc(trace.job_id)}</code></span> '
        f'{_PROV_BADGE.get(trace.run_provenance, "")}</header>'
    )

    if trace.evidence_used:
        rows = "".join(
            "<tr>"
            f"<td>{_PROV_BADGE.get(ev.provenance, '')}</td>"
            f"<td><code>{_esc(ev.kind)}</code></td>"
            f"<td><code>{_esc(ev.source_path)}</code></td>"
            f"<td>{_esc(ev.t_ns) if ev.t_ns is not None else '—'}</td>"
            f"<td>{_esc(ev.snippet)}</td>"
            "</tr>"
            for ev in trace.evidence_used
        )
        sections.append(
            "<section class='trace-section'><h3>Evidence used</h3>"
            "<table class='trace-table'><thead><tr><th>tag</th><th>kind</th><th>source</th><th>t_ns</th><th>snippet</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></section>"
        )
    else:
        sections.append("<section class='trace-section'><h3>Evidence used</h3><p>No structured evidence manifest available for this run.</p></section>")

    if trace.discarded:
        items = "".join(
            f"<li><strong>{_esc(d.label)}</strong> (conf {d.confidence_at_drop:.2f}) — {_esc(d.reason)}</li>"
            for d in trace.discarded
        )
        sections.append(f"<section class='trace-section'><h3>Discarded hypotheses</h3><ul>{items}</ul></section>")

    if trace.gate:
        sections.append(
            "<section class='trace-section'><h3>Grounding gate</h3>"
            f"<table class='trace-table'>{_row('outcome', _esc(trace.gate.outcome))}"
            f"{_row('min_evidence', _esc(trace.gate.min_evidence))}"
            f"{_row('rationale', _esc(trace.gate.rationale))}</table></section>"
        )

    if trace.cost_steps:
        rows = "".join(
            "<tr>"
            f"<td><code>{_esc(s.step_name)}</code></td>"
            f"<td>{s.cached_input_tokens:,}</td>"
            f"<td>{s.uncached_input_tokens:,}</td>"
            f"<td>{s.output_tokens:,}</td>"
            f"<td>${s.usd_cost:.4f}</td>"
            "</tr>"
            for s in trace.cost_steps
        )
        sections.append(
            "<section class='trace-section'><h3>Per-step cost</h3>"
            "<table class='trace-table'><thead><tr><th>step</th><th>cached_in</th><th>uncached_in</th><th>out</th><th>USD</th></tr></thead>"
            f"<tbody>{rows}<tr><th colspan='4'>total</th><td>${trace.total_usd():.4f}</td></tr></tbody></table></section>"
        )

    if trace.confidence:
        raises = "".join(f"<li>{_esc(r)}</li>" for r in trace.confidence.raises)
        lowers = "".join(f"<li>{_esc(r)}</li>" for r in trace.confidence.lowers)
        sections.append(
            "<section class='trace-section'><h3>Confidence calibration</h3>"
            f"<p>Score <strong>{trace.confidence.score:.2f}</strong></p>"
            f"<details open><summary>Would raise</summary><ul>{raises or '<li>—</li>'}</ul></details>"
            f"<details open><summary>Would lower</summary><ul>{lowers or '<li>—</li>'}</ul></details>"
            "</section>"
        )

    return "<article class='evidence-trace'>" + "".join(sections) + "</article>"
