"""Opus 4.7 vs 4.6 A/B harness — model parametrization and dry-run wiring."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_compare_mod():
    spec = importlib.util.spec_from_file_location(
        "_compare_opus_models", ROOT / "scripts" / "compare_opus_models.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_claude_client_accepts_model_arg(monkeypatch):
    """ClaudeClient(model=...) overrides default; per-model pricing applied."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.delenv("BLACKBOX_MODEL", raising=False)
    monkeypatch.delenv("OPUS_PRICING_JSON", raising=False)

    from black_box.analysis import ClaudeClient

    c46 = ClaudeClient(model="claude-opus-4-6")
    c47 = ClaudeClient(model="claude-opus-4-7")
    assert c46.model == "claude-opus-4-6"
    assert c47.model == "claude-opus-4-7"
    assert c46.pricing == ClaudeClient.PRICING_BY_MODEL["claude-opus-4-6"]
    assert c47.pricing == ClaudeClient.PRICING_BY_MODEL["claude-opus-4-7"]


def test_claude_client_reads_blackbox_model_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setenv("BLACKBOX_MODEL", "claude-opus-4-6")
    monkeypatch.delenv("OPUS_PRICING_JSON", raising=False)

    from black_box.analysis import ClaudeClient
    assert ClaudeClient().model == "claude-opus-4-6"


