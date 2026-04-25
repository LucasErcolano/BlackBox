# SPDX-License-Identifier: MIT
"""Tests for memory L1–L3 maintenance (prune + compact)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from black_box.memory.layers import CaseMemory, PlatformMemory, TaxonomyMemory
from black_box.memory.maintenance import (
    compact_platform,
    compact_taxonomy,
    prune_case,
    run_all,
)
from black_box.memory.records import CaseRecord, PlatformPrior, TaxonomyCount


def _t(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def test_prune_case_drops_old_keeps_new(tmp_path: Path) -> None:
    cm = CaseMemory(tmp_path)
    cm.log(CaseRecord(case_key="c1", kind="note", t_logged=_t(60), payload={"k": "old"}))
    cm.log(CaseRecord(case_key="c1", kind="note", t_logged=_t(5), payload={"k": "fresh"}))
    rep = prune_case(tmp_path, max_age_days=30)
    assert rep.before == 2
    assert rep.after == 1
    remaining = CaseMemory(tmp_path).for_case("c1")
    assert len(remaining) == 1
    assert remaining[0].payload["k"] == "fresh"


def test_prune_case_dry_run_changes_nothing(tmp_path: Path) -> None:
    cm = CaseMemory(tmp_path)
    cm.log(CaseRecord(case_key="c1", kind="note", t_logged=_t(99), payload={}))
    rep = prune_case(tmp_path, max_age_days=30, dry_run=True)
    assert rep.before == 1
    assert rep.after == 0  # would-keep count
    assert len(CaseMemory(tmp_path).for_case("c1")) == 1


def test_compact_platform_collapses_dup_signatures(tmp_path: Path) -> None:
    pm = PlatformMemory(tmp_path)
    pm.log(PlatformPrior(platform="rover", signature="sig_a", bug_class="pid", confidence=0.5, hits=2, t_logged=_t(10)))
    pm.log(PlatformPrior(platform="rover", signature="sig_a", bug_class="pid", confidence=0.8, hits=3, t_logged=_t(1)))
    pm.log(PlatformPrior(platform="rover", signature="sig_b", bug_class="timeout", confidence=0.9, hits=1, t_logged=_t(2)))
    rep = compact_platform(tmp_path)
    assert rep.before == 3
    assert rep.after == 2
    priors = {p.signature: p for p in PlatformMemory(tmp_path).priors_for("rover")}
    assert priors["sig_a"].hits == 5
    assert priors["sig_a"].confidence == 0.8


def test_compact_taxonomy_sums_counts(tmp_path: Path) -> None:
    tm = TaxonomyMemory(tmp_path)
    tm.log(TaxonomyCount(bug_class="pid", signature="sig_a", count=2, t_logged=_t(10)))
    tm.log(TaxonomyCount(bug_class="pid", signature="sig_a", count=3, t_logged=_t(1)))
    tm.log(TaxonomyCount(bug_class="timeout", signature="sig_b", count=1, t_logged=_t(2)))
    rep = compact_taxonomy(tmp_path)
    assert rep.before == 3
    assert rep.after == 2
    totals = TaxonomyMemory(tmp_path).totals_by_class()
    assert totals == {"pid": 5, "timeout": 1}


def test_compact_idempotent(tmp_path: Path) -> None:
    tm = TaxonomyMemory(tmp_path)
    tm.log(TaxonomyCount(bug_class="pid", signature="sig_a", count=2))
    tm.log(TaxonomyCount(bug_class="pid", signature="sig_a", count=3))
    compact_taxonomy(tmp_path)
    rep2 = compact_taxonomy(tmp_path)
    assert rep2.before == rep2.after == 1
    assert TaxonomyMemory(tmp_path).totals_by_class() == {"pid": 5}


def test_run_all_returns_three_reports(tmp_path: Path) -> None:
    reports = run_all(tmp_path, max_age_days=30)
    layers = [r.layer for r in reports]
    assert layers == ["L1_case", "L2_platform", "L3_taxonomy"]


def test_l4_eval_untouched_by_run_all(tmp_path: Path) -> None:
    from black_box.memory.layers import EvalMemory
    from black_box.memory.records import EvalRecord
    em = EvalMemory(tmp_path)
    em.log(EvalRecord(case_key="c1", predicted_bug="pid", ground_truth_bug="pid", match=True))
    run_all(tmp_path)
    assert len(EvalMemory(tmp_path).all()) == 1
