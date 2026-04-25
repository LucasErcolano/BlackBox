"""#84 — async batch runner: concurrency, resume, cost cap, isolation."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from black_box.eval.batch import create_batch, get_state, run_batch


@pytest.fixture
def repo(tmp_path):
    yield tmp_path


def _runner_ok():
    async def runner(case_key: str, case_root: Path) -> dict:
        await asyncio.sleep(0.01)
        return {"usd_spent": 0.10, "artifact_path": f"reports/{case_key}.md"}
    return runner


def _runner_one_failure(bad_key: str):
    async def runner(case_key: str, case_root: Path) -> dict:
        if case_key == bad_key:
            raise RuntimeError("synthetic failure")
        await asyncio.sleep(0.01)
        return {"usd_spent": 0.10, "artifact_path": f"reports/{case_key}.md"}
    return runner


def test_full_batch_completes(repo):
    manifest = create_batch(["a", "b", "c"], repo_root=repo)
    state = asyncio.run(run_batch(manifest, runner=_runner_ok(), repo_root=repo, case_root=repo))
    assert {s.status for s in state.values()} == {"done"}
    assert len(state) == 3


def test_isolated_failure_does_not_abort_batch(repo):
    manifest = create_batch(["a", "b", "c"], repo_root=repo)
    state = asyncio.run(run_batch(manifest, runner=_runner_one_failure("b"), repo_root=repo, case_root=repo))
    assert state["a"].status == "done"
    assert state["b"].status == "failed"
    assert "synthetic failure" in state["b"].error
    assert state["c"].status == "done"


def test_resume_skips_done_cases(repo):
    manifest = create_batch(["a", "b", "c"], repo_root=repo)
    asyncio.run(run_batch(manifest, runner=_runner_ok(), repo_root=repo, case_root=repo))

    # Re-run with a runner that fails on every call. Anything skipped
    # stays 'done'; nothing should regress to failed.
    async def boom(case_key, case_root):
        raise AssertionError(f"resume must not re-run done case {case_key}")

    state2 = asyncio.run(run_batch(manifest, runner=boom, repo_root=repo, case_root=repo))
    assert all(s.status == "done" for s in state2.values())


def test_cost_cap_aborts_remaining_cases(repo):
    # Plant a costs.jsonl already over the cap.
    (repo / "data").mkdir()
    (repo / "data" / "costs.jsonl").write_text(json.dumps({"usd_cost": 99.0}) + "\n")
    manifest = create_batch(["a", "b", "c"], cost_ceiling_usd=10.0, repo_root=repo)
    state = asyncio.run(run_batch(manifest, runner=_runner_ok(), repo_root=repo, case_root=repo))
    aborted = [k for k, v in state.items() if v.status == "aborted_cap"]
    assert len(aborted) == 3, f"all cases should abort under cap; got {state}"


def test_smoke_three_case_with_mid_run_kill_resumes(repo):
    """Acceptance smoke: start 3-case batch, simulate kill after 1 case, resume."""
    manifest = create_batch(["a", "b", "c"], repo_root=repo)

    # Phase 1: only run 'a'. Pretend the worker died after that (sim by partial manifest).
    async def runner_a_only(case_key, case_root):
        if case_key in ("b", "c"):
            raise RuntimeError("interrupted")
        await asyncio.sleep(0.01)
        return {"usd_spent": 0.05, "artifact_path": f"reports/{case_key}.md"}
    asyncio.run(run_batch(manifest, runner=runner_a_only, repo_root=repo, case_root=repo))

    # Phase 2: resume — full runner. 'a' must NOT be re-run; 'b' and 'c' should complete.
    seen = []
    async def runner_full(case_key, case_root):
        seen.append(case_key)
        await asyncio.sleep(0.01)
        return {"usd_spent": 0.05, "artifact_path": f"reports/{case_key}.md"}
    asyncio.run(run_batch(manifest, runner=runner_full, repo_root=repo, case_root=repo))

    assert "a" not in seen, "resume must not re-run done case"
    assert set(seen) == {"b", "c"}
    state = get_state(manifest.batch_id, repo)
    assert state["a"].status == "done" and state["b"].status == "done" and state["c"].status == "done"
