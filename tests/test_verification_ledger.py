"""#86 — append-only verification ledger.

Verifies:
- Notes append to per-analysis verification_note.md without overwriting.
- Notes append to global JSONL ledger without rewriting prior rows.
- Tamper-evidence: there is no public delete or edit function on the module.
- PolicyAdvisor surfaces disputes as a caveat block.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from black_box.memory import (
    VerificationNote,
    add_note,
    disputes_for_class,
    iter_notes_for,
    now_utc_iso,
)
from black_box.memory import verification as ver_mod


@pytest.fixture(autouse=True)
def _isolate_memory_root(tmp_path, monkeypatch):
    monkeypatch.setattr(ver_mod, "default_memory_root", lambda: tmp_path / "mem")
    yield


def _note(analysis_id: str = "job_a", **over) -> VerificationNote:
    base = dict(
        analysis_id=analysis_id,
        operator_id="lucas",
        written_at=now_utc_iso(),
        agent_conclusion="root cause: pid_saturation",
        real_cause="actually a sensor_timeout from /imu/data",
        disputed_class="pid_saturation",
        severity="dispute",
    )
    base.update(over)
    return VerificationNote(**base)


def test_first_note_creates_md_with_header(tmp_path):
    root = tmp_path / "analysis_a"
    md = add_note(root, _note(analysis_id="analysis_a"))
    text = md.read_text(encoding="utf-8")
    assert text.startswith("# Human verification ledger")
    assert "DISPUTE" in text
    assert "analysis_a" in text


def test_second_note_appends_does_not_overwrite(tmp_path):
    root = tmp_path / "analysis_b"
    add_note(root, _note(analysis_id="analysis_b", real_cause="first cause"))
    add_note(root, _note(analysis_id="analysis_b", real_cause="second, corrected", severity="correction"))
    text = (root / "verification_note.md").read_text(encoding="utf-8")
    assert "first cause" in text
    assert "second, corrected" in text
    assert text.count("###") == 2  # two entries, header is "# "


def test_global_ledger_is_append_only_jsonl(tmp_path):
    root = tmp_path / "analysis_c"
    add_note(root, _note(analysis_id="analysis_c"))
    add_note(root, _note(analysis_id="analysis_c", real_cause="round 2"))
    notes = list(iter_notes_for("analysis_c"))
    assert len(notes) == 2
    assert notes[0].real_cause != notes[1].real_cause


def test_module_exposes_no_delete_or_edit_api():
    forbidden = {"delete_note", "remove_note", "edit_note", "update_note", "overwrite_note"}
    public = {n for n in dir(ver_mod) if not n.startswith("_")}
    assert public.isdisjoint(forbidden), (
        f"verification module must be append-only; found mutator surface: "
        f"{public & forbidden}"
    )


def test_disputes_for_class_returns_matching_notes(tmp_path):
    root = tmp_path / "analysis_d"
    add_note(root, _note(analysis_id="analysis_d", disputed_class="pid_saturation"))
    add_note(root, _note(analysis_id="analysis_d", disputed_class="latency_spike"))
    pid_disputes = disputes_for_class("pid_saturation")
    assert len(pid_disputes) == 1
    assert pid_disputes[0].disputed_class == "pid_saturation"


def test_policy_advisor_surfaces_dispute_caveat(tmp_path):
    from black_box.analysis.policy import PolicyAdvisor
    from black_box.memory import MemoryStack

    root = tmp_path / "analysis_e"
    add_note(root, _note(analysis_id="analysis_e", disputed_class="pid_saturation"))
    add_note(root, _note(analysis_id="analysis_e", disputed_class="pid_saturation"))
    add_note(root, _note(analysis_id="analysis_e", disputed_class="missing_null_check"))

    advisor = PolicyAdvisor(memory=MemoryStack.open(tmp_path / "mem-stack"))
    block = advisor.dispute_caveat_block()
    assert "pid_saturation" in block
    assert "disputed 2 times" in block
    assert "missing_null_check" in block
