"""Unit tests for the Managed Agents wiring.

Mocks the anthropic SDK so nothing hits the real API.
"""
from __future__ import annotations

import json
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from black_box.analysis import managed_agent as ma
from black_box.analysis.managed_agent import (
    ForensicAgent,
    ForensicAgentConfig,
    ForensicSession,
    _RateLimiter,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeFiles:
    def __init__(self):
        self.uploaded: list[str] = []

    def upload(self, *, file, **_):
        name = "blob"
        if isinstance(file, tuple):
            name = file[0]
        self.uploaded.append(name)
        return SimpleNamespace(id=f"file_{len(self.uploaded):03d}", filename=name)


class _FakeEnvironments:
    def __init__(self):
        self.created: list[dict] = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return SimpleNamespace(id="env_abc", name=kwargs.get("name"))


class _FakeAgents:
    def __init__(self):
        self.created: list[dict] = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return SimpleNamespace(id="agent_xyz", version=1, **{k: v for k, v in kwargs.items() if k != "betas"})


class _FakeEvents:
    def __init__(self, scripted_events=None):
        self.sent: list[dict] = []
        self._scripted = scripted_events or []
        self._listed: list[dict] = []

    def send(self, *, session_id, events, **_):
        self.sent.append({"session_id": session_id, "events": list(events)})
        return SimpleNamespace(ok=True)

    def stream(self, *, session_id, **_):
        return iter(self._scripted)

    def list(self, *, session_id, order="asc", limit=100, **_):
        data = self._listed if order == "asc" else list(reversed(self._listed))
        return SimpleNamespace(data=data)


class _FakeSessions:
    def __init__(self, events):
        self.events = events
        self.created: list[dict] = []
        self._session_state = SimpleNamespace(
            id="session_123",
            status="idle",
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=200,
                cache_read_input_tokens=50,
                cache_creation=SimpleNamespace(
                    ephemeral_5m_input_tokens=30,
                    ephemeral_1h_input_tokens=0,
                ),
            ),
        )

    def create(self, **kwargs):
        self.created.append(kwargs)
        return SimpleNamespace(id="session_123")

    def retrieve(self, session_id, **_):
        return self._session_state


class _FakeBeta:
    def __init__(self, events):
        self.files = _FakeFiles()
        self.environments = _FakeEnvironments()
        self.agents = _FakeAgents()
        self.sessions = _FakeSessions(events)
        # attach events under sessions
        self.sessions.events = events


class _FakeClient:
    def __init__(self, events):
        self.beta = _FakeBeta(events)


def _make_event(etype: str, **fields):
    ns = SimpleNamespace(type=etype, processed_at=fields.pop("processed_at", 1000.0), **fields)
    return ns


def _make_text_block(text: str):
    return SimpleNamespace(type="text", text=text)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_open_session_creates_env_agent_and_session(tmp_path: Path):
    bag = tmp_path / "crash.bag"
    bag.write_bytes(b"\x00fake\x00bag")

    events = _FakeEvents()
    client = _FakeClient(events)

    config = ForensicAgentConfig(task_budget_minutes=7, skills=["ros-bag-decoder"])
    agent = ForensicAgent(config=config, client=client)

    session = agent.open_session(bag_path=bag, case_key="crash_001")

    assert isinstance(session, ForensicSession)
    assert session.session_id == "session_123"
    assert session.case_key == "crash_001"
    # env created once with cloud config
    assert len(client.beta.environments.created) == 1
    env_kwargs = client.beta.environments.created[0]
    assert env_kwargs["config"]["type"] == "cloud"
    # agent created once with real SDK tool names only
    assert len(client.beta.agents.created) == 1
    agent_kwargs = client.beta.agents.created[0]
    toolset = agent_kwargs["tools"][0]
    assert toolset["type"] == "agent_toolset_20260401"
    names = {c["name"] for c in toolset["configs"]}
    assert names <= {"bash", "read", "write", "edit", "glob", "grep", "web_fetch", "web_search"}
    assert "mcp" not in names  # filtered out, SDK uses separate toolset type
    assert agent_kwargs["skills"] == [{"type": "anthropic", "skill_id": "ros-bag-decoder"}]
    # session created referencing env + agent + uploaded file
    session_kwargs = client.beta.sessions.created[0]
    assert session_kwargs["agent"] == {"id": "agent_xyz", "type": "agent"}
    assert session_kwargs["environment_id"] == "env_abc"
    assert session_kwargs["resources"][0]["type"] == "file"
    assert session_kwargs["resources"][0]["file_id"].startswith("file_")
    # seed user event sent
    assert len(events.sent) == 1
    seed = events.sent[0]["events"][0]
    assert seed["type"] == "user.message"
    assert "crash_001" in seed["content"][0]["text"]


