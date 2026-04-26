# SPDX-License-Identifier: MIT
"""Seed prerequisites for the UI feature inserts capture.

- Two memory checkpoints so /checkpoints renders a real timeline.
- A trace_manifest.json for job f748de9e40ca so /trace/<id> renders
  populated evidence/discarded/gate sections (real numbers from the
  Sanfer run, not invented).
"""
from __future__ import annotations

import json
from pathlib import Path

from black_box.memory.checkpoint import _checkpoints_root, checkpoint
from black_box.memory.store import default_memory_root

JOB_ID = "f748de9e40ca"


def seed_checkpoints() -> None:
    root = default_memory_root()
    root.mkdir(parents=True, exist_ok=True)
    # Ensure the active L1/L2 files exist so the snapshot has content.
    for fname in ("L1_case.jsonl", "L2_platform.jsonl"):
        p = root / fname
        if not p.exists():
            p.write_text(
                json.dumps({
                    "case_key": "sanfer_tunnel",
                    "platform": "sanfer-rover-04",
                    "note": "pre-ingest snapshot",
                }) + "\n",
                encoding="utf-8",
            )
    cps = _checkpoints_root(root)
    cps.mkdir(parents=True, exist_ok=True)
    if not any(cps.iterdir()):
        checkpoint("ingestion", "pre-ingest", note="before bag enters memory",
                   provenance="replay", job_id=JOB_ID)
        checkpoint("analysis_turn", "post-grounding-gate",
                   note="after grounding gate (min_evidence=2 PASS)",
                   provenance="replay", job_id=JOB_ID)


def seed_trace_manifest() -> None:
    out_dir = Path("data/reports") / JOB_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "run_provenance": "replay",
        "evidence_used": [
            {"kind": "telemetry_window",
             "source_path": "data/final_runs/sanfer_tunnel/telemetry/rtk_status.csv",
             "t_ns": 1714158420000000000,
             "snippet": "carr_solution=NONE 100% of session, REL_POS_VALID never set",
             "provenance": "replay"},
            {"kind": "frame",
             "source_path": "data/final_runs/sanfer_tunnel/frames/front_cam_0042.jpg",
             "t_ns": 1714158451000000000,
             "snippet": "front-cam: open sky, no tunnel ingress visible",
             "provenance": "replay"},
            {"kind": "chrony_log",
             "source_path": "data/final_runs/sanfer_tunnel/chrony.log",
             "snippet": "stratum stable, no GPS dropout signature",
             "provenance": "replay"},
        ],
        "discarded": [
            {"label": "operator hypothesis: tunnel ingress broke RTK",
             "reason": "RTK was already broken pre-tunnel (carr=NONE entire session)",
             "confidence_at_drop": 0.08},
            {"label": "GPS multipath in canyon segment",
             "reason": "front-cam shows open sky, no canyon geometry",
             "confidence_at_drop": 0.12},
        ],
        "gate": {
            "outcome": "pass",
            "rationale": "3 independent exhibits cross-confirm RTK base-station break",
            "min_evidence": 2,
        },
        "confidence": {
            "score": 0.91,
            "raises": ["3 independent exhibits", "telemetry + vision agree"],
            "lowers": ["no RTK base-station log retrieved (operator-side)"],
        },
    }
    (out_dir / "trace_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


def main() -> int:
    seed_checkpoints()
    seed_trace_manifest()
    print("seeded checkpoints + trace manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
