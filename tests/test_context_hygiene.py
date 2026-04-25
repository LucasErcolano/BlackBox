"""#92 — bounded-context regression on a synthetic 200-turn session."""
from __future__ import annotations

from pathlib import Path

import pytest

from black_box.analysis.context_hygiene import (
    InputTokenLedger,
    ToolSearchRegistry,
    PRUNE_PLACEHOLDER,
    programmatic_call_directive,
    prune_stale_tool_results,
)


def _user_with_tool_result(tu_id: str, payload: str) -> dict:
    return {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": tu_id, "content": payload}],
    }


def _assistant_text(text: str) -> dict:
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def _assistant_tool_use(tu_id: str, name: str, inp: dict) -> dict:
    return {
        "role": "assistant",
        "content": [{"type": "tool_use", "id": tu_id, "name": name, "input": inp}],
    }


def test_prune_stale_replaces_old_tool_results():
    msgs = []
    for i in range(40):
        msgs.append(_assistant_tool_use(f"tu_{i}", "grep", {"q": "x"}))
        msgs.append(_user_with_tool_result(f"tu_{i}", "x" * 5000))

    pruned = prune_stale_tool_results(msgs, max_age_turns=10)
    pruned_results = [
        b
        for m in pruned
        for b in (m.get("content") or [])
        if isinstance(b, dict) and b.get("type") == "tool_result"
        and b.get("content") == PRUNE_PLACEHOLDER
    ]
    # Old half should be largely placeholder'd; recent ~10 turns kept.
    assert len(pruned_results) >= 25


def test_prune_keeps_referenced_tool_results():
    msgs = [
        _assistant_tool_use("tu_keepme", "grep", {"q": "x"}),
        _user_with_tool_result("tu_keepme", "the_evidence_payload"),
    ]
    # Pad with many later turns; reference tu_keepme in a recent assistant text.
    for i in range(50):
        msgs.append(_assistant_text(f"thinking turn {i}"))
        msgs.append(_user_with_tool_result(f"tu_{i}", "noise"))
    msgs.append(_assistant_text("recall: tool_use_id=tu_keepme contained the evidence."))
    msgs.append({"role": "user", "content": [{"type": "text", "text": "next?"}]})

    pruned = prune_stale_tool_results(msgs, max_age_turns=5)
    # The referenced one must still carry its real payload.
    found_payload = False
    for m in pruned:
        for b in m.get("content", []) or []:
            if (
                isinstance(b, dict)
                and b.get("tool_use_id") == "tu_keepme"
                and b.get("content") == "the_evidence_payload"
            ):
                found_payload = True
    assert found_payload, "referenced tool_use_id was pruned despite being cited later"


def test_tool_search_registry_manifest_is_compact():
    reg = ToolSearchRegistry()
    for name in ["grep", "find", "read_bag", "render_plot"]:
        reg.register(
            {
                "name": name,
                "description": f"do {name} thing — long winded explanation that should be truncated " * 10,
                "input_schema": {"type": "object", "properties": {}},
            }
        )
    manifest = reg.manifest()
    assert all(name in manifest for name in ["grep", "find", "read_bag", "render_plot"])
    # Manifest is short — line-per-tool, no JSONSchema bodies.
    assert "input_schema" not in manifest
    assert manifest.count("\n") < 20


def test_tool_search_registry_resolve_returns_only_requested():
    reg = ToolSearchRegistry()
    for name in ["grep", "find", "read_bag"]:
        reg.register({"name": name, "description": name, "input_schema": {}})
    schemas = reg.resolve_for_turn(["grep"])
    assert len(schemas) == 1 and schemas[0]["name"] == "grep"


def test_programmatic_directive_is_stable_string():
    a = programmatic_call_directive()
    b = programmatic_call_directive()
    assert a == b  # cache-friendly
    assert "iterating" in a.lower()


def test_synthetic_200_turn_session_is_bounded(tmp_path):
    """Bounded-growth invariant: with prune at every turn, input-token estimate
    stays within ~constant factor regardless of session length.
    """
    ledger = InputTokenLedger(tmp_path / "ctx.jsonl")
    msgs: list[dict] = []
    sample = [None] * 200
    peak = 0
    for turn in range(200):
        msgs.append(_assistant_tool_use(f"tu_{turn}", "grep", {"q": str(turn)}))
        msgs.append(_user_with_tool_result(f"tu_{turn}", "y" * 4000))
        msgs = prune_stale_tool_results(msgs, max_age_turns=8)
        row = ledger.record(turn=turn, messages=msgs)
        peak = max(peak, row["tokens_est"])

    # Without pruning, 200 turns × ~4000 chars ≈ 200k tokens. With pruning to
    # 8 turns of live tool_result, tokens stay under 30k.
    assert peak < 30_000, f"unbounded growth: peak={peak}"
    rows = (tmp_path / "ctx.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 200