def test_stream_yields_normalized_dicts():
    scripted = [
        _make_event("agent.thinking", id="t1"),
        _make_event(
            "agent.tool_use",
            id="u1",
            name="bash",
            input={"cmd": "ls /mnt/bag"},
        ),
        _make_event(
            "agent.tool_result",
            id="r1",
            tool_use_id="u1",
            content=[_make_text_block("ok")],
            is_error=False,
        ),
        _make_event(
            "agent.message",
            id="m1",
            content=[_make_text_block('{"ok": true}')],
        ),
        _make_event(
            "session.status_idle",
            id="s1",
            stop_reason=SimpleNamespace(type="end_turn"),
        ),
    ]
    events = _FakeEvents(scripted_events=scripted)
    client = _FakeClient(events)
    session = ForensicSession(
        session_id="session_123",
        case_key="crash_001",
        _client=client,
    )

    emitted = list(session.stream())
    kinds = [e["type"] for e in emitted]
    assert kinds[:4] == ["reasoning", "tool_call", "tool_result", "assistant"]
    # status events after terminal
    assert emitted[4]["type"] == "status"
    assert emitted[4]["payload"]["state"] == "idle"
    assert emitted[-1]["payload"] == {"state": "completed"}
    # tool_call payload preserved
    assert emitted[1]["payload"]["name"] == "bash"
    assert emitted[1]["payload"]["input"] == {"cmd": "ls /mnt/bag"}
    # assistant text captured for finalize
    assert session._final_text == '{"ok": true}'


def test_steer_posts_user_event():
    events = _FakeEvents()
    client = _FakeClient(events)
    session = ForensicSession(
        session_id="session_123", case_key="c", _client=client
    )

    session.steer("focus on 12-15s")

    assert len(events.sent) == 1
    ev = events.sent[0]
    assert ev["session_id"] == "session_123"
    assert ev["events"][0]["type"] == "user.message"
    assert ev["events"][0]["content"][0]["text"] == "focus on 12-15s"


def test_finalize_parses_last_assistant_and_logs_cost(tmp_path: Path, monkeypatch):
    report_json = {
        "timeline": [{"t_ns": 1, "label": "boot", "cross_view": False}],
        "hypotheses": [
            {
                "bug_class": "pid_saturation",
                "confidence": 0.9,
                "summary": "PID wound up",
                "evidence": [
                    {
                        "source": "telemetry",
                        "topic_or_file": "/cmd_vel",
                        "t_ns": 12000,
                        "snippet": "max u for 3s",
                    }
                ],
                "patch_hint": "clamp output to +/-1.0",
            }
        ],
        "root_cause_idx": 0,
        "patch_proposal": "clamp in control_loop.py",
    }
    events = _FakeEvents()
    events._listed = [
        _make_event(
            "agent.message",
            id="m1",
            content=[_make_text_block(f"```json\n{json.dumps(report_json)}\n```")],
        )
    ]
    client = _FakeClient(events)
    session = ForensicSession(
        session_id="session_123", case_key="crash_001", _client=client
    )

    # redirect cost log to tmp path
    fake_cost = tmp_path / "costs.jsonl"
    monkeypatch.setattr(ma, "_costs_file", lambda: fake_cost)

    result = session.finalize()

    assert result["root_cause_idx"] == 0
    assert result["hypotheses"][0]["bug_class"] == "pid_saturation"
    # cost line written
    lines = fake_cost.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["prompt_kind"] == "managed_agent_postmortem"
    assert entry["session_id"] == "session_123"
    assert entry["model"] == "claude-opus-4-7"
    assert entry["output_tokens"] == 200
    assert entry["cached_input_tokens"] == 50
    assert entry["cache_creation_tokens"] == 30
    assert entry["usd_cost"] > 0


