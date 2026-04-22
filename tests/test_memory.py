"""Tests for the 4-layer memory stack."""

from __future__ import annotations

import json

import pytest

from black_box.memory import (
    CaseMemory,
    CaseRecord,
    EvalMemory,
    EvalRecord,
    MemoryStack,
    PlatformMemory,
    PlatformPrior,
    TaxonomyCount,
    TaxonomyMemory,
)


@pytest.fixture()
def mem_root(tmp_path):
    return tmp_path / "mem"


def test_case_memory_append_and_filter_by_case(mem_root):
    m = CaseMemory(mem_root)
    m.log(CaseRecord(case_key="c1", kind="hypothesis", payload={"bug": "pid"}))
    m.log(CaseRecord(case_key="c2", kind="evidence", payload={"src": "imu"}))
    m.log(CaseRecord(case_key="c1", kind="steering", payload={"note": "focus"}))

    c1 = m.for_case("c1")
    c2 = m.for_case("c2")
    assert [r.kind for r in c1] == ["hypothesis", "steering"]
    assert len(c2) == 1
    assert c2[0].payload == {"src": "imu"}


def test_case_memory_missing_file_returns_empty(mem_root):
    m = CaseMemory(mem_root)
    assert m.for_case("nonexistent") == []


def test_platform_memory_top_signatures_orders_by_confidence_then_hits(mem_root):
    m = PlatformMemory(mem_root)
    m.log(PlatformPrior(platform="nao6", signature="ramp", bug_class="pid_saturation",
                        confidence=0.8, hits=3))
    m.log(PlatformPrior(platform="nao6", signature="spike", bug_class="latency_spike",
                        confidence=0.8, hits=5))
    m.log(PlatformPrior(platform="nao6", signature="stale", bug_class="sensor_timeout",
                        confidence=0.6, hits=100))
    m.log(PlatformPrior(platform="ur5", signature="deadlock", bug_class="state_machine_deadlock",
                        confidence=0.95, hits=1))

    top = m.top_signatures("nao6", k=2)
    assert [p.signature for p in top] == ["spike", "ramp"]

    ur5_top = m.top_signatures("ur5")
    assert len(ur5_top) == 1
    assert ur5_top[0].platform == "ur5"


def test_platform_memory_filters_by_platform(mem_root):
    m = PlatformMemory(mem_root)
    m.log(PlatformPrior(platform="nao6", signature="a", bug_class="other", confidence=0.5))
    m.log(PlatformPrior(platform="ur5", signature="b", bug_class="other", confidence=0.5))
    assert len(m.priors_for("nao6")) == 1
    assert len(m.priors_for("ur5")) == 1
    assert m.priors_for("tesla") == []


def test_taxonomy_memory_totals(mem_root):
    m = TaxonomyMemory(mem_root)
    m.log(TaxonomyCount(bug_class="pid_saturation", signature="ramp", count=3))
    m.log(TaxonomyCount(bug_class="pid_saturation", signature="oscillation", count=2))
    m.log(TaxonomyCount(bug_class="latency_spike", signature="spike"))

    by_class = m.totals_by_class()
    assert by_class == {"pid_saturation": 5, "latency_spike": 1}

    by_sig = m.totals_by_signature()
    assert by_sig == {"ramp": 3, "oscillation": 2, "spike": 1}


def test_eval_memory_accuracy(mem_root):
    m = EvalMemory(mem_root)
    assert m.accuracy() == 0.0  # empty

    m.log(EvalRecord(case_key="c1", predicted_bug="pid_saturation",
                     ground_truth_bug="pid_saturation", match=True))
    m.log(EvalRecord(case_key="c2", predicted_bug="bad_gain_tuning",
                     ground_truth_bug="pid_saturation", match=False))
    m.log(EvalRecord(case_key="c3", predicted_bug="sensor_timeout",
                     ground_truth_bug="sensor_timeout", match=True))

    assert m.accuracy() == pytest.approx(2 / 3)


def test_eval_memory_accuracy_by_case_and_class(mem_root):
    m = EvalMemory(mem_root)
    assert m.accuracy_by_case() == {}
    assert m.accuracy_by_bug_class() == {}

    # Two rows for c1 (one hit, one miss) and one for c2 (hit).
    m.log(EvalRecord(case_key="c1", predicted_bug="pid_saturation",
                     ground_truth_bug="pid_saturation", match=True))
    m.log(EvalRecord(case_key="c1", predicted_bug="bad_gain_tuning",
                     ground_truth_bug="pid_saturation", match=False))
    m.log(EvalRecord(case_key="c2", predicted_bug="sensor_timeout",
                     ground_truth_bug="sensor_timeout", match=True))

    by_case = m.accuracy_by_case()
    assert by_case == {"c1": pytest.approx(0.5), "c2": pytest.approx(1.0)}

    by_class = m.accuracy_by_bug_class()
    # pid_saturation: 1 hit, 1 miss = 0.5; sensor_timeout: 1 hit = 1.0
    assert by_class == {
        "pid_saturation": pytest.approx(0.5),
        "sensor_timeout": pytest.approx(1.0),
    }


def test_memory_stack_uses_common_root(mem_root):
    stack = MemoryStack.open(mem_root)
    stack.case.log(CaseRecord(case_key="c1", kind="note", payload={}))
    stack.platform.log(
        PlatformPrior(platform="nao6", signature="x", bug_class="other", confidence=0.5)
    )
    stack.taxonomy.log(TaxonomyCount(bug_class="other", signature="x"))
    stack.eval.log(
        EvalRecord(case_key="c1", predicted_bug="other", ground_truth_bug="other", match=True)
    )

    expected = {"L1_case.jsonl", "L2_platform.jsonl", "L3_taxonomy.jsonl", "L4_eval.jsonl"}
    assert {p.name for p in mem_root.iterdir()} == expected


def test_records_roundtrip_jsonl(mem_root):
    m = CaseMemory(mem_root)
    orig = CaseRecord(case_key="c1", kind="hypothesis", payload={"nested": [1, 2, 3]})
    m.log(orig)

    raw = (mem_root / "L1_case.jsonl").read_text().strip()
    parsed = json.loads(raw)
    assert parsed["case_key"] == "c1"
    assert parsed["payload"] == {"nested": [1, 2, 3]}
    assert "t_logged" in parsed

    restored = m.for_case("c1")
    assert len(restored) == 1
    assert restored[0].payload == orig.payload


def test_type_mismatch_raises(mem_root):
    m = CaseMemory(mem_root)
    with pytest.raises(TypeError):
        m._store.append(TaxonomyCount(bug_class="other", signature="x"))


def test_platform_prior_confidence_bounds():
    # Schema enforces [0, 1]; out-of-range should fail validation at construction.
    with pytest.raises(Exception):
        PlatformPrior(platform="p", signature="s", bug_class="other", confidence=1.5)
    with pytest.raises(Exception):
        PlatformPrior(platform="p", signature="s", bug_class="other", confidence=-0.1)
