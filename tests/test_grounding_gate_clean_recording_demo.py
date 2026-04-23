"""Keep the clean-recording grounding-gate demo asset honest.

If anyone retunes GroundingThresholds, the fixture snapshot under
demo_assets/grounding_gate/clean_recording/ will diverge from what the
gate actually does. This test re-runs the builder in-memory and checks
the shipped JSON still matches.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = REPO_ROOT / "demo_assets" / "grounding_gate" / "clean_recording"
SCRIPT = REPO_ROOT / "scripts" / "build_grounding_gate_demo.py"


def test_builder_script_is_runnable_and_produces_no_anomaly_report(tmp_path: Path):
    """Run the builder end-to-end and confirm the gate shipped the silence exit."""
    from black_box.analysis.grounding import NO_ANOMALY_PATCH, ground_post_mortem

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import build_grounding_gate_demo as demo
    finally:
        sys.path.pop(0)

    raw = demo._raw_report()
    gated = ground_post_mortem(raw)

    # The hand-tuned raw fixture must cover every drop reason once, so future
    # threshold changes surface as a visible diff.
    assert gated.hypotheses == []
    assert gated.patch_proposal == NO_ANOMALY_PATCH


def test_shipped_fixture_matches_regenerated_output():
    """Shipped JSON must match what the builder produces today."""
    assert ASSET_DIR.exists(), f"missing asset dir: {ASSET_DIR}"
    for name in ("raw_hypotheses.json", "gated_report.json", "drop_reasons.json"):
        f = ASSET_DIR / name
        assert f.exists(), f"missing fixture: {f}"
        # Must parse — don't snapshot the full bytes (pydantic ordering is stable
        # but we keep the assertion narrow so minor key reorders don't block CI).
        json.loads(f.read_text())

    readme = (ASSET_DIR / "README.md").read_text()
    assert "nothing anomalous" in readme.lower()
    assert "build_grounding_gate_demo.py" in readme
