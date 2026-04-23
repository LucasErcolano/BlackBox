"""Build the grounding-gate clean-recording demo asset.

Demonstrates the "nothing anomalous detected" branch of the gate: given a
clean recording, a model under pressure to produce output may emit
low-confidence / under-evidenced hypotheses. The gate fails closed and
ships an explicit no-anomaly report rather than a fabricated fix.

Outputs three artifacts under demo_assets/grounding_gate/clean_recording/:
  - raw_hypotheses.json   what a less-disciplined model might emit
  - gated_report.json     what Black Box actually ships
  - README.md             before/after + rule reference

Re-run: python scripts/build_grounding_gate_demo.py
"""
from __future__ import annotations

import json
from pathlib import Path

from black_box.analysis.grounding import (
    NO_ANOMALY_PATCH,
    GroundingThresholds,
    ground_post_mortem,
)
from black_box.analysis.schemas import (
    Evidence,
    Hypothesis,
    PostMortemReport,
    TimelineEvent,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "demo_assets" / "grounding_gate" / "clean_recording"


def _raw_report() -> PostMortemReport:
    """A tempting-but-ungrounded report on a clean recording.

    Each hypothesis is crafted to fail one specific gate rule:
      #0 high-conf but ONLY ONE evidence row            (< 2 evidence)
      #1 two evidence rows but both from same source    (< 2 distinct sources)
      #2 'other' with low evidence count                (< 3 for 'other')
      #3 two evidence rows but confidence below floor   (< 0.4 confidence)

    No hypothesis passes — gate returns the no-anomaly payload.
    """
    return PostMortemReport(
        timeline=[
            TimelineEvent(t_ns=0, label="session start", cross_view=False),
            TimelineEvent(t_ns=180_000_000_000, label="session end", cross_view=False),
        ],
        hypotheses=[
            Hypothesis(
                bug_class="pid_saturation",
                confidence=0.72,
                summary="Minor overshoot visible on /cmd_vel near t=90s",
                evidence=[
                    Evidence(
                        source="telemetry",
                        topic_or_file="/cmd_vel",
                        t_ns=90_000_000_000,
                        snippet="peak 0.18 m/s, within nominal band",
                    ),
                ],
                patch_hint="clamp max velocity tighter",
            ),
            Hypothesis(
                bug_class="calibration_drift",
                confidence=0.60,
                summary="Two frames on camera 2 look slightly tilted vs camera 1",
                evidence=[
                    Evidence(
                        source="camera",
                        topic_or_file="/cam2/image",
                        t_ns=30_000_000_000,
                        snippet="horizon tilt ~1deg",
                    ),
                    Evidence(
                        source="camera",
                        topic_or_file="/cam2/image",
                        t_ns=60_000_000_000,
                        snippet="horizon tilt ~1deg",
                    ),
                ],
                patch_hint="recalibrate cam2 extrinsics",
            ),
            Hypothesis(
                bug_class="other",
                confidence=0.55,
                summary="Ambient vibration signature looks a little noisy",
                evidence=[
                    Evidence(
                        source="telemetry",
                        topic_or_file="/imu",
                        t_ns=45_000_000_000,
                        snippet="accel RMS 0.4 m/s^2",
                    ),
                    Evidence(
                        source="timeline",
                        topic_or_file="derived",
                        t_ns=45_000_000_000,
                        snippet="no correlated control event",
                    ),
                ],
                patch_hint="add vibration damper",
            ),
            Hypothesis(
                bug_class="latency_spike",
                confidence=0.22,
                summary="One 15ms jitter on /odom",
                evidence=[
                    Evidence(
                        source="telemetry",
                        topic_or_file="/odom",
                        t_ns=120_000_000_000,
                        snippet="dt 15ms vs 10ms nominal",
                    ),
                    Evidence(
                        source="timeline",
                        topic_or_file="derived",
                        t_ns=120_000_000_000,
                        snippet="isolated single sample",
                    ),
                ],
                patch_hint="widen odom latency budget",
            ),
        ],
        root_cause_idx=0,
        patch_proposal="clamp velocity + recalibrate cam2 + damp vibration",
    )


def _reason_dropped(h: Hypothesis, t: GroundingThresholds, available_sources: int) -> str:
    if h.confidence < t.min_confidence:
        return f"confidence {h.confidence:.2f} < {t.min_confidence}"
    if len(h.evidence) < t.min_evidence_per_hypothesis:
        return f"only {len(h.evidence)} evidence row(s) (need >= {t.min_evidence_per_hypothesis})"
    if h.bug_class == "other" and len(h.evidence) < t.min_evidence_for_other:
        return f"bug_class=other with {len(h.evidence)} evidence rows (need >= {t.min_evidence_for_other})"
    required = min(t.min_cross_source_evidence, available_sources)
    distinct = {e.source for e in h.evidence}
    if len(distinct) < required:
        return f"only 1 source ({', '.join(distinct)}) — need >= {required}"
    return "accepted"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    raw = _raw_report()
    t = GroundingThresholds()
    available_sources = len({e.source for h in raw.hypotheses for e in h.evidence})
    drops = [
        {
            "bug_class": h.bug_class,
            "confidence": h.confidence,
            "reason_dropped": _reason_dropped(h, t, available_sources),
        }
        for h in raw.hypotheses
    ]

    gated = ground_post_mortem(raw, t)

    (OUT_DIR / "raw_hypotheses.json").write_text(
        json.dumps(raw.model_dump(), indent=2) + "\n"
    )
    (OUT_DIR / "gated_report.json").write_text(
        json.dumps(gated.model_dump(), indent=2) + "\n"
    )
    (OUT_DIR / "drop_reasons.json").write_text(
        json.dumps(drops, indent=2) + "\n"
    )

    readme = _render_readme(raw, gated, drops, t)
    (OUT_DIR / "README.md").write_text(readme)

    print(f"Wrote {OUT_DIR}")
    for p in sorted(OUT_DIR.iterdir()):
        print(f"  {p.name}")


def _render_readme(
    raw: PostMortemReport,
    gated: PostMortemReport,
    drops: list[dict],
    t: GroundingThresholds,
) -> str:
    lines = [
        "# Grounding gate: \"nothing anomalous detected\" demo",
        "",
        "A clean recording went in. The model under pressure produced four ",
        "plausible-but-under-evidenced hypotheses. The gate killed all four ",
        "and the report that ships says so explicitly.",
        "",
        "## Why this asset exists",
        "",
        "Lucas asked for the grounding gate to be visible in the demo, ",
        "including the no-anomaly branch. Previous assets only showed the ",
        "*refutation* side (operator narrative contradicted by telemetry). ",
        "This one shows the *silence* side — the agent would rather ship ",
        "nothing than ship a fabrication.",
        "",
        "## Before (raw) vs after (gated)",
        "",
        f"| # | bug_class | conf | evidence | status |",
        f"|--:|-----------|-----:|---------:|--------|",
    ]
    for i, (h, d) in enumerate(zip(raw.hypotheses, drops)):
        lines.append(
            f"| {i} | `{h.bug_class}` | {h.confidence:.2f} | "
            f"{len(h.evidence)} | dropped — {d['reason_dropped']} |"
        )
    lines += [
        "",
        f"**Gated output** — `patch_proposal`: _{gated.patch_proposal}_",
        f"**Hypotheses shipped**: {len(gated.hypotheses)}",
        "",
        "## Gate rules applied",
        "",
        f"- min confidence: `{t.min_confidence}`",
        f"- min evidence rows / hypothesis: `{t.min_evidence_per_hypothesis}`",
        f"- min evidence rows for `other`: `{t.min_evidence_for_other}`",
        f"- min distinct evidence sources: "
        f"`min({t.min_cross_source_evidence}, available_sources)`",
        "- info-severity moments dropped by default",
        "",
        "Rules live in `src/black_box/analysis/grounding.py :: GroundingThresholds`. ",
        "",
        "## Regenerate",
        "",
        "```",
        "python scripts/build_grounding_gate_demo.py",
        "```",
        "",
        "Outputs:",
        "- `raw_hypotheses.json` — pre-gate report",
        "- `gated_report.json` — what ships to the PDF renderer",
        "- `drop_reasons.json` — per-hypothesis rejection reason",
        "",
        "## Companion asset",
        "",
        "`../README.md` covers the *refutation* side on sanfer_tunnel. This ",
        "file covers the *silence* side. Together they cover both exits from ",
        "the gate.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
