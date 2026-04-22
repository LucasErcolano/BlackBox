"""Real-API smoke test for Managed Agents wiring (PR #7).

Phase 1 — beta-access probe (<$0.02): create+delete a minimal agent.
Phase 2 — full E2E: upload bag → env → agent → session → stream →
         validate usage/stop_reason shape against #7's expectations.

Wall-clock kill-switch at 180 s. Budget hint 2 min in seed prompt.
Logs everything to /tmp/managed_agent_smoke_<ts>.log + stdout.

Exit 0 on PASS, 1 on FAIL. No fixes — diagnosis only.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from anthropic import Anthropic

from black_box.analysis.managed_agent import (
    ANTHROPIC_BETA_HEADER,
    MODEL,
    ForensicAgent,
    ForensicAgentConfig,
    _PRICING,
    _extract_text,
)

BAG = Path("/mnt/hdd/sanfer_sanisidro/2_diagnostics.bag")
WALL_CLOCK_KILL_S = 180.0
BUDGET_MIN = 2
COST_ABORT_USD = 0.75
TS = datetime.now().strftime("%Y%m%dT%H%M%S")
LOG = Path(f"/tmp/managed_agent_smoke_{TS}.log")

_warnings: list[str] = []
_fails: list[str] = []


def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def warn(msg: str) -> None:
    _warnings.append(msg)
    log(f"WARN: {msg}")


def fail(msg: str) -> None:
    _fails.append(msg)
    log(f"FAIL: {msg}")


def dump(label: str, obj) -> None:
    try:
        if hasattr(obj, "model_dump"):
            data = obj.model_dump()
        elif hasattr(obj, "__dict__"):
            data = {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        else:
            data = str(obj)
        log(f"{label}: {json.dumps(data, default=str)[:2000]}")
    except Exception as exc:
        log(f"{label}: <unserializable: {exc}> repr={obj!r}")


def phase1_probe(client: Anthropic) -> bool:
    log("=== PHASE 1: beta-access probe ===")
    try:
        agent = client.beta.agents.create(
            model=MODEL,
            name="blackbox-smoke-probe",
            system="probe",
            tools=[],
            skills=[],
        )
        log(f"probe agent.id={agent.id}")
        try:
            client.beta.agents.delete(agent.id)
            log("probe agent deleted")
        except Exception as exc:
            warn(f"probe-cleanup delete failed: {exc}")
        return True
    except Exception as exc:
        fail(f"beta probe rejected: {type(exc).__name__}: {exc}")
        traceback.print_exc(file=sys.stderr)
        return False


def compute_cost(usage) -> tuple[float, dict]:
    cached = getattr(usage, "cache_read_input_tokens", 0) or 0
    uncached = getattr(usage, "input_tokens", 0) or 0
    cc_obj = getattr(usage, "cache_creation", None)
    cc = 0
    if cc_obj is not None:
        cc = (getattr(cc_obj, "ephemeral_5m_input_tokens", 0) or 0) + (
            getattr(cc_obj, "ephemeral_1h_input_tokens", 0) or 0
        )
        if not cc:
            cc = getattr(cc_obj, "input_tokens", 0) or 0
    output = getattr(usage, "output_tokens", 0) or 0
    cost = (
        uncached * _PRICING["input"]
        + cc * _PRICING["cache_write"]
        + cached * _PRICING["cache_read"]
        + output * _PRICING["output"]
    ) / 1e6
    breakdown = {
        "cached_input": cached,
        "uncached_input": uncached,
        "cache_creation": cc,
        "output": output,
    }
    return cost, breakdown


def validate_shape(session_obj, stop_reasons_seen: set[str]) -> None:
    log("=== shape validation vs PR #7 expectations ===")
    usage = getattr(session_obj, "usage", None)
    if usage is None:
        fail("session.usage is None — cost ledger will log all zeros")
        return

    expected_fields = [
        "cache_read_input_tokens",
        "input_tokens",
        "cache_creation",
        "output_tokens",
    ]
    for f in expected_fields:
        if not hasattr(usage, f) and not (isinstance(usage, dict) and f in usage):
            warn(f"usage missing field: {f} (cost ledger will default to 0)")

    cc_obj = getattr(usage, "cache_creation", None)
    if cc_obj is not None:
        if not (
            hasattr(cc_obj, "ephemeral_5m_input_tokens")
            or hasattr(cc_obj, "ephemeral_1h_input_tokens")
            or hasattr(cc_obj, "input_tokens")
        ):
            warn(
                f"usage.cache_creation has none of the 3 expected subfields; "
                f"fields present: {dir(cc_obj)[-10:]}"
            )

    known_stops = {"end_turn", "max_tokens", "stop_sequence", "tool_use", "error", None}
    for sr in stop_reasons_seen:
        if sr not in known_stops:
            warn(f"unknown stop_reason value: {sr!r} (code does not branch on this)")

    status = getattr(session_obj, "status", None)
    handled_statuses = {"idle", "terminated"}
    if status not in handled_statuses and status is not None:
        warn(
            f"final session.status={status!r} not in {handled_statuses} — "
            f"finalize() polling loop may hang on re-run"
        )


def phase2_e2e(client: Anthropic) -> bool:
    log("=== PHASE 2: full E2E ===")
    if not BAG.exists():
        fail(f"bag missing: {BAG}")
        return False
    log(f"bag: {BAG} size={BAG.stat().st_size} bytes")

    cfg = ForensicAgentConfig(
        task_budget_minutes=BUDGET_MIN,
        mounted_files=[],
        network="egress_only",
        system_prompt=(
            "You are Black Box. A ROS1 bag is mounted under "
            "/mnt/session/uploads/ (find it with `ls`). Do a QUICK "
            "scenario-mining pass: list at most 2 topics present, report "
            "duration, return a minimal JSON report. Budget 2 minutes — "
            "return fast. Do not install packages or do deep analysis."
        ),
    )
    agent = ForensicAgent(cfg, client=client)

    started = time.monotonic()
    session_id = None
    stop_reasons: set[str] = set()

    try:
        log("opening session (upload + env + agent + session.create + seed send) …")
        t0 = time.monotonic()
        session = agent.open_session(bag_path=BAG, case_key=f"smoke_{TS}")
        session_id = session.session_id
        log(f"session opened: id={session_id} open_latency_s={time.monotonic()-t0:.1f}")

        if not callable(getattr(session, "steer", None)):
            fail("session.steer not callable")
        else:
            log("session.steer is callable (not invoked)")

        log("streaming events …")
        event_count = 0
        tool_use_count = 0
        assistant_count = 0
        for ev in session.stream():
            event_count += 1
            etype = ev.get("type")
            if etype == "tool_call":
                tool_use_count += 1
            elif etype == "assistant":
                assistant_count += 1
            if etype == "status":
                sr = ev.get("payload", {}).get("stop_reason")
                if sr is not None:
                    stop_reasons.add(sr)
            if event_count <= 40:
                log(f"event #{event_count}: {json.dumps(ev, default=str)[:400]}")
            elapsed = time.monotonic() - started
            if elapsed > WALL_CLOCK_KILL_S:
                fail(
                    f"wall-clock kill-switch tripped at {elapsed:.1f}s "
                    f"(agent ignored 2-min budget hint)"
                )
                break

        elapsed = time.monotonic() - started
        log(
            f"stream done: events={event_count} tool_use={tool_use_count} "
            f"assistant={assistant_count} elapsed={elapsed:.1f}s"
        )

        log("retrieving final session + usage …")
        final = client.beta.sessions.retrieve(session_id)
        dump("session.retrieve", final)
        validate_shape(final, stop_reasons)

        usage = getattr(final, "usage", None)
        if usage is not None:
            cost, bd = compute_cost(usage)
            log(f"cost=${cost:.4f} breakdown={bd}")
            if cost > COST_ABORT_USD:
                fail(f"cost ${cost:.4f} > ${COST_ABORT_USD} abort threshold")

        try:
            final_text = session._final_text
            if final_text:
                log(f"final_text_first_400: {final_text[:400]!r}")
            else:
                warn("no final assistant text captured during stream — finalize() would re-list events")
        except Exception as exc:
            warn(f"could not inspect _final_text: {exc}")

        return not _fails

    except Exception as exc:
        fail(f"E2E exception: {type(exc).__name__}: {exc}")
        traceback.print_exc(file=sys.stderr)
        with open(LOG, "a") as f:
            traceback.print_exc(file=f)
        return False
    finally:
        if session_id:
            log(f"cleanup: deleting session {session_id} …")
            try:
                client.beta.sessions.delete(session_id)
                log("session deleted")
            except Exception as exc:
                fail(
                    f"ORPHAN RISK: sessions.delete failed: {type(exc).__name__}: {exc} — "
                    f"session {session_id} may continue billing passively. "
                    f"Manual cleanup required via API or dashboard."
                )


def main() -> int:
    log(f"log file: {LOG}")
    log(f"SDK beta header: {ANTHROPIC_BETA_HEADER}")
    log(f"model: {MODEL}")
    log(f"wall-clock kill: {WALL_CLOCK_KILL_S}s")

    if not os.getenv("ANTHROPIC_API_KEY"):
        fail("ANTHROPIC_API_KEY not set")
        print_final()
        return 1

    client = Anthropic()

    ok1 = phase1_probe(client)
    if not ok1:
        log("=== STOPPING: probe failed, skipping E2E ===")
        print_final()
        return 1

    ok2 = phase2_e2e(client)
    print_final(ok2)
    return 0 if (ok2 and not _fails) else 1


def print_final(ok: bool | None = None) -> None:
    print("\n" + "=" * 60)
    if _fails:
        print("RESULT: FAIL")
        for f in _fails:
            print(f"  FAIL: {f}")
    else:
        print("RESULT: PASS")
    if _warnings:
        print(f"\nWARNINGS ({len(_warnings)}):")
        for w in _warnings:
            print(f"  WARN: {w}")
    print(f"\nLog: {LOG}")


if __name__ == "__main__":
    sys.exit(main())
