# SPDX-License-Identifier: MIT
"""Time-travel checkpoints over the L1–L4 memory substrate.

Per #95: poisoned evidence enters memory; the operator needs to roll the
agent back to a labeled checkpoint without surgical JSONL edits, and
without losing the original timeline.

Design — three guarantees:

1. **Append-only**: a checkpoint snapshots the L1–L4 JSONL files by
   copy. Source files remain untouched.
2. **Immutable timeline**: rollback never deletes. Files at the active
   memory root are first archived to ``data/memory/_archive_<ts>/``,
   then the checkpoint contents are copied into place. Both halves
   stay on disk.
3. **Forked replay**: the operator can re-emit subsequent events
   selectively against the rolled-back state. The verification ledger
   (#86) is a sibling immutable record so the dispute that triggered
   the rollback stays visible after the fact.

Checkpoint anchors:
- ``ingestion``: before/after a bag enters memory.
- ``analysis_turn``: at each Managed Agents tool boundary the agent
  loop calls ``checkpoint("analysis_turn", note=...)``.
- ``hitl_decision``: paired with every ``record_decision`` write.

Storage layout::

    data/memory/                         # active state
      L1_case.jsonl
      L2_platform.jsonl
      L3_taxonomy.jsonl
      L4_eval.jsonl
      verification.jsonl
      decisions.jsonl
    data/memory/checkpoints/
      <checkpoint_id>/
        manifest.json
        L1_case.jsonl
        L2_platform.jsonl
        ...
    data/memory/_archive_<ts>/<former-active-state>
"""
from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal, Optional

from pydantic import BaseModel, Field

from .store import default_memory_root


CheckpointKind = Literal["ingestion", "analysis_turn", "hitl_decision", "manual"]
Provenance = Literal["live", "replay", "sample"]


_TRACKED_FILES: tuple[str, ...] = (
    "L1_case.jsonl",
    "L2_platform.jsonl",
    "L3_taxonomy.jsonl",
    "L4_eval.jsonl",
    "verification.jsonl",
    "decisions.jsonl",
)


class CheckpointManifest(BaseModel):
    checkpoint_id: str
    kind: CheckpointKind
    label: str
    note: str = ""
    provenance: Provenance = "live"
    created_at: str
    parent_id: Optional[str] = None
    job_id: Optional[str] = None
    file_sizes: dict[str, int] = Field(default_factory=dict)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _checkpoints_root(memory_root: Path) -> Path:
    return memory_root / "checkpoints"


def _archives_root(memory_root: Path) -> Path:
    return memory_root / "_archives"


def checkpoint(
    kind: CheckpointKind,
    label: str,
    *,
    note: str = "",
    provenance: Provenance = "live",
    job_id: Optional[str] = None,
    parent_id: Optional[str] = None,
    memory_root: Optional[Path] = None,
) -> CheckpointManifest:
    """Snapshot active memory under data/memory/checkpoints/<id>/.

    Returns the manifest. Idempotent across kind/label, but the
    checkpoint_id is unique per call so two captures at the same
    boundary do not collide.
    """
    root = memory_root or default_memory_root()
    cp_id = f"{int(time.time() * 1000):013d}_{uuid.uuid4().hex[:8]}"
    cp_dir = _checkpoints_root(root) / cp_id
    cp_dir.mkdir(parents=True, exist_ok=True)

    sizes: dict[str, int] = {}
    for fname in _TRACKED_FILES:
        src = root / fname
        if not src.exists():
            continue
        dst = cp_dir / fname
        shutil.copy2(src, dst)
        sizes[fname] = dst.stat().st_size

    manifest = CheckpointManifest(
        checkpoint_id=cp_id,
        kind=kind,
        label=label,
        note=note,
        provenance=provenance,
        created_at=_now_utc_iso(),
        parent_id=parent_id,
        job_id=job_id,
        file_sizes=sizes,
    )
    (cp_dir / "manifest.json").write_text(
        json.dumps(manifest.model_dump(), indent=2),
        encoding="utf-8",
    )
    return manifest


def list_checkpoints(memory_root: Optional[Path] = None) -> list[CheckpointManifest]:
    root = memory_root or default_memory_root()
    base = _checkpoints_root(root)
    if not base.exists():
        return []
    out: list[CheckpointManifest] = []
    for sub in sorted(base.iterdir()):
        m = sub / "manifest.json"
        if not m.exists():
            continue
        try:
            out.append(CheckpointManifest.model_validate_json(m.read_text(encoding="utf-8")))
        except Exception:  # corrupted manifest — skip rather than fail
            continue
    return out


def get_checkpoint(checkpoint_id: str, memory_root: Optional[Path] = None) -> CheckpointManifest:
    root = memory_root or default_memory_root()
    m = _checkpoints_root(root) / checkpoint_id / "manifest.json"
    if not m.exists():
        raise KeyError(f"unknown checkpoint {checkpoint_id!r}")
    return CheckpointManifest.model_validate_json(m.read_text(encoding="utf-8"))


def rollback(
    checkpoint_id: str,
    *,
    memory_root: Optional[Path] = None,
) -> dict:
    """Restore active memory to the state captured by ``checkpoint_id``.

    Archive-then-copy: the current active files are first copied to
    ``_archives/_archive_<ts>/`` (immutable timeline), then replaced by
    the checkpoint's files. Returns ``{"archived_to": str, "checkpoint_id": str}``.
    """
    root = memory_root or default_memory_root()
    cp_dir = _checkpoints_root(root) / checkpoint_id
    if not cp_dir.exists():
        raise KeyError(f"unknown checkpoint {checkpoint_id!r}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_dir = _archives_root(root) / f"_archive_{ts}_{uuid.uuid4().hex[:6]}"
    archive_dir.mkdir(parents=True, exist_ok=True)

    for fname in _TRACKED_FILES:
        src = root / fname
        if src.exists():
            shutil.copy2(src, archive_dir / fname)
            src.unlink()

    for fname in _TRACKED_FILES:
        cp_src = cp_dir / fname
        if cp_src.exists():
            shutil.copy2(cp_src, root / fname)

    return {
        "checkpoint_id": checkpoint_id,
        "archived_to": str(archive_dir),
    }


def deduction_provenance(
    deduction_record: dict,
    checkpoints: Optional[list[CheckpointManifest]] = None,
    memory_root: Optional[Path] = None,
) -> dict:
    """Locate the most recent checkpoint that contained this deduction.

    Used by the UI provenance graph (#95): each row in the active L1
    case-record stream is linked back to its parent checkpoint so the
    operator can see "this conclusion was added in checkpoint X".
    """
    cps = checkpoints if checkpoints is not None else list_checkpoints(memory_root)
    target_repr = json.dumps(deduction_record, sort_keys=True)
    candidates: list[CheckpointManifest] = []
    root = memory_root or default_memory_root()
    for cp in cps:
        l1 = _checkpoints_root(root) / cp.checkpoint_id / "L1_case.jsonl"
        if not l1.exists():
            continue
        for line in l1.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if json.dumps(row, sort_keys=True) == target_repr:
                candidates.append(cp)
                break
    return {
        "deduction": deduction_record,
        "checkpoint_chain": [cp.checkpoint_id for cp in candidates],
    }