def test_compare_dry_run_lists_default_pair():
    res = subprocess.run(
        [sys.executable, "scripts/compare_opus_models.py", "--dry-run"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0, res.stderr
    assert "claude-opus-4-6" in res.stdout
    assert "claude-opus-4-7" in res.stdout
    assert "Dry-run" in res.stdout


def test_default_uses_all_supported_cases():
    """Empty --cases default → harness picks every non-skeleton case with telemetry."""
    res = subprocess.run(
        [sys.executable, "scripts/compare_opus_models.py", "--dry-run"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0, res.stderr
    # rtk_heading_break_01 has telemetry + non-skeleton status — must appear by default.
    assert "rtk_heading_break_01" in res.stdout
    assert "bad_gain_01" in res.stdout


def test_patch_target_match_substring():
    mod = _load_compare_mod()
    gt = {"file": "source/buggy/heading_controller.py",
          "function": "HeadingController.step"}
    assert mod._patch_target_match(
        "diff --git a/source/buggy/heading_controller.py ...", gt) is True
    assert mod._patch_target_match("call .step() with reduced gain", gt) is True
    assert mod._patch_target_match("rewrite the planner module", gt) is False
    assert mod._patch_target_match("", gt) is False
    assert mod._patch_target_match("anything", {}) is False


def test_patch_target_breakdown_strict_both():
    mod = _load_compare_mod()
    gt = {"file": "source/buggy/heading_controller.py",
          "function": "HeadingController.step"}
    f, fn, both = mod._patch_target_breakdown(
        "patch heading_controller.py inside step()", gt)
    assert f is True and fn is True and both is True
    f, fn, both = mod._patch_target_breakdown(
        "patch heading_controller.py only", gt)
    assert f is True and fn is False and both is False
    f, fn, both = mod._patch_target_breakdown("call step() somewhere", gt)
    assert f is False and fn is True and both is False
    f, fn, both = mod._patch_target_breakdown("nope", gt)
    assert (f, fn, both) == (False, False, False)


def test_flip_rate():
    mod = _load_compare_mod()
    assert mod._flip_rate(["a", "a", "a"]) == 0.0
    assert mod._flip_rate(["a", "b"]) == 1.0
    # 3 preds [a,a,b], pairs (a,a)(a,b)(a,b) -> 2 disagree / 3 = 2/3
    assert abs(mod._flip_rate(["a", "a", "b"]) - (2 / 3)) < 1e-9
    assert mod._flip_rate(["a"]) == 0.0
    assert mod._flip_rate([]) == 0.0


def test_aggregate_brier_and_per_correct():
    mod = _load_compare_mod()
    rows = [
        mod.CaseSeedResult(
            case_key="c1", model="m", seed=0,
            ground_truth_bug="x", predicted_bug="x", bug_match=True,
            patch_target_file="", patch_target_function="",
            pt_file_match=True, pt_function_match=False, pt_both_match=False,
            confidence=0.8, evidence_count=3, tool_error=False,
            cost_usd=0.1, wall_time_s=10.0, notes="ok",
        ),
        mod.CaseSeedResult(
            case_key="c1", model="m", seed=1,
            ground_truth_bug="x", predicted_bug="y", bug_match=False,
            patch_target_file="", patch_target_function="",
            pt_file_match=False, pt_function_match=False, pt_both_match=False,
            confidence=0.6, evidence_count=2, tool_error=False,
            cost_usd=0.2, wall_time_s=20.0, notes="ok",
        ),
    ]
    agg = mod._aggregate("m", rows, seeds=2)
    assert agg.bug_match_count == 1
    assert agg.bug_match_rate == 0.5
    # Brier = ((0.8 - 1)^2 + (0.6 - 0)^2) / 2 = (0.04 + 0.36)/2 = 0.20
    assert abs(agg.brier_score - 0.20) < 1e-9
    # 1 correct -> $0.30 / 1 = $0.30; wall 30s / 1 = 30s
    assert abs(agg.usd_per_correct - 0.30) < 1e-9
    assert abs(agg.wall_per_correct - 30.0) < 1e-9
    # Single case, predictions ["x","y"] -> flip=1.0
    assert agg.mean_flip_rate == 1.0


def test_operator_hypothesis_extraction():
    mod = _load_compare_mod()
    # No anti_hypothesis, no operator_narrative -> None
    assert mod._operator_hypothesis({"bug_class": "x"}) is None
    # operator_narrative without refutes_operator -> None
    assert mod._operator_hypothesis(
        {"operator_narrative": "tunnel did it"}) is None
    # refutes_operator + operator_narrative -> returned
    assert mod._operator_hypothesis(
        {"operator_narrative": "tunnel did it", "refutes_operator": True}
    ) == "tunnel did it"
    # anti_hypothesis.operator_report is preferred
    assert mod._operator_hypothesis(
        {"anti_hypothesis": {"operator_report": "GPS fails in tunnel"}}
    ) == "GPS fails in tunnel"


def test_refutation_keyword_match():
    mod = _load_compare_mod()
    op = "GPS fails when the car passes under a tunnel"
    # Positive refutation signals
    assert mod._scores_refutation("Failure is session-wide.", op) is True
    assert mod._scores_refutation("Pre-existing RTK config break.", op) is True
    assert mod._scores_refutation("Carrier-phase never engaged.", op) is True
    assert mod._scores_refutation("navrelposned flags FLAGS_REL_POS_VALID never set.", op) is True
    assert mod._scores_refutation("Sensor timeout throughout the bag.", op) is True
    assert mod._scores_refutation("RTCM stream drop independent of tunnel.", op) is True
    assert mod._scores_refutation("Hypothesis contradicts the operator narrative.", op) is True
    # Confirms operator → no refutation signal
    assert mod._scores_refutation("Tunnel caused GNSS dropout.", op) is False
    assert mod._scores_refutation("", op) is False
    assert mod._scores_refutation("anything", "") is False


def test_no_grounding_flag_recognized():
    res = subprocess.run(
        [sys.executable, "scripts/compare_opus_models.py",
         "--no-grounding", "--dry-run"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0, res.stderr
    assert "Dry-run" in res.stdout


def test_operator_mode_flag_accepts_all_three():
    for mode in ("none", "native", "false"):
        res = subprocess.run(
            [sys.executable, "scripts/compare_opus_models.py",
             "--operator-mode", mode, "--dry-run"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        )
        assert res.returncode == 0, res.stderr
    bad = subprocess.run(
        [sys.executable, "scripts/compare_opus_models.py",
         "--operator-mode", "bogus", "--dry-run"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
    )
    assert bad.returncode != 0


def test_resolve_operator_text_modes():
    mod = _load_compare_mod()
    gt_native = {"operator_narrative": "tunnel did it", "refutes_operator": True}
    gt_no_native = {}
    assert mod._resolve_operator_text("any_case", gt_native, "none") is None
    assert mod._resolve_operator_text("any_case", gt_native, "native") == "tunnel did it"
    assert mod._resolve_operator_text("any_case", gt_no_native, "native") is None
    # 'false' mode reads FALSE_OPERATOR_BY_CASE map regardless of gt
    txt = mod._resolve_operator_text("bad_gain_01", gt_no_native, "false")
    assert txt is not None and "IMU" in txt
    assert mod._resolve_operator_text("not_in_map", gt_no_native, "false") is None
    import pytest
    with pytest.raises(ValueError):
        mod._resolve_operator_text("x", {}, "garbage")


def test_is_under_specified():
    mod = _load_compare_mod()
    # Explicit override
    assert mod._is_under_specified({"under_specified": True}) is True
    # Rationale signal
    assert mod._is_under_specified(
        {"scoring": {"bug_class_rationale": "no exact slot — closed taxonomy mismatch"}}
    ) is True
    # Multiple accepted classes
    assert mod._is_under_specified(
        {"scoring": {"bug_class_match": ["other", "sensor_timeout", "calibration_drift"]}}
    ) is True
    # Single class accepted -> solvable
    assert mod._is_under_specified(
        {"scoring": {"bug_class_match": ["bad_gain_tuning"]}}
    ) is False
    # No scoring at all -> solvable
    assert mod._is_under_specified({"bug_class": "x"}) is False


def test_aggregate_abstention_and_solvable_subsets():
    mod = _load_compare_mod()

    def _row(case, under, abst, match, conf=0.8):
        return mod.CaseSeedResult(
            case_key=case, model="m", seed=0,
            ground_truth_bug="x", predicted_bug=("error" if abst else "x"),
            bug_match=match,
            patch_target_file="", patch_target_function="",
            pt_file_match=False, pt_function_match=False, pt_both_match=False,
            confidence=(0.0 if abst else conf), evidence_count=(0 if abst else 3),
            tool_error=False, cost_usd=0.1, wall_time_s=10.0, notes="ok",
            is_under_specified=under, abstained=abst,
        )
    rows = [
        _row("rtk", True, True, False),    # under-specified, abstained -> abst_correct
        _row("rtk", True, False, True),    # under-specified, committed -> not abst_correct
        _row("good_a", False, False, True),
        _row("good_b", False, False, False),
    ]
    agg = mod._aggregate("m", rows, seeds=1)
    assert agg.n_under_specified_runs == 2
    assert agg.abstention_correctness == 0.5  # 1 of 2 abstained
    assert agg.n_solvable_runs == 2
    assert agg.solvable_accuracy == 0.5  # 1 of 2 matched


def test_run_case_seed_marks_abstention(monkeypatch):
    """Empty hypotheses + clean notes -> abstained=True, predicted=='error'."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    mod = _load_compare_mod()
    from black_box.analysis import ClaudeClient

    class FakeReport:
        timeline = []
        hypotheses = []
        patch_proposal = ""

    class FakeCost:
        usd_cost = 0.05

    def fake_analyze(self, **kwargs):
        return FakeReport(), FakeCost()

    monkeypatch.setattr(ClaudeClient, "analyze", fake_analyze)
    case = ROOT / "black-box-bench" / "cases" / "bad_gain_01"
    r = mod._run_case_seed(case, "claude-opus-4-7", seed=0, temperature=1.0)
    assert r.predicted_bug == "error"
    assert r.abstained is True
    assert r.tool_error is False


def test_aggregate_includes_refutation():
    mod = _load_compare_mod()
    rows = [
        mod.CaseSeedResult(
            case_key="rtk", model="m", seed=0,
            ground_truth_bug="x", predicted_bug="x", bug_match=True,
            patch_target_file="", patch_target_function="",
            pt_file_match=False, pt_function_match=False, pt_both_match=False,
            confidence=0.8, evidence_count=3, tool_error=False,
            cost_usd=0.1, wall_time_s=10.0, notes="ok",
            has_operator_hypothesis=True, refutes_operator=True,
        ),
        mod.CaseSeedResult(
            case_key="rtk", model="m", seed=1,
            ground_truth_bug="x", predicted_bug="x", bug_match=True,
            patch_target_file="", patch_target_function="",
            pt_file_match=False, pt_function_match=False, pt_both_match=False,
            confidence=0.8, evidence_count=3, tool_error=False,
            cost_usd=0.1, wall_time_s=10.0, notes="ok",
            has_operator_hypothesis=True, refutes_operator=False,
        ),
        mod.CaseSeedResult(
            case_key="other", model="m", seed=0,
            ground_truth_bug="x", predicted_bug="x", bug_match=True,
            patch_target_file="", patch_target_function="",
            pt_file_match=False, pt_function_match=False, pt_both_match=False,
            confidence=0.8, evidence_count=3, tool_error=False,
            cost_usd=0.1, wall_time_s=10.0, notes="ok",
            has_operator_hypothesis=False, refutes_operator=False,
        ),
    ]
    agg = mod._aggregate("m", rows, seeds=2)
    # Only 2 rows have operator hypothesis; 1 of 2 refutes
    assert agg.n_refutation_runs == 2
    assert agg.refutation_rate == 0.5


def test_aggregate_zero_correct_per_correct_inf():
    import math as _math
    mod = _load_compare_mod()
    row = mod.CaseSeedResult(
        case_key="c1", model="m", seed=0,
        ground_truth_bug="x", predicted_bug="y", bug_match=False,
        patch_target_file="", patch_target_function="",
        pt_file_match=False, pt_function_match=False, pt_both_match=False,
        confidence=0.5, evidence_count=1, tool_error=False,
        cost_usd=0.1, wall_time_s=5.0, notes="ok",
    )
    agg = mod._aggregate("m", [row], seeds=1)
    assert _math.isinf(agg.usd_per_correct)
    assert _math.isinf(agg.wall_per_correct)


def test_claude_client_temperature_passthrough(monkeypatch):
    """analyze(temperature=...) reaches anthropic SDK kwargs."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    from black_box.analysis import ClaudeClient, post_mortem_prompt

    captured: dict = {}

    class FakeUsage:
        input_tokens = 10
        output_tokens = 5
        cache_read_input_tokens = 0
        cache_creation_input_tokens = 0

    class FakeContentBlock:
        text = '{"timeline": [], "hypotheses": [], "root_cause_idx": 0, "patch_proposal": ""}'

    class FakeResponse:
        content = [FakeContentBlock()]
        usage = FakeUsage()

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    c = ClaudeClient(model="claude-opus-4-7")
    c.client = FakeClient()
    spec = post_mortem_prompt()
    c.analyze(prompt_spec=spec,
              user_fields={"bag_summary": "x", "synced_frames_description": "x",
                           "code_snippets": "x"},
              temperature=0.7,
              apply_grounding=False)
    assert captured.get("temperature") == 0.7
    # No temperature => key absent
    captured.clear()
    c.analyze(prompt_spec=spec,
              user_fields={"bag_summary": "x", "synced_frames_description": "x",
                           "code_snippets": "x"},
              apply_grounding=False)
    assert "temperature" not in captured