def test_finalize_bumps_memory_stack_when_bound(tmp_path: Path, monkeypatch):
    """After a successful finalize(), L1 case + L3 taxonomy should both be written."""
    from black_box.memory import MemoryStack

    report_json = {
        "timeline": [{"t_ns": 1, "label": "boot", "cross_view": False}],
        "hypotheses": [
            {
                "bug_class": "pid_saturation",
                "confidence": 0.9,
                "summary": "Integral wind-up on hip pitch during step initiation",
                "evidence": [
                    {
                        "source": "telemetry",
                        "topic_or_file": "/cmd_vel",
                        "t_ns": 12000,
                        "snippet": "max u for 3s",
                    }
                ],
                "patch_hint": "clamp output to +/-1.0",
            },
            {
                "bug_class": "bad_gain_tuning",
                "confidence": 0.4,
                "summary": "Kp too high on LHipPitch",
                "evidence": [],
                "patch_hint": "reduce Kp 30%",
            },
        ],
        "root_cause_idx": 0,
        "patch_proposal": "clamp in control_loop.py",
    }
    events = _FakeEvents()
    events._listed = [
        _make_event(
            "agent.message",
            id="m1",
            content=[_make_text_block(f"```json\n{json.dumps(report_json)}\n```")],
        )
    ]
    client = _FakeClient(events)
    mem = MemoryStack.open(tmp_path / "mem")
    session = ForensicSession(
        session_id="session_123",
        case_key="c1_faceplant",
        _client=client,
        _memory=mem,
    )
    monkeypatch.setattr(ma, "_costs_file", lambda: tmp_path / "costs.jsonl")

    session.finalize()

    # L1: one CaseRecord written for this case
    case_rows = mem.case.for_case("c1_faceplant")
    assert len(case_rows) == 1
    assert case_rows[0].kind == "hypothesis"
    assert case_rows[0].payload["root_cause_idx"] == 0

    # L3: one count per hypothesis
    by_class = mem.taxonomy.totals_by_class()
    assert by_class == {"pid_saturation": 1, "bad_gain_tuning": 1}


def test_finalize_without_memory_is_a_noop():
    """No MemoryStack attached -> finalize succeeds and writes nothing."""
    report_json = {
        "timeline": [],
        "hypotheses": [
            {"bug_class": "other", "confidence": 0.1, "summary": "n/a",
             "evidence": [], "patch_hint": ""}
        ],
        "root_cause_idx": 0,
        "patch_proposal": "",
    }
    events = _FakeEvents()
    events._listed = [
        _make_event(
            "agent.message",
            id="m1",
            content=[_make_text_block(json.dumps(report_json))],
        )
    ]
    client = _FakeClient(events)
    session = ForensicSession(
        session_id="s", case_key="c", _client=client, _memory=None
    )
    # Should not raise.
    session._record_memory(report_json)


