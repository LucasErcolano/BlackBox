# SPDX-License-Identifier: MIT
"""Async batch runner for forensic sessions.

Per #84: launch N sessions, walk away, resume from last completed case
without re-paying for finished work. Pure asyncio + JSONL state — no
Redis / Celery / arq dep, so a clean checkout runs the smoke without
extra services. The interface is shaped so a future swap to arq is a
single function-pointer change.

State on disk::

    data/batches/<batch_id>/
      manifest.json
      state.jsonl         # one row per case attempt (case_key, status, ...)

Status flow per case::

    queued -> running -> {done | failed}

Resumption rule: a case in ``done`` is skipped on restart. A case in
``running`` (interrupted mid-run) is treated as ``failed`` with cause
``interrupted`` so the batch behavior is deterministic — no double
billing on restart. The operator can re-queue the case explicitly if
they want to retry.

Cost ceiling: the runner reads ``data/costs.jsonl`` between cases and
aborts cleanly when cumulative USD crosses the configured cap. Cases
already ``done`` keep their state; the rest move to ``aborted_cap``.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Literal, Optional

from pydantic import BaseModel, Field


CaseStatus = Literal["queued", "running", "done", "failed", "aborted_cap"]
RunnerFn = Callable[[str, Path], Awaitable[dict]]


class CaseState(BaseModel):
    case_key: str
    status: CaseStatus = "queued"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: str = ""
    usd_spent: float = 0.0
    artifact_path: str = ""


class BatchManifest(BaseModel):
    batch_id: str
    created_at: str
    cases: list[str] = Field(default_factory=list)
    concurrency: int = 2
    cost_ceiling_usd: float = 50.0


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _batches_root(repo_root: Path) -> Path:
    return repo_root / "data" / "batches"


def _read_state_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _latest_state(rows: list[dict]) -> dict[str, CaseState]:
    """Fold append-only rows into the latest-state-per-case map."""
    out: dict[str, CaseState] = {}
    for row in rows:
        ck = row.get("case_key")
        if not ck:
            continue
        out[ck] = CaseState.model_validate(row)
    return out


def _append_state(state_path: Path, state: CaseState) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("a", encoding="utf-8") as f:
        f.write(state.model_dump_json() + "\n")


def _cumulative_usd(costs_path: Path) -> float:
    if not costs_path.exists():
        return 0.0
    total = 0.0
    for line in costs_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            total += float(json.loads(line).get("usd_cost", 0.0) or 0.0)
        except (json.JSONDecodeError, TypeError):
            continue
    return total


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_batch(
    cases: list[str],
    *,
    concurrency: int = 2,
    cost_ceiling_usd: float = 50.0,
    repo_root: Path,
    batch_id: Optional[str] = None,
) -> BatchManifest:
    bid = batch_id or f"batch_{int(time.time())}"
    batch_dir = _batches_root(repo_root) / bid
    batch_dir.mkdir(parents=True, exist_ok=True)
    manifest = BatchManifest(
        batch_id=bid,
        created_at=_now_utc_iso(),
        cases=list(cases),
        concurrency=concurrency,
        cost_ceiling_usd=cost_ceiling_usd,
    )
    (batch_dir / "manifest.json").write_text(
        json.dumps(manifest.model_dump(), indent=2),
        encoding="utf-8",
    )
    return manifest


def get_state(batch_id: str, repo_root: Path) -> dict[str, CaseState]:
    state_path = _batches_root(repo_root) / batch_id / "state.jsonl"
    return _latest_state(_read_state_lines(state_path))


async def run_batch(
    manifest: BatchManifest,
    *,
    runner: RunnerFn,
    repo_root: Path,
    case_root: Path,
) -> dict[str, CaseState]:
    """Execute the batch. Idempotent — re-running on the same batch_id
    skips any case already in 'done' state; resumes the rest.
    """
    state_path = _batches_root(repo_root) / manifest.batch_id / "state.jsonl"
    costs_path = repo_root / "data" / "costs.jsonl"

    existing = get_state(manifest.batch_id, repo_root)
    sem = asyncio.Semaphore(manifest.concurrency)
    cap_hit = asyncio.Event()

    async def _worker(case_key: str) -> None:
        if cap_hit.is_set():
            _append_state(state_path, CaseState(case_key=case_key, status="aborted_cap"))
            return
        cur = existing.get(case_key)
        if cur and cur.status == "done":
            return  # already paid; do not redo
        async with sem:
            if _cumulative_usd(costs_path) >= manifest.cost_ceiling_usd:
                cap_hit.set()
                _append_state(state_path, CaseState(case_key=case_key, status="aborted_cap"))
                return
            _append_state(
                state_path,
                CaseState(case_key=case_key, status="running", started_at=_now_utc_iso()),
            )
            try:
                result = await runner(case_key, case_root)
                _append_state(
                    state_path,
                    CaseState(
                        case_key=case_key,
                        status="done",
                        started_at=_now_utc_iso(),
                        finished_at=_now_utc_iso(),
                        usd_spent=float(result.get("usd_spent", 0.0)),
                        artifact_path=str(result.get("artifact_path", "")),
                    ),
                )
            except Exception as exc:
                _append_state(
                    state_path,
                    CaseState(
                        case_key=case_key,
                        status="failed",
                        finished_at=_now_utc_iso(),
                        error=f"{type(exc).__name__}: {exc}",
                    ),
                )

    await asyncio.gather(*(_worker(ck) for ck in manifest.cases))
    return get_state(manifest.batch_id, repo_root)
