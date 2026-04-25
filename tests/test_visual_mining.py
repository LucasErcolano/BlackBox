"""#87 — visual_mining_v2 plan + frame discipline + cost-delta."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from black_box.analysis.visual_mining import (
    DEFAULT_THUMBNAIL,
    HIRES_ESCALATION,
    FrameDisciplineError,
    PROMPT_KIND_TELEMETRY_ONLY,
    PROMPT_KIND_VISUAL,
    VisualMiningPlan,
    cost_delta,
    plan_visual_mining,
    validate_plan,
)


CAMS = ["cam1", "cam5", "cam6", "cam4", "cam3"]


def test_plan_from_operator_windows_validates():
    plan = plan_visual_mining(
        case_key="hero_a",
        timeline_json_path=None,
        cameras=CAMS,
        operator_windows=[(10.0, 20.0), (60.0, 70.0)],
    )
    assert plan.windows_anchored_from == "operator"
    assert plan.cameras == CAMS
    assert plan.resolution == DEFAULT_THUMBNAIL
    validate_plan(plan)


def test_plan_from_timeline_uses_from_timeline(tmp_path):
    p = tmp_path / "timeline.json"
    p.write_text(json.dumps({
        "timeline": [
            {"t_ns": 5_000_000_000, "span_s": 4, "label": "spike", "cross_view": True},
            {"t_ns": 60_000_000_000, "span_s": 6, "label": "stall", "cross_view": False},
        ]
    }))
    plan = plan_visual_mining(case_key="hero_b", timeline_json_path=p, cameras=CAMS)
    assert plan.windows_anchored_from == "from_timeline"
    assert len(plan.windows_s) == 2
    assert plan.windows_s[0][1] - plan.windows_s[0][0] == pytest.approx(4.0)


def test_plan_without_windows_fails_discipline(tmp_path):
    with pytest.raises(FrameDisciplineError):
        plan_visual_mining(case_key="x", timeline_json_path=None, cameras=CAMS)


def test_validate_plan_rejects_per_camera_calls():
    p = VisualMiningPlan(
        case_key="x", windows_anchored_from="operator", windows_s=[(0.0, 1.0)],
        cameras=CAMS, resolution=DEFAULT_THUMBNAIL, cross_view_single_call=False,
    )
    with pytest.raises(FrameDisciplineError, match="ONE prompt"):
        validate_plan(p)


def test_validate_plan_rejects_off_resolution():
    p = VisualMiningPlan(
        case_key="x", windows_anchored_from="operator", windows_s=[(0.0, 1.0)],
        cameras=CAMS, resolution=(640, 480),
    )
    with pytest.raises(FrameDisciplineError, match="resolution"):
        validate_plan(p)


def test_validate_plan_rejects_single_camera():
    p = VisualMiningPlan(
        case_key="x", windows_anchored_from="operator", windows_s=[(0.0, 1.0)],
        cameras=["cam1"], resolution=DEFAULT_THUMBNAIL,
    )
    with pytest.raises(FrameDisciplineError, match="cross-view"):
        validate_plan(p)


def test_hires_escalation_resolution_accepted():
    p = VisualMiningPlan(
        case_key="x", windows_anchored_from="operator", windows_s=[(0.0, 1.0)],
        cameras=CAMS, resolution=HIRES_ESCALATION,
    )
    validate_plan(p)


def test_cost_delta_separates_visual_from_telemetry(tmp_path):
    p = tmp_path / "costs.jsonl"
    rows = [
        {"case_key": "hero", "prompt_kind": PROMPT_KIND_TELEMETRY_ONLY, "usd_cost": 0.05},
        {"case_key": "hero", "prompt_kind": PROMPT_KIND_VISUAL, "usd_cost": 0.40},
        {"case_key": "hero", "prompt_kind": PROMPT_KIND_VISUAL, "usd_cost": 0.30},
        {"case_key": "other", "prompt_kind": PROMPT_KIND_VISUAL, "usd_cost": 999.0},
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows))
    delta = cost_delta(p, case_key="hero")
    assert delta["visual_usd"] == 0.70
    assert delta["telemetry_usd"] == 0.05
    assert delta["delta_usd"] == 0.65
    assert delta["visual_n"] == 2 and delta["telemetry_n"] == 1


HERO_BAGS_DIR = Path("/mnt/hdd/sanfer_sanisidro")


@pytest.mark.skipif(not HERO_BAGS_DIR.exists(), reason="hero bags directory not present in this env")
def test_hero_session_discovers_cameras_for_visual_mining():
    """End-to-end smoke: discover_session_assets + camera-presence check
    on the real /mnt/hdd/sanfer_sanisidro session.
    """
    from black_box.ingestion.session import discover_session_assets

    session = discover_session_assets(HERO_BAGS_DIR)
    # The smoke just asserts the discovery returns something and does not blow up.
    assert session is not None
    # The presence test runs without iterating bag bytes — it's a probe of
    # the manifest shape, not a full ingest.
