"""#82 — HITL decisions: durable ledger + apply-patch gate."""
from __future__ import annotations

from pathlib import Path

import pytest

from black_box.memory import (
    PatchNotApprovedError,
    apply_patch_if_approved,
    history_for,
    latest_for,
    record_decision,
    rejected_classes_count,
)
from black_box.memory import decisions as dec_mod


@pytest.fixture(autouse=True)
def _isolate_memory_root(tmp_path, monkeypatch):
    monkeypatch.setattr(dec_mod, "default_memory_root", lambda: tmp_path / "mem")
    yield


def test_record_decision_validates_status(tmp_path):
    with pytest.raises(ValueError):
        record_decision(job_id="j1", status="maybe")


def test_history_and_latest(tmp_path):
    record_decision("j1", "rejected", note="bad evidence")
    record_decision("j1", "approved", note="re-reviewed")
    assert latest_for("j1").status == "approved"
    assert [r.status for r in history_for("j1")] == ["rejected", "approved"]


def test_apply_patch_refuses_without_approval(tmp_path):
    with pytest.raises(PatchNotApprovedError):
        apply_patch_if_approved("j1", "diff --git a b\n", target_root=tmp_path / "out")


def test_apply_patch_refuses_after_rejection(tmp_path):
    record_decision("j1", "rejected")
    with pytest.raises(PatchNotApprovedError):
        apply_patch_if_approved("j1", "diff", target_root=tmp_path / "out")


def test_apply_patch_writes_after_approval(tmp_path):
    record_decision("j1", "approved", note="LGTM")
    out = apply_patch_if_approved("j1", "diff --git a/x b/x\n", target_root=tmp_path / "out")
    assert out.exists()
    assert "diff --git" in out.read_text(encoding="utf-8")


def test_apply_patch_refuses_when_rejection_supersedes_approval(tmp_path):
    record_decision("j1", "approved")
    record_decision("j1", "rejected", note="found regression")
    with pytest.raises(PatchNotApprovedError):
        apply_patch_if_approved("j1", "diff", target_root=tmp_path / "out")


def test_rejection_class_marker_feeds_negative_prior(tmp_path):
    record_decision("j1", "rejected", note="class:pid_saturation reason: not the cause")
    record_decision("j2", "rejected", note="class:pid_saturation other context")
    record_decision("j3", "rejected", note="class:latency_spike unrelated")
    assert rejected_classes_count("pid_saturation") == 2
    assert rejected_classes_count("latency_spike") == 1
    assert rejected_classes_count("calibration_drift") == 0


def test_module_has_no_unsanctioned_apply_function():
    """No public function named '*apply*' exists besides the gated one."""
    public = {n for n in dir(dec_mod) if not n.startswith("_")}
    apply_like = {n for n in public if "apply" in n.lower()}
    assert apply_like == {"apply_patch_if_approved"}, (
        f"unexpected apply-shaped function on memory.decisions: {apply_like}"
    )
