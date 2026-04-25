# SPDX-License-Identifier: MIT
"""Bounded-context utilities for long-horizon ForensicAgent sessions.

The forensic loop on a multi-hour case can rack up dozens of tool calls
(`grep`, `find`, telemetry windowing, frame sampling). Without discipline,
every turn re-ingests the entire history; cost grows quadratically. This
module ships four mechanics referenced in the *Anthropic prompt-eng for
production* notes:

- **prune_stale_tool_results** — surgical drop of stale tool-result blocks
  beyond a turn-age horizon, preserving any block whose tool_use_id is
  cited later in an assistant message.
- **ToolSearchRegistry** — on-demand tool-schema lookup. The agent sees a
  short manifest in context; full JSONSchema for a tool is fetched only
  when the tool is about to be used.
- **programmatic_call_directive** — short prompt fragment that pushes the
  agent to consolidate N micro tool calls into one sandbox-executed
  script when iterating.
- **InputTokenLedger** — per-turn input-token telemetry sink so a
  regression test can assert bounded growth on a synthetic 200-turn run.

No Anthropic SDK import here — the module is pure-Python and stays unit-
testable without an API key. The agent's send loop is responsible for
calling `prune_stale_tool_results` between turns.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# A "message" here is the Anthropic Messages API shape:
# {"role": "user"|"assistant", "content": [block, ...]}
# A "block" is a dict with "type" in {"text", "tool_use", "tool_result", ...}.

PRUNE_PLACEHOLDER = (
    "[context-hygiene] this tool_result was pruned for age "
    "(see context_hygiene.prune_stale_tool_results); rerun the tool if needed."
)

# Conservative char-per-token proxy used by the ledger. Real token counts come
# from the Anthropic SDK; this is a deterministic offline estimate so tests
# can assert bounded growth without an API key.
CHARS_PER_TOKEN = 4


def _is_referenced_later(tool_use_id: str, messages: list[dict], from_idx: int) -> bool:
    """Return True if tool_use_id appears in any assistant text/tool_use after from_idx."""
    pattern = re.compile(re.escape(tool_use_id))
    for m in messages[from_idx + 1:]:
        if m.get("role") != "assistant":
            continue
        for b in m.get("content", []) or []:
            if b.get("type") == "text" and pattern.search(b.get("text") or ""):
                return True
            if b.get("type") == "tool_use":
                # Some agents reference prior IDs in input.
                if pattern.search(json.dumps(b.get("input") or {})):
                    return True
    return False


def prune_stale_tool_results(
    messages: list[dict],
    max_age_turns: int = 10,
    keep_referenced: bool = True,
) -> list[dict]:
    """Return a new message list with stale tool_result blocks replaced by a marker.

    A tool_result is "stale" when its turn index is more than ``max_age_turns``
    older than the last user turn. When ``keep_referenced`` is True, a stale
    block is kept verbatim if its ``tool_use_id`` is mentioned in any later
    assistant message — that is the agent's working memory and removing it
    would corrupt the reasoning chain.

    The function is pure: it does not mutate the input.
    """
    n = len(messages)
    out: list[dict] = []
    for i, msg in enumerate(messages):
        age = n - 1 - i
        if msg.get("role") != "user" or age <= max_age_turns:
            out.append(msg)
            continue
        new_content: list[dict] = []
        for b in msg.get("content", []) or []:
            if b.get("type") != "tool_result":
                new_content.append(b)
                continue
            tu_id = b.get("tool_use_id", "")
            if keep_referenced and tu_id and _is_referenced_later(tu_id, messages, i):
                new_content.append(b)
            else:
                new_content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu_id,
                        "content": PRUNE_PLACEHOLDER,
                        "is_error": False,
                    }
                )
        out.append({**msg, "content": new_content})
    return out


@dataclass
class ToolSearchRegistry:
    """Lazy tool-schema registry.

    Anthropic's tool_use API requires the full JSONSchema for any tool the
    model can call. Eagerly injecting all of them blows the context. The
    registry holds full schemas internally; the manifest exposed to the
    model is one line per tool. The model issues a `tool_search` directive
    naming the tool, and the agent loop fetches the full schema right
    before the next turn.
    """

    _schemas: dict[str, dict] = field(default_factory=dict)

    def register(self, schema: dict) -> None:
        name = schema.get("name")
        if not name:
            raise ValueError("tool schema missing 'name'")
        self._schemas[name] = schema

    def manifest(self) -> str:
        """Return a one-line-per-tool catalog suitable for the system prompt."""
        if not self._schemas:
            return ""
        rows = []
        for name in sorted(self._schemas):
            s = self._schemas[name]
            desc = (s.get("description") or "").splitlines()[0][:120]
            rows.append(f"- `{name}` — {desc}")
        return (
            "Tool catalog (manifest only — full schemas are fetched on demand "
            "via the `tool_search` directive). To use a tool, first emit "
            '`tool_search:{name}` so the loader can attach its JSONSchema.\n'
            + "\n".join(rows)
        )

    def get(self, name: str) -> dict:
        if name not in self._schemas:
            raise KeyError(f"unknown tool {name!r}; check the manifest.")
        return self._schemas[name]

    def resolve_for_turn(self, requested: Iterable[str]) -> list[dict]:
        """Return the schemas for the names requested in this turn only."""
        return [self.get(n) for n in dict.fromkeys(requested)]


def programmatic_call_directive() -> str:
    """Short prompt fragment that pushes the agent to consolidate iteration.

    Folded into the system preamble. Cache-friendly: the text is stable.
    """
    return (
        "## Tool-call discipline\n\n"
        "When iterating over a list of items (frames, telemetry rows, files), "
        "do NOT emit one tool_use per item. Instead, write a small Python "
        "script that runs the iteration locally and returns a single "
        "consolidated tool_result. This shortens the trajectory and keeps "
        "the trace auditable in one place. If a single sandbox call cannot "
        "fit within the tool_result size budget, batch the iteration into a "
        "small number of calls (≤5), each returning a structured summary."
    )


@dataclass
class InputTokenLedger:
    """Per-turn input-token telemetry sink.

    Append-only JSONL at ``data/context_telemetry.jsonl``. The helper
    ``estimate_tokens`` is a deterministic char proxy; replace with the
    real Anthropic ``count_tokens`` call when wiring into the live agent.
    """

    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def estimate_tokens(messages: list[dict]) -> int:
        chars = 0
        for m in messages:
            content = m.get("content", []) or []
            if isinstance(content, str):
                chars += len(content)
                continue
            for b in content:
                if b.get("type") == "text":
                    chars += len(b.get("text") or "")
                elif b.get("type") == "tool_result":
                    c = b.get("content")
                    if isinstance(c, str):
                        chars += len(c)
                    elif isinstance(c, list):
                        for sub in c:
                            chars += len(sub.get("text") or "")
                elif b.get("type") == "tool_use":
                    chars += len(json.dumps(b.get("input") or {}))
        return chars // CHARS_PER_TOKEN

    def record(self, turn: int, messages: list[dict], note: str = "") -> dict:
        row = {
            "ts": time.time(),
            "turn": turn,
            "tokens_est": self.estimate_tokens(messages),
            "note": note,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        return row
