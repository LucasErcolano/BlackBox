"""#95 — time-travel checkpoint + rollback smoke."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from black_box.memory import checkpoint as cp_mod


@pytest.fixture
def memroot(tmp_path):
    yield tmp_path / "mem"


def _seed(root: Path, **rows) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for fname, lines in rows.items():
        (root / fname).write_text("\n".join(json.dumps(r) for r in lines) + "\n", encoding="utf-8")


def test_checkpoint_snapshots_active_memory(memroot):
    _seed(memroot, **{
        "L1_case.jsonl": [{"case_key": "case_a", "evidence": "clean"}],
        "L3_taxonomy.jsonl": [{"bug_class": "pid_saturation", "count": 1}],
    })
    m = cp_mod.checkpoint("ingestion", "post-ingest case_a", memory_root=memroot)
    cp_dir = memroot / "checkpoints" / m.checkpoint_id
    assert (cp_dir / "manifest.json").exists()
    assert (cp_dir / "L1_case.jsonl").exists()
    assert (cp_dir / "L3_taxonomy.jsonl").exists()
    assert m.kind == "ingestion"
    assert m.file_sizes["L1_case.jsonl"] > 0


def test_rollback_archives_then_restores(memroot):
    # 1. clean state
    _seed(memroot, **{"L1_case.jsonl": [{"case_key": "case_a", "evidence": "clean"}]})
    cp_clean = cp_mod.checkpoint("ingestion", "pre-poison", memory_root=memroot)

    # 2. poison (additional row, simulating bad ingest)
    with (memroot / "L1_case.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"case_key": "case_a", "evidence": "POISONED!!!"}) + "\n")

    # 3. rollback
    res = cp_mod.rollback(cp_clean.checkpoint_id, memory_root=memroot)
    assert "archived_to" in res
    archive_dir = Path(res["archived_to"])
    assert archive_dir.exists()

    # Active state should match clean checkpoint
    active_lines = (memroot / "L1_case.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(active_lines) == 1
    assert "POISONED" not in active_lines[0]

    # Poisoned state preserved in archive (immutable timeline)
    archive_lines = (archive_dir / "L1_case.jsonl").read_text(encoding="utf-8").splitlines()
    assert any("POISONED" in line for line in archive_lines)


def test_list_checkpoints_returns_in_creation_order(memroot):
    _seed(memroot, **{"L1_case.jsonl": [{"k": 1}]})
    cp1 = cp_mod.checkpoint("ingestion", "first", memory_root=memroot)
    cp2 = cp_mod.checkpoint("analysis_turn", "second", memory_root=memroot)
    cps = cp_mod.list_checkpoints(memory_root=memroot)
    ids = [c.checkpoint_id for c in cps]
    assert ids == sorted(ids)
    assert cp1.checkpoint_id in ids and cp2.checkpoint_id in ids


def test_rollback_unknown_id_raises(memroot):
    memroot.mkdir(parents=True)
    with pytest.raises(KeyError):
        cp_mod.rollback("nope", memory_root=memroot)


def test_deduction_provenance_links_to_checkpoint(memroot):
    deduction = {"case_key": "case_a", "hypothesis": "pid_saturation"}
    _seed(memroot, **{"L1_case.jsonl": [deduction]})
    cp1 = cp_mod.checkpoint("analysis_turn", "after first turn", memory_root=memroot)

    chain = cp_mod.deduction_provenance(deduction, memory_root=memroot)
    assert cp1.checkpoint_id in chain["checkpoint_chain"]


def test_smoke_poison_then_rollback_then_clean_reingest(memroot):
    """Acceptance smoke per #95."""
    _seed(memroot, **{"L1_case.jsonl": [{"case_key": "x", "deduction": "calibration_drift"}]})
    pre = cp_mod.checkpoint("ingestion", "pre-poison", memory_root=memroot)

    # Poison: append wrong deduction
    with (memroot / "L1_case.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"case_key": "x", "deduction": "wrong_class_from_poison"}) + "\n")

    # Rollback
    cp_mod.rollback(pre.checkpoint_id, memory_root=memroot)

    # Clean re-ingest: append the right deduction
    with (memroot / "L1_case.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"case_key": "x", "deduction": "sensor_timeout"}) + "\n")

    rows = [json.loads(l) for l in (memroot / "L1_case.jsonl").read_text().splitlines()]
    deductions = {r["deduction"] for r in rows}
    assert "wrong_class_from_poison" not in deductions
    assert "calibration_drift" in deductions and "sensor_timeout" in deductions
