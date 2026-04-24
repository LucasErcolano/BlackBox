# SPDX-License-Identifier: MIT
"""Managed Agents integration for long-horizon bag replay.

Real wiring against ``anthropic>=0.96`` beta ``managed-agents-2026-04-01``:

    * **Agent**       -> ``client.beta.agents.create``
    * **Environment** -> ``client.beta.environments.create``  (cloud config)
    * **Files**       -> ``client.beta.files.upload`` (bag, artefacts) then
                         referenced from the Session as ``file`` resources.
    * **Session**     -> ``client.beta.sessions.create`` (agent+env+resources)
    * **Events**      -> ``client.beta.sessions.events.stream`` (live) with
                         ``.list`` fallback; ``events.send`` for steering.
    * **Outcomes**    -> final ``agent.message`` event parsed as JSON and
                         validated against ``PostMortemReport``.

Rate limits per docs: 60 create/min, 600 read/min -> tiny local throttle.

Usage::

    agent = ForensicAgent(ForensicAgentConfig(task_budget_minutes=15))
    session = agent.open_session(bag_path=Path("/mnt/bag"), case_key="crash_001")
    for event in session.stream():
        ui.push(event)
    session.steer("focus on the 12s-15s window, ignore earlier")
    report = session.finalize()
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal

from anthropic import Anthropic
from pydantic import ValidationError

from .schemas import PostMortemReport
from ..memory import CaseRecord, MemoryStack, TaxonomyCount


# ---------------------------------------------------------------------------
# Beta handshake
# ---------------------------------------------------------------------------
ANTHROPIC_BETA_HEADER = "managed-agents-2026-04-01"
MODEL = "claude-opus-4-7"

# Logical tool names we care about; mapped to the SDK's closed set when
# building agent tool configs. SDK tools as of 2026-04-01:
#   bash, edit, read, write, glob, grep, web_fetch, web_search
BUILTIN_TOOLS: tuple[str, ...] = (
    "bash",
    "file_read",
    "file_write",
    "file_edit",
    "file_glob",
    "file_grep",
    "web_search",
    "web_fetch",
    "mcp",
)

_TOOL_ALIASES: dict[str, str] = {
    "bash": "bash",
    "file_read": "read",
    "file_write": "write",
    "file_edit": "edit",
    "file_glob": "glob",
    "file_grep": "grep",
    "web_search": "web_search",
    "web_fetch": "web_fetch",
}

_SDK_TOOL_NAMES: frozenset[str] = frozenset(
    {"bash", "read", "write", "edit", "glob", "grep", "web_fetch", "web_search"}
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass
class ForensicAgentConfig:
    """Declarative spec for the forensic Agent + its Environment."""

    task_budget_minutes: int = 15
    model: str = MODEL
    system_prompt: str = (
        "You are Black Box, a forensic copilot for robot incidents. "
        "Uploaded artifacts (bag, source tree, etc.) are mounted under "
        "/mnt/session/uploads/ — list that directory first to discover them. "
        "Produce an evidence-grounded post-mortem."
    )
    tools: tuple[str, ...] = BUILTIN_TOOLS
    mcp_servers: list[dict] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)          # e.g. ["ros-bag-decoder"]
    mounted_files: list[Path] = field(default_factory=list)  # bag, source tree
    network: Literal["none", "egress_only"] = "egress_only"
    environment_template: str = "python-3.11-ros-tools"
    agent_name: str = "black-box-forensic"


# ---------------------------------------------------------------------------
# Rate limit throttle (60 create/min, 600 read/min)
# ---------------------------------------------------------------------------
class _RateLimiter:
    """Sliding-window limiter. One-per-process; guarded by a lock."""

    def __init__(self, max_per_window: int, window_seconds: float = 60.0) -> None:
        self._max = max_per_window
        self._window = window_seconds
        self._events: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            cutoff = now - self._window
            while self._events and self._events[0] < cutoff:
                self._events.popleft()
            if len(self._events) >= self._max:
                sleep_for = self._events[0] + self._window - now
                if sleep_for > 0:
                    time.sleep(sleep_for)
                    now = time.monotonic()
                    cutoff = now - self._window
                    while self._events and self._events[0] < cutoff:
                        self._events.popleft()
            self._events.append(now)


_CREATE_LIMITER = _RateLimiter(max_per_window=60)
_READ_LIMITER = _RateLimiter(max_per_window=600)


# ---------------------------------------------------------------------------
# Cost logging (re-uses data/costs.jsonl from claude_client)
# ---------------------------------------------------------------------------
def _find_repo_root() -> Path:
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return Path.cwd()


def _costs_file() -> Path:
    root = _find_repo_root()
    costs_dir = root / "data"
    costs_dir.mkdir(parents=True, exist_ok=True)
    return costs_dir / "costs.jsonl"


_PRICING = {
    "input": 15.0,
    "cache_write": 18.75,
    "cache_read": 1.50,
    "output": 75.0,
}


def _append_cost_entry(entry: dict) -> None:
    path = _costs_file()
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _wrap_call(endpoint: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # narrow re-raise with context
        raise RuntimeError(f"managed-agents {endpoint} failed: {exc}") from exc


def _event_timestamp(event) -> float:
    ts = getattr(event, "processed_at", None)
    if isinstance(ts, datetime):
        return ts.timestamp()
    if isinstance(ts, (int, float)):
        return float(ts)
    return time.time()


_TERMINAL_EVENT_TYPES: frozenset[str] = frozenset(
    {"session.status_idle", "session.status_terminated", "session.deleted"}
)


def _normalize_event(event) -> dict:
    """Translate an SDK event object into the UI-facing shape."""
    etype = getattr(event, "type", "unknown")
    ts = _event_timestamp(event)

    if etype == "agent.thinking":
        kind = "reasoning"
        payload = {"id": getattr(event, "id", None)}
    elif etype == "agent.message":
        kind = "assistant"
        payload = {
            "id": getattr(event, "id", None),
            "text": _extract_text(getattr(event, "content", None)),
        }
    elif etype in ("agent.tool_use", "agent.mcp_tool_use", "agent.custom_tool_use"):
        kind = "tool_call"
        payload = {
            "id": getattr(event, "id", None),
            "name": getattr(event, "name", None),
            "input": getattr(event, "input", None),
        }
    elif etype in ("agent.tool_result", "agent.mcp_tool_result"):
        kind = "tool_result"
        payload = {
            "id": getattr(event, "id", None),
            "tool_use_id": getattr(event, "tool_use_id", None),
            "is_error": getattr(event, "is_error", None),
            "text": _extract_text(getattr(event, "content", None)),
        }
    elif etype.startswith("session.status_") or etype == "session.error":
        kind = "status"
        state = etype.replace("session.status_", "").replace("session.", "")
        payload = {"state": state}
        stop = getattr(event, "stop_reason", None)
        if stop is not None:
            payload["stop_reason"] = getattr(stop, "type", str(stop))
    else:
        kind = "status"
        payload = {"state": etype}

    return {"type": kind, "ts": ts, "payload": payload}


def _extract_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    try:
        iterator: Iterable = content  # type: ignore[assignment]
    except TypeError:
        return str(content)
    for block in iterator:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if text:
            parts.append(text)
    return "\n".join(parts)


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _build_tool_configs(tool_names: Iterable[str]) -> list[dict]:
    configs: list[dict] = []
    seen: set[str] = set()
    for name in tool_names:
        sdk_name = _TOOL_ALIASES.get(name, name)
        if sdk_name in _SDK_TOOL_NAMES and sdk_name not in seen:
            configs.append({"name": sdk_name, "enabled": True})
            seen.add(sdk_name)
    return configs


def _build_cloud_config(network: str) -> dict:
    if network == "none":
        net: dict = {
            "type": "limited",
            "allow_mcp_servers": False,
            "allow_package_managers": False,
            "allowed_hosts": [],
        }
    else:  # "egress_only" (and any other value)
        net = {"type": "unrestricted"}
    return {"type": "cloud", "networking": net}


# ---------------------------------------------------------------------------
# Agent / Session
# ---------------------------------------------------------------------------
class ForensicAgent:
    """Thin wrapper around the Managed Agents control plane."""

    def __init__(
        self,
        config: ForensicAgentConfig | None = None,
        client: Anthropic | None = None,
        memory: MemoryStack | None = None,
        platform: str | None = None,
    ) -> None:
        self.config = config or ForensicAgentConfig()
        self._client: Anthropic = client or Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self._memory = memory
        self._platform = platform
        # Lazily build the advisor so agents constructed without memory stay
        # zero-overhead. Advisor is safe to build once per agent because it
        # only reads from the memory stack.
        from .policy import PolicyAdvisor

        self._advisor = PolicyAdvisor(memory, platform=platform) if memory is not None else None

    def open_session(self, bag_path: Path, case_key: str) -> "ForensicSession":
        beta = self._client.beta

        file_resources: list[dict] = []
        bag_path = Path(bag_path)
        to_upload: list[Path] = []
        if bag_path.exists() and bag_path.is_file():
            to_upload.append(bag_path)
        for extra in self.config.mounted_files:
            p = Path(extra)
            if p.exists() and p.is_file():
                to_upload.append(p)
        for path in to_upload:
            _CREATE_LIMITER.acquire()
            with open(path, "rb") as fh:
                metadata = _wrap_call(
                    "files.upload",
                    beta.files.upload,
                    file=(path.name, fh, "application/octet-stream"),
                )
            file_resources.append(
                {
                    "type": "file",
                    "file_id": metadata.id,
                    "mount_path": path.name,
                }
            )

        _CREATE_LIMITER.acquire()
        environment = _wrap_call(
            "environments.create",
            beta.environments.create,
            name=f"blackbox-env-{case_key}",
            config=_build_cloud_config(self.config.network),
            metadata={"case_key": case_key},
        )

        tool_configs = _build_tool_configs(self.config.tools)
        tools_param: list[dict] = []
        if tool_configs:
            tools_param.append(
                {"type": "agent_toolset_20260401", "configs": tool_configs}
            )
        skills_param = [
            {"type": "anthropic", "skill_id": sid} for sid in self.config.skills
        ]

        agent_kwargs: dict = {
            "model": self.config.model,
            "name": self.config.agent_name,
            "system": self.config.system_prompt,
            "tools": tools_param,
            "skills": skills_param,
            "metadata": {"case_key": case_key},
        }
        if self.config.mcp_servers:
            agent_kwargs["mcp_servers"] = self.config.mcp_servers

        _CREATE_LIMITER.acquire()
        agent = _wrap_call("agents.create", beta.agents.create, **agent_kwargs)

        session_kwargs: dict = {
            "agent": {"id": agent.id, "type": "agent"},
            "environment_id": environment.id,
            "metadata": {"case_key": case_key, "mode": "post_mortem"},
            "title": f"post-mortem {case_key}",
        }
        if file_resources:
            session_kwargs["resources"] = file_resources

        _CREATE_LIMITER.acquire()
        session = _wrap_call("sessions.create", beta.sessions.create, **session_kwargs)

        priors_block = ""
        if self._advisor is not None:
            try:
                priors_block = self._advisor.prime_prompt_block() or ""
            except Exception:
                priors_block = ""
        seed_text = (
            f"Case key: {case_key}\n"
            f"Mode: post_mortem\n"
            f"Budget: {self.config.task_budget_minutes} minutes.\n"
            "Uploaded artifacts are under /mnt/session/uploads/ — run `ls "
            "/mnt/session/uploads/` to discover the bag and any extras. "
            "Analyze the rosbag and return a single JSON object that "
            "validates against the PostMortemReport schema: keys timeline, "
            "hypotheses, root_cause_idx, patch_proposal."
        )
        if priors_block:
            seed_text = seed_text + "\n\n" + priors_block
        _CREATE_LIMITER.acquire()
        _wrap_call(
            "sessions.events.send",
            beta.sessions.events.send,
            session_id=session.id,
            events=[
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": seed_text}],
                }
            ],
        )

        return ForensicSession(
            session_id=session.id,
            case_key=case_key,
            _client=self._client,
            _agent_id=agent.id,
            _environment_id=environment.id,
            _started_at=time.monotonic(),
            _memory=self._memory,
            _advisor=self._advisor,
        )


@dataclass
class ForensicSession:
    """Represents one running managed-agents Session.

    The UI treats this as an event stream until ``finalize()`` is called.
    """

    session_id: str
    case_key: str
    _client: Anthropic | None = None
    _agent_id: str | None = None
    _environment_id: str | None = None
    _started_at: float = field(default_factory=time.monotonic)
    _final_text: str | None = field(default=None, repr=False)
    _memory: MemoryStack | None = field(default=None, repr=False)
    _advisor: Any = field(default=None, repr=False)

    # -- event stream --------------------------------------------------------
    def stream(self) -> Iterator[dict]:
        """Yield session Events as structured dicts."""
        if self._client is None:
            raise RuntimeError("ForensicSession has no client bound")

        beta = self._client.beta
        terminal_emitted = False

        try:
            _READ_LIMITER.acquire()
            stream_ctx = _wrap_call(
                "sessions.events.stream",
                beta.sessions.events.stream,
                session_id=self.session_id,
            )
        except RuntimeError:
            stream_ctx = None

        if stream_ctx is not None:
            for event in stream_ctx:
                payload = _normalize_event(event)
                if payload["type"] == "assistant":
                    self._final_text = payload["payload"].get("text") or self._final_text
                yield payload
                if getattr(event, "type", "") in _TERMINAL_EVENT_TYPES:
                    terminal_emitted = True
                    break

        if not terminal_emitted:
            yield from self._poll_events()
            terminal_emitted = True

        yield {
            "type": "status",
            "ts": time.time(),
            "payload": {"state": "completed"},
        }

    def _poll_events(self) -> Iterator[dict]:
        assert self._client is not None
        beta = self._client.beta
        seen_ids: set[str] = set()
        while True:
            _READ_LIMITER.acquire()
            page = _wrap_call(
                "sessions.events.list",
                beta.sessions.events.list,
                session_id=self.session_id,
                order="asc",
                limit=100,
            )
            items = getattr(page, "data", None) or list(page)
            terminal = False
            for event in items:
                eid = getattr(event, "id", None)
                if eid is not None:
                    if eid in seen_ids:
                        continue
                    seen_ids.add(eid)
                payload = _normalize_event(event)
                if payload["type"] == "assistant":
                    self._final_text = payload["payload"].get("text") or self._final_text
                yield payload
                if getattr(event, "type", "") in _TERMINAL_EVENT_TYPES:
                    terminal = True
            if terminal:
                return
            _READ_LIMITER.acquire()
            session = _wrap_call(
                "sessions.retrieve",
                beta.sessions.retrieve,
                self.session_id,
            )
            status = getattr(session, "status", None)
            if status in ("idle", "terminated"):
                return
            time.sleep(1.0)

    # -- steering ------------------------------------------------------------
    def steer(self, message: str) -> None:
        if self._client is None:
            raise RuntimeError("ForensicSession has no client bound")
        _CREATE_LIMITER.acquire()
        _wrap_call(
            "sessions.events.send",
            self._client.beta.sessions.events.send,
            session_id=self.session_id,
            events=[
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": message}],
                }
            ],
        )

    # -- finalize ------------------------------------------------------------
    def finalize(self) -> dict:
        if self._client is None:
            raise RuntimeError("ForensicSession has no client bound")
        beta = self._client.beta

        final_text = self._final_text
        _READ_LIMITER.acquire()
        session = _wrap_call(
            "sessions.retrieve",
            beta.sessions.retrieve,
            self.session_id,
        )

        if not final_text:
            _READ_LIMITER.acquire()
            page = _wrap_call(
                "sessions.events.list",
                beta.sessions.events.list,
                session_id=self.session_id,
                order="desc",
                limit=50,
            )
            items = getattr(page, "data", None) or list(page)
            for event in items:
                if getattr(event, "type", "") == "agent.message":
                    final_text = _extract_text(getattr(event, "content", None))
                    if final_text:
                        break

        wall_time = time.monotonic() - self._started_at
        self._log_usage(session, wall_time)

        if not final_text:
            raise RuntimeError(
                f"managed-agents session {self.session_id} produced no assistant message"
            )

        raw = _strip_json_fences(final_text)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"assistant output was not valid JSON: {exc}; text={raw[:200]!r}"
            ) from exc
        try:
            report = PostMortemReport.model_validate(data)
        except ValidationError as exc:
            raise RuntimeError(
                f"assistant JSON did not match PostMortemReport: {exc}"
            ) from exc
        payload = report.model_dump()
        payload = self._apply_advisor(payload)
        self._record_memory(payload)
        return payload

    def _apply_advisor(self, payload: dict) -> dict:
        """Fold L3 tie-break into hypotheses and L4 regression alarms into the payload.

        No-op when no advisor is bound. Runs before memory writes so the
        tie-broken ordering is what persists in L1 and drives L3 counts.
        """
        if self._advisor is None:
            return payload
        try:
            hyps = payload.get("hypotheses") or []
            if hyps:
                reordered = self._advisor.apply_tie_break(hyps)
                if reordered and reordered[0] is not hyps[0]:
                    # Tie-break changed the winner — rewrite root_cause_idx
                    # to point at the new top-ranked hypothesis.
                    payload["hypotheses"] = reordered
                    payload["root_cause_idx"] = 0
                    payload["advisor_tie_break_applied"] = True
                else:
                    payload["hypotheses"] = reordered
            alarms = self._advisor.regression_alarms()
            if alarms:
                payload["regression_alarms"] = [
                    {
                        "bug_class": a.bug_class,
                        "accuracy": a.accuracy,
                        "n_samples": a.n_samples,
                        "threshold": a.threshold,
                    }
                    for a in alarms
                ]
        except Exception:
            # Advisor must never take down finalize. Silent by design.
            pass
        return payload

    def _record_memory(self, report: dict) -> None:
        """Bump L3 taxonomy + append L1 case record for a finalized report.

        No-op if no MemoryStack was bound to the session. Failures are
        swallowed so memory bookkeeping can never take down a finalize.
        """
        if self._memory is None:
            return
        try:
            self._memory.case.log(
                CaseRecord(
                    case_key=self.case_key,
                    kind="hypothesis",
                    payload={
                        "root_cause_idx": report.get("root_cause_idx"),
                        "hypotheses": report.get("hypotheses", []),
                        "patch_proposal": report.get("patch_proposal", ""),
                    },
                )
            )
            for h in report.get("hypotheses", []) or []:
                bug_class = h.get("bug_class", "other")
                signature = (h.get("summary") or bug_class)[:64]
                self._memory.taxonomy.log(
                    TaxonomyCount(bug_class=bug_class, signature=signature)
                )
        except Exception:  # never let memory break the pipeline
            pass

    def _log_usage(self, session, wall_time: float) -> None:
        usage = getattr(session, "usage", None)
        cached_input = getattr(usage, "cache_read_input_tokens", 0) or 0
        uncached_input = getattr(usage, "input_tokens", 0) or 0
        cache_creation_obj = getattr(usage, "cache_creation", None)
        cache_creation = 0
        if cache_creation_obj is not None:
            cache_creation = (
                getattr(cache_creation_obj, "ephemeral_5m_input_tokens", 0) or 0
            ) + (
                getattr(cache_creation_obj, "ephemeral_1h_input_tokens", 0) or 0
            )
            if not cache_creation:
                cache_creation = getattr(cache_creation_obj, "input_tokens", 0) or 0
        output = getattr(usage, "output_tokens", 0) or 0

        input_cost = (
            uncached_input * _PRICING["input"]
            + cache_creation * _PRICING["cache_write"]
            + cached_input * _PRICING["cache_read"]
        ) / 1e6
        output_cost = output * _PRICING["output"] / 1e6
        total_cost = input_cost + output_cost

        entry = {
            "cached_input_tokens": int(cached_input),
            "uncached_input_tokens": int(uncached_input),
            "cache_creation_tokens": int(cache_creation),
            "output_tokens": int(output),
            "usd_cost": float(total_cost),
            "wall_time_s": float(wall_time),
            "model": MODEL,
            "prompt_kind": "managed_agent_postmortem",
            "session_id": self.session_id,
            "case_key": self.case_key,
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
        _append_cost_entry(entry)


__all__ = [
    "ANTHROPIC_BETA_HEADER",
    "MODEL",
    "BUILTIN_TOOLS",
    "ForensicAgentConfig",
    "ForensicAgent",
    "ForensicSession",
]
