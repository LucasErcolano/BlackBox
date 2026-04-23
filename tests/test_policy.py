"""Tests for the self-improving policy advisor."""
from __future__ import annotations

from pathlib import Path

import pytest

from black_box.analysis.policy import PolicyAdvisor, RegressionAlarm
from black_box.memory import (
    EvalRecord,
    MemoryStack,
    PlatformPrior,
    TaxonomyCount,
)


@pytest.fixture()
def mem(tmp_path: Path) -> MemoryStack:
    return MemoryStack.open(tmp_path / "mem")


# ---------------------------------------------------------------------------
# L2 prime_prompt_block
# ---------------------------------------------------------------------------
def test_prime_block_empty_when_no_platform(mem):
    advisor = PolicyAdvisor(mem, platform=None)
    assert advisor.prime_prompt_block() == ""


def test_prime_block_empty_when_no_priors(mem):
    advisor = PolicyAdvisor(mem, platform="nao6")
    assert advisor.prime_prompt_block() == ""


def test_prime_block_renders_top_k_priors_sorted_by_confidence(mem):
    mem.platform.log(PlatformPrior(platform="nao6", signature="ramp",
                                   bug_class="bad_gain_tuning", confidence=0.9, hits=5))
    mem.platform.log(PlatformPrior(platform="nao6", signature="deadlock",
                                   bug_class="state_machine_deadlock", confidence=0.8, hits=2))
    mem.platform.log(PlatformPrior(platform="nao6", signature="stale",
                                   bug_class="sensor_timeout", confidence=0.6, hits=10))
    # Different platform — must not leak in.
    mem.platform.log(PlatformPrior(platform="ur5", signature="other",
                                   bug_class="pid_saturation", confidence=0.95))

    advisor = PolicyAdvisor(mem, platform="nao6")
    block = advisor.prime_prompt_block(top_k=2)

    assert "nao6" in block
    assert "ur5" not in block
    # Top 2 by confidence: 0.9 (ramp) then 0.8 (deadlock). 0.6 excluded.
    assert "ramp" in block and "deadlock" in block
    assert "stale" not in block
    # The warning footer must be present so the prompt never lets a prior
    # short-circuit case-local evidence.
    assert "weak evidence" in block


# ---------------------------------------------------------------------------
# L3 tie-break
# ---------------------------------------------------------------------------
def test_tie_break_leaves_clear_winner_alone(mem):
    mem.taxonomy.log(TaxonomyCount(bug_class="pid_saturation", signature="s", count=100))
    mem.taxonomy.log(TaxonomyCount(bug_class="bad_gain_tuning", signature="t", count=1))

    advisor = PolicyAdvisor(mem)
    hyps = [
        {"bug_class": "bad_gain_tuning", "confidence": 0.85},  # clear winner
        {"bug_class": "pid_saturation", "confidence": 0.50},
    ]
    out = advisor.apply_tie_break(hyps)
    assert out[0]["bug_class"] == "bad_gain_tuning"  # not promoted despite higher L3
    assert out[1]["bug_class"] == "pid_saturation"


def test_tie_break_promotes_more_frequent_class_on_near_tie(mem):
    mem.taxonomy.log(TaxonomyCount(bug_class="pid_saturation", signature="s", count=20))
    mem.taxonomy.log(TaxonomyCount(bug_class="bad_gain_tuning", signature="t", count=2))

    advisor = PolicyAdvisor(mem)
    hyps = [
        {"bug_class": "bad_gain_tuning", "confidence": 0.55},
        {"bug_class": "pid_saturation", "confidence": 0.52},  # near-tie
    ]
    out = advisor.apply_tie_break(hyps)
    # pid_saturation has much higher L3 frequency — should be promoted.
    assert out[0]["bug_class"] == "pid_saturation"
    assert out[1]["bug_class"] == "bad_gain_tuning"


def test_tie_break_does_not_promote_when_frequencies_also_tie(mem):
    mem.taxonomy.log(TaxonomyCount(bug_class="a", signature="s", count=5))
    mem.taxonomy.log(TaxonomyCount(bug_class="b", signature="t", count=5))

    advisor = PolicyAdvisor(mem)
    hyps = [
        {"bug_class": "a", "confidence": 0.50},
        {"bug_class": "b", "confidence": 0.48},
    ]
    out = advisor.apply_tie_break(hyps)
    assert out[0]["bug_class"] == "a"  # original order kept