def test_finalize_applies_advisor_tie_break_and_regression_alarms(
    tmp_path: Path, monkeypatch
):
    """Finalize should fold the PolicyAdvisor's tie-break + alarms into the payload.

    Given an L3 taxonomy that overwhelmingly favors pid_saturation and an L4
    eval history where sensor_timeout is regressing, a near-tied top-2 must
    be reordered so pid_saturation wins, root_cause_idx must be rewritten to
    0, and regression_alarms must surface sensor_timeout.
    """
    from black_box.analysis.policy import PolicyAdvisor
    from black_box.memory import EvalRecord, MemoryStack, TaxonomyCount

    mem = MemoryStack.open(tmp_path / "mem")
    # L3: pid_saturation is much more common than bad_gain_tuning.
    mem.taxonomy.log(TaxonomyCount(bug_class="pid_saturation", signature="s", count=50))
    mem.taxonomy.log(TaxonomyCount(bug_class="bad_gain_tuning", signature="t", count=2))
    # L4: sensor_timeout regressing — 1/4 correct, below 0.6.
    mem.eval.log(EvalRecord(case_key="c1", predicted_bug="sensor_timeout",
                            ground_truth_bug="sensor_timeout", match=True))
    for i in range(3):
        mem.eval.log(EvalRecord(case_key=f"c{i+2}", predicted_bug="other",
                                ground_truth_bug="sensor_timeout", match=False))

    # Top-2 near-tied: bad_gain_tuning (0.55) vs pid_saturation (0.52). Advisor
    # should promote pid_saturation because its L3 count dwarfs bad_gain_tuning.
    report_json = {
        "timeline": [{"t_ns": 1, "label": "boot", "cross_view": False}],
        "hypotheses": [
            {
                "bug_class": "bad_gain_tuning",
                "confidence": 0.55,
                "summary": "Kp too high on LHipPitch",
                "evidence": [],
                "patch_hint": "reduce Kp 30%",
            },
            {
                "bug_class": "pid_saturation",
                "confidence": 0.52,
                "summary": "Integral wind-up during step initiation",
                "evidence": [
                    {
                        "source": "telemetry",
                        "topic_or_file": "/cmd_vel",
                        "t_ns": 12000,
                        "snippet": "max u for 3s",
                    }
                ],
                "patch_hint": "clamp output to +/-1.0",
            },
        ],
        "root_cause_idx": 0,
        "patch_proposal": "clamp in control_loop.py",
    }
    events = _FakeEvents()
    events._listed = [
        _make_event(
            "agent.message",
            id="m1",
            content=[_make_text_block(f"```json\n{json.dumps(report_json)}\n```")],
        )
    ]
    client = _FakeClient(events)
    session = ForensicSession(
        session_id="session_123",
        case_key="c1_faceplant",
        _client=client,
        _memory=mem,
        _advisor=PolicyAdvisor(
            mem,
            platform="nao6",
            tie_delta=0.1,
            regression_threshold=0.6,
            regression_min_samples=3,
        ),
    )
    monkeypatch.setattr(ma, "_costs_file", lambda: tmp_path / "costs.jsonl")

    payload = session.finalize()

    # Tie-break flipped the winner.
    assert payload["advisor_tie_break_applied"] is True
    assert payload["root_cause_idx"] == 0
    assert payload["hypotheses"][0]["bug_class"] == "pid_saturation"
    assert payload["hypotheses"][1]["bug_class"] == "bad_gain_tuning"

    # L4 regression alarm surfaced in the finalize payload.
    alarms = payload.get("regression_alarms") or []
    bug_classes = {a["bug_class"] for a in alarms}
    assert "sensor_timeout" in bug_classes
    st = next(a for a in alarms if a["bug_class"] == "sensor_timeout")
    assert st["n_samples"] == 4
    assert st["accuracy"] == pytest.approx(0.25)
    assert st["threshold"] == 0.6

    # L1 persisted the tie-broken ordering (root cause was rewritten before write).
    case_rows = mem.case.for_case("c1_faceplant")
    assert len(case_rows) == 1
    assert case_rows[0].payload["hypotheses"][0]["bug_class"] == "pid_saturation"


def test_finalize_without_advisor_leaves_payload_alone(tmp_path: Path, monkeypatch):
    """No advisor bound -> payload matches the parsed report verbatim."""
    report_json = {
        "timeline": [],
        "hypotheses": [
            {
                "bug_class": "bad_gain_tuning",
                "confidence": 0.55,
                "summary": "x",
                "evidence": [],
                "patch_hint": "",
            },
            {
                "bug_class": "pid_saturation",
                "confidence": 0.52,
                "summary": "y",
                "evidence": [],
                "patch_hint": "",
            },
        ],
        "root_cause_idx": 0,
        "patch_proposal": "",
    }
    events = _FakeEvents()
    events._listed = [
        _make_event(
            "agent.message",
            id="m1",
            content=[_make_text_block(json.dumps(report_json))],
        )
    ]
    client = _FakeClient(events)
    session = ForensicSession(
        session_id="s", case_key="c", _client=client, _advisor=None
    )
    monkeypatch.setattr(ma, "_costs_file", lambda: tmp_path / "costs.jsonl")

    payload = session.finalize()

    assert payload["hypotheses"][0]["bug_class"] == "bad_gain_tuning"  # untouched
    assert "advisor_tie_break_applied" not in payload
    assert "regression_alarms" not in payload


def test_rate_limiter_sleeps_after_burst():
    limiter = _RateLimiter(max_per_window=60, window_seconds=60.0)
    # Pre-fill 60 slots in the limiter's deque at monotonic() time.
    now = time.monotonic()
    limiter._events.extend([now] * 60)

    with mock.patch("black_box.analysis.managed_agent.time.sleep") as sleep_mock:
        limiter.acquire()
        assert sleep_mock.called
        # The sleep duration should be positive and <= window
        slept_for = sleep_mock.call_args[0][0]
        assert slept_for > 0
        assert slept_for <= 60.0
