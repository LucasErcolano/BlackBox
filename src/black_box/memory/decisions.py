# SPDX-License-Identifier: MIT
"""Durable HITL decision ledger.

Per #82 the contract is:
    a patch is never applied without an explicit human approval, and the
    decision is part of the report.

Implementation: append-only JSONL at `data/memory/decisions.jsonl`. The
existing UI per-job `<job_id>.decision.json` stays as the latest-state
cache; this module is the audit log + the gate function.

`apply_patch_if_approved` is the single allowed write to disk for any
patch. Anything that bypasses it is a privacy/safety bug. The test suite
asserts that bypass-shaped APIs do not exist on the public surface.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from pydantic import BaseModel, Field

from .store import JsonlStore, default_memory_root


class DecisionRecord(BaseModel):
    job_id: str
    status: str  # "approved" | "rejected"
    decided_at: str
    operator: str = Field(default="anonymous")
    note: str = ""


def _store() -> JsonlStore:
    return JsonlStore(default_memory_root() / "decisions.jsonl", DecisionRecord)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_decision(
    job_id: str,
    status: str,
    note: str = "",
    operator: str = "anonymous",
) -> DecisionRecord:
    if status not in ("approved", "rejected"):
        raise ValueError(f"status must be 'approved' or 'rejected', got {status!r}")
    rec = DecisionRecord(
        job_id=job_id,
        status=status,
        decided_at=_now_utc_iso(),
        operator=operator,
        note=note,
    )
    _store().append(rec)
    return rec


def latest_for(job_id: str) -> Optional[DecisionRecord]:
    last: Optional[DecisionRecord] = None
    for r in _store().iter_all():
        if r.job_id == job_id:
            last = r  # type: ignore[assignment]
    return last


def history_for(job_id: str) -> list[DecisionRecord]:
    return [r for r in _store().iter_all() if r.job_id == job_id]  # type: ignore[misc]


def rejected_classes_count(taxonomy_class: str) -> int:
    """Negative-prior input: how many times a hypothesis class has been rejected.

    Reads the optional ``note`` for ``class:<name>`` markers — an
    operator who wants the rejection to feed PolicyAdvisor includes
    this tag in the rejection note.
    """
    needle = f"class:{taxonomy_class}"
    return sum(
        1
        for r in _store().iter_all()
        if r.status == "rejected" and needle in (r.note or "")  # type: ignore[union-attr]
    )


class PatchNotApprovedError(RuntimeError):
    """Raised when patch application is attempted without an approved record."""


def apply_patch_if_approved(
    job_id: str,
    patch_blob: str,
    target_root: Path,
) -> Path:
    """The ONLY sanctioned path that writes a patch to disk.

    Refuses to write unless the latest decision for ``job_id`` is
    ``approved``. Raises ``PatchNotApprovedError`` otherwise. Returns the
    path of the written patch file.
    """
    latest = latest_for(job_id)
    if latest is None or latest.status != "approved":
        raise PatchNotApprovedError(
            f"refusing to apply patch for job {job_id!r}: "
            f"latest decision is {latest.status if latest else 'none'}"
        )
    out = Path(target_root) / f"{job_id}.patch"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(patch_blob, encoding="utf-8")
    return out