def test_tie_break_custom_delta(mem):
    mem.taxonomy.log(TaxonomyCount(bug_class="b", signature="t", count=99))

    advisor = PolicyAdvisor(mem, tie_delta=0.3)
    hyps = [
        {"bug_class": "a", "confidence": 0.80},
        {"bug_class": "b", "confidence": 0.60},  # Δ = 0.20 < 0.30 -> still near-tie
    ]
    out = advisor.apply_tie_break(hyps)
    assert out[0]["bug_class"] == "b"  # higher L3 wins under larger tie_delta


def test_tie_break_handles_short_lists(mem):
    advisor = PolicyAdvisor(mem)
    assert advisor.apply_tie_break([]) == []
    solo = [{"bug_class": "x", "confidence": 0.9}]
    assert advisor.apply_tie_break(solo) == solo


def test_tie_break_accepts_attr_objects(mem):
    mem.taxonomy.log(TaxonomyCount(bug_class="b", signature="t", count=50))

    class H:
        def __init__(self, bug_class, confidence):
            self.bug_class = bug_class
            self.confidence = confidence

    advisor = PolicyAdvisor(mem)
    hyps = [H("a", 0.55), H("b", 0.53)]
    out = advisor.apply_tie_break(hyps)
    assert out[0].bug_class == "b"


# ---------------------------------------------------------------------------
# L4 regression alarms
# ---------------------------------------------------------------------------
def test_no_alarm_under_min_samples(mem):
    mem.eval.log(EvalRecord(case_key="c1", predicted_bug="x",
                            ground_truth_bug="pid_saturation", match=False))
    mem.eval.log(EvalRecord(case_key="c2", predicted_bug="y",
                            ground_truth_bug="pid_saturation", match=False))

    advisor = PolicyAdvisor(mem, regression_threshold=0.6, regression_min_samples=3)
    assert advisor.regression_alarms() == []


def test_alarm_fires_below_threshold_with_enough_samples(mem):
    # 1 hit, 3 misses -> 25% accuracy, 4 samples, below 0.6 threshold.
    mem.eval.log(EvalRecord(case_key="c1", predicted_bug="pid_saturation",
                            ground_truth_bug="pid_saturation", match=True))
    for i in range(3):
        mem.eval.log(EvalRecord(case_key=f"c{i+2}", predicted_bug="bad_gain_tuning",
                                ground_truth_bug="pid_saturation", match=False))
    # Healthy class: 3/3.
    for i in range(3):
        mem.eval.log(EvalRecord(case_key=f"s{i}", predicted_bug="sensor_timeout",
                                ground_truth_bug="sensor_timeout", match=True))

    advisor = PolicyAdvisor(mem, regression_threshold=0.6, regression_min_samples=3)
    alarms = advisor.regression_alarms()
    assert len(alarms) == 1
    alarm = alarms[0]
    assert isinstance(alarm, RegressionAlarm)
    assert alarm.bug_class == "pid_saturation"
    assert alarm.accuracy == pytest.approx(0.25)
    assert alarm.n_samples == 4
    assert alarm.threshold == 0.6


def test_alarms_sorted_by_accuracy_ascending(mem):
    # Class A: 0 / 3 = 0.00
    for i in range(3):
        mem.eval.log(EvalRecord(case_key=f"a{i}", predicted_bug="x",
                                ground_truth_bug="A", match=False))
    # Class B: 1 / 4 = 0.25
    mem.eval.log(EvalRecord(case_key="b0", predicted_bug="B",
                            ground_truth_bug="B", match=True))
    for i in range(3):
        mem.eval.log(EvalRecord(case_key=f"b{i+1}", predicted_bug="x",
                                ground_truth_bug="B", match=False))

    advisor = PolicyAdvisor(mem, regression_threshold=0.6, regression_min_samples=3)
    alarms = advisor.regression_alarms()
    assert [a.bug_class for a in alarms] == ["A", "B"]


def test_no_alarm_when_class_is_healthy(mem):
    for i in range(4):
        mem.eval.log(EvalRecord(case_key=f"c{i}", predicted_bug="x",
                                ground_truth_bug="x", match=True))
    advisor = PolicyAdvisor(mem, regression_threshold=0.6, regression_min_samples=3)
    assert advisor.regression_alarms() == []
