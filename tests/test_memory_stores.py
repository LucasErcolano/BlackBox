"""Tests for native Anthropic Managed Agents memory_stores wiring.

Covers:
  * idempotent platform-store provisioning (lookup before create)
  * fresh per-case store on every session (case isolation)
  * session resources include both read_only + read_write entries
  * `enable_native_memory=False` short-circuits the API
  * safety gate refuses unverified promotion to platform store
  * a freshly-extracted "operator says X" hypothesis cannot auto-promote

All Anthropic SDK calls are stubbed; nothing hits the network.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from black_box.analysis import managed_agent as ma
from black_box.analysis.managed_agent import (
    ForensicAgent,
    ForensicAgentConfig,
    MemoryStoreSpec,
)
from black_box.memory import (
    UnverifiedMemoryPromotionError,
    promote_verified_priors_to_managed_memory,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeMemoriesAPI:
    def __init__(self) -> None:
        self.created: list[dict] = []

    def create(self, *, memory_store_id, path, content, **_):
        rec = {"memory_store_id": memory_store_id, "path": path, "content": content}
        self.created.append(rec)
        return SimpleNamespace(
            id=f"mem_{len(self.created):04d}",
            memory_store_id=memory_store_id,
            path=path,
        )


class _FakeMemoryStoresAPI:
    def __init__(self, preexisting: list[SimpleNamespace] | None = None) -> None:
        self._stores: list[SimpleNamespace] = list(preexisting or [])
        self.created: list[dict] = []
        self.list_calls = 0
        self.memories = _FakeMemoriesAPI()

    def list(self):
        self.list_calls += 1
        return SimpleNamespace(data=list(self._stores))

    def create(self, *, name, description=None, metadata=None, **_):
        store = SimpleNamespace(
            id=f"memstore_{len(self._stores) + 1:04d}",
            name=name,
            description=description,
            metadata=metadata or {},
            mount_path=f"/mnt/memory/{name}",
        )
        self._stores.append(store)
        self.created.append(
            {"name": name, "description": description, "metadata": metadata}
        )
        return store


class _FakeFiles:
    def upload(self, *, file, **_):
        name = file[0] if isinstance(file, tuple) else "blob"
        return SimpleNamespace(id=f"file_{name}", filename=name)


class _FakeEnvironments:
    def create(self, **kwargs):
        return SimpleNamespace(id="env_abc", name=kwargs.get("name"))


class _FakeAgents:
    def create(self, **kwargs):
        return SimpleNamespace(id="agent_xyz", **{k: v for k, v in kwargs.items() if k != "betas"})


class _FakeEvents:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, *, session_id, events, **_):
        self.sent.append({"session_id": session_id, "events": list(events)})
        return SimpleNamespace(ok=True)

    def stream(self, *, session_id, **_):
        return iter([])

    def list(self, *, session_id, order="asc", limit=100, **_):
        return SimpleNamespace(data=[])


class _FakeSessions:
    def __init__(self, events) -> None:
        self.events = events
        self.created: list[dict] = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return SimpleNamespace(id="session_123")

    def retrieve(self, session_id, **_):
        return SimpleNamespace(id=session_id, status="idle", usage=None)


class _FakeBeta:
    def __init__(self, *, memory_stores: _FakeMemoryStoresAPI | None) -> None:
        self.files = _FakeFiles()
        self.environments = _FakeEnvironments()
        self.agents = _FakeAgents()
        events = _FakeEvents()
        self.sessions = _FakeSessions(events)
        self.sessions.events = events
        if memory_stores is not None:
            self.memory_stores = memory_stores


class _FakeClient:
    def __init__(self, *, memory_stores: _FakeMemoryStoresAPI | None) -> None:
        self.beta = _FakeBeta(memory_stores=memory_stores)


# ---------------------------------------------------------------------------
# Provisioning tests
# ---------------------------------------------------------------------------
def test_platform_store_is_reused_when_it_already_exists(tmp_path: Path):
    existing = SimpleNamespace(
        id="memstore_existing",
        name="bb-platform-priors",
        mount_path="/mnt/memory/bb-platform-priors",
    )
    stores = _FakeMemoryStoresAPI(preexisting=[existing])
    client = _FakeClient(memory_stores=stores)
    bag = tmp_path / "crash.bag"
    bag.write_bytes(b"x")

    agent = ForensicAgent(
        config=ForensicAgentConfig(task_budget_minutes=1),
        client=client,
    )
    agent.open_session(bag_path=bag, case_key="crash_001")

    # Platform store reused — only the per-case store should have been created.
    case_creates = [c for c in stores.created if c["name"] != "bb-platform-priors"]
    platform_creates = [c for c in stores.created if c["name"] == "bb-platform-priors"]
    assert platform_creates == []  # idempotent
    assert len(case_creates) == 1  # fresh per-case store
    assert case_creates[0]["name"].startswith("bb-forensic-learnings-crash_001")
    # No seed memories were written to a reused platform store.
    assert stores.memories.created == []


def test_platform_store_is_created_and_seeded_when_absent(tmp_path: Path):
    stores = _FakeMemoryStoresAPI(preexisting=[])
    client = _FakeClient(memory_stores=stores)
    bag = tmp_path / "crash.bag"
    bag.write_bytes(b"x")

    agent = ForensicAgent(
        config=ForensicAgentConfig(task_budget_minutes=1),
        client=client,
    )
    agent.open_session(bag_path=bag, case_key="crash_002")

    names_created = [c["name"] for c in stores.created]
    assert "bb-platform-priors" in names_created
    # Seed memories were written on first creation.
    seed_paths = [m["path"] for m in stores.memories.created]
    assert any("anti_hypotheses/rtk_heading_break" in p for p in seed_paths)
    assert any("bug_taxonomy" in p for p in seed_paths)


def test_per_case_store_is_fresh_each_session(tmp_path: Path):
    """Two sessions with the same case_key still create distinct case stores.

    Case isolation is the safety contract: a case store is a read-write
    scratchpad, so reuse across sessions would leak state across runs.
    """
    stores = _FakeMemoryStoresAPI(preexisting=[])
    client = _FakeClient(memory_stores=stores)
    bag = tmp_path / "crash.bag"
    bag.write_bytes(b"x")

    cfg = ForensicAgentConfig(task_budget_minutes=1)
    ForensicAgent(config=cfg, client=client).open_session(bag_path=bag, case_key="case_a")
    ForensicAgent(config=cfg, client=client).open_session(bag_path=bag, case_key="case_a")

    case_creates = [c for c in stores.created if "forensic-learnings" in c["name"]]
    # Two separate creations even though the case_key is identical.
    assert len(case_creates) == 2


def test_session_resources_include_read_only_and_read_write(tmp_path: Path):
    stores = _FakeMemoryStoresAPI(preexisting=[])
    client = _FakeClient(memory_stores=stores)
    bag = tmp_path / "crash.bag"
    bag.write_bytes(b"x")

    agent = ForensicAgent(
        config=ForensicAgentConfig(task_budget_minutes=1),
        client=client,
    )
    agent.open_session(bag_path=bag, case_key="crash_003")

    session_kwargs = client.beta.sessions.created[0]
    resources = session_kwargs["resources"]
    types_seen = {r["type"] for r in resources}
    assert "memory_store" in types_seen
    accesses = {r["access"] for r in resources if r["type"] == "memory_store"}
    assert accesses == {"read_only", "read_write"}
    # Both have non-empty instructions and they fit the 4096-char ceiling.
    for r in resources:
        if r["type"] == "memory_store":
            assert r["instructions"]
            assert len(r["instructions"]) <= 4096


def test_seed_text_mentions_mount_path_and_human_gate(tmp_path: Path):
    stores = _FakeMemoryStoresAPI(preexisting=[])
    client = _FakeClient(memory_stores=stores)
    bag = tmp_path / "crash.bag"
    bag.write_bytes(b"x")

    agent = ForensicAgent(
        config=ForensicAgentConfig(task_budget_minutes=1),
        client=client,
    )
    agent.open_session(bag_path=bag, case_key="crash_004")

    seed_text = client.beta.sessions.events.sent[0]["events"][0]["content"][0]["text"]
    assert "/mnt/memory/" in seed_text
    assert "READ-ONLY" in seed_text
    assert "READ-WRITE" in seed_text
    assert "human-verification" in seed_text


def test_enable_native_memory_false_skips_api_calls(tmp_path: Path):
    stores = _FakeMemoryStoresAPI(preexisting=[])
    client = _FakeClient(memory_stores=stores)
    bag = tmp_path / "crash.bag"
    bag.write_bytes(b"x")

    agent = ForensicAgent(
        config=ForensicAgentConfig(task_budget_minutes=1, enable_native_memory=False),
        client=client,
    )
    agent.open_session(bag_path=bag, case_key="crash_off")

    assert stores.created == []
    assert stores.list_calls == 0
    # Session should still have file resources but no memory_store entries.
    session_kwargs = client.beta.sessions.created[0]
    resources = session_kwargs.get("resources", [])
    assert all(r["type"] != "memory_store" for r in resources)


def test_provisioning_failure_falls_back_gracefully(tmp_path: Path):
    """If memory_stores.list raises, the session still launches.

    The senior reviewer's call: native memory is a strict bonus; an outage
    should not take the whole forensic session down.
    """
    class _BoomStores(_FakeMemoryStoresAPI):
        def list(self):
            raise RuntimeError("simulated outage")

    stores = _BoomStores(preexisting=[])
    client = _FakeClient(memory_stores=stores)
    bag = tmp_path / "crash.bag"
    bag.write_bytes(b"x")

    agent = ForensicAgent(
        config=ForensicAgentConfig(task_budget_minutes=1),
        client=client,
    )
    # Should not raise; session is still created without memory_store resources.
    agent.open_session(bag_path=bag, case_key="crash_boom")
    session_kwargs = client.beta.sessions.created[0]
    resources = session_kwargs.get("resources", [])
    # Platform path raised; per-case path will still attempt and may succeed,
    # but we explicitly assert at least no platform read_only resource leaked.
    accesses = {r["access"] for r in resources if r.get("type") == "memory_store"}
    assert "read_only" not in accesses


# ---------------------------------------------------------------------------
# Safety gate tests
# ---------------------------------------------------------------------------
def test_safety_gate_rejects_unverified_promotion(tmp_path: Path):
    stores = _FakeMemoryStoresAPI(preexisting=[])
    client = _FakeClient(memory_stores=stores)

    operator_says = {
        "path": "/priors/operator_narrative_2026.md",
        "content": "Operator says: GPS fails inside the tunnel.",
        # No `verified=True` and no analysis_id with a confirmation note.
    }

    with pytest.raises(UnverifiedMemoryPromotionError):
        promote_verified_priors_to_managed_memory(
            client=client,
            store_id="memstore_platform",
            verified_priors=[operator_says],
        )

    # Nothing was written even partially.
    assert stores.memories.created == []


def test_safety_gate_accepts_explicit_verified_flag(tmp_path: Path):
    stores = _FakeMemoryStoresAPI(preexisting=[])
    client = _FakeClient(memory_stores=stores)

    prior = {
        "path": "/priors/sanfer_rtk.md",
        "content": "RTK heading break — sensor_timeout, refutes operator narrative.",
        "verified": True,
    }
    written = promote_verified_priors_to_managed_memory(
        client=client,
        store_id="memstore_platform",
        verified_priors=[prior],
    )
    assert len(written) == 1
    assert stores.memories.created[0]["path"] == "/priors/sanfer_rtk.md"


def test_safety_gate_accepts_confirmation_note_in_ledger(tmp_path: Path, monkeypatch):
    """A prior referencing an analysis_id with a `severity='confirmation'`
    note in the verification ledger passes the gate without `verified=True`.
    """
    from black_box.memory import VerificationNote, add_note

    fake_ledger = tmp_path / "verification.jsonl"

    monkeypatch.setattr(
        "black_box.memory.verification._global_ledger_path",
        lambda: fake_ledger,
    )

    note = VerificationNote(
        analysis_id="case_sanfer_42",
        operator_id="aayush@morgan.edu",
        written_at="2026-04-23T12:00:00+00:00",
        agent_conclusion="bug_class=sensor_timeout",
        real_cause="confirmed: rover never ingested MB observation stream",
        disputed_class=None,
        severity="confirmation",
    )
    add_note(tmp_path / "case_sanfer_42", note)

    stores = _FakeMemoryStoresAPI(preexisting=[])
    client = _FakeClient(memory_stores=stores)

    prior = {
        "path": "/priors/case_sanfer_42.md",
        "content": "Verified: sensor_timeout root cause confirmed by operator.",
        "analysis_id": "case_sanfer_42",
    }
    written = promote_verified_priors_to_managed_memory(
        client=client,
        store_id="memstore_platform",
        verified_priors=[prior],
    )
    assert len(written) == 1


def test_freshly_extracted_operator_hypothesis_cannot_auto_promote(tmp_path: Path):
    """Negative test: the most dangerous failure mode.

    The agent extracted an operator narrative ("GPS fails in tunnel") from a
    new bag and tried to write it into the platform store as if it were a
    verified prior. This MUST be rejected by the safety gate, not just
    discouraged in prose.
    """
    stores = _FakeMemoryStoresAPI(preexisting=[])
    client = _FakeClient(memory_stores=stores)

    fresh_extraction = {
        "path": "/priors/auto_extracted_2026_04_23.md",
        "content": (
            "Operator narrative auto-extracted from sanfer_drive bag: "
            "'GPS fails when entering the tunnel'. Bug class: sensor_timeout."
        ),
        "analysis_id": "case_unverified_999",
        # No verified=True. No confirmation note in the ledger.
    }

    with pytest.raises(UnverifiedMemoryPromotionError):
        promote_verified_priors_to_managed_memory(
            client=client,
            store_id="memstore_platform",
            verified_priors=[fresh_extraction],
        )
    assert stores.memories.created == []


def test_safety_gate_rejects_whole_batch_atomically(tmp_path: Path):
    """One unverified entry sinks the whole batch; the platform store is
    never partially mutated.
    """
    stores = _FakeMemoryStoresAPI(preexisting=[])
    client = _FakeClient(memory_stores=stores)

    batch = [
        {"path": "/priors/ok.md", "content": "ok", "verified": True},
        {"path": "/priors/bad.md", "content": "bad"},  # no verified flag
    ]
    with pytest.raises(UnverifiedMemoryPromotionError):
        promote_verified_priors_to_managed_memory(
            client=client,
            store_id="memstore_platform",
            verified_priors=batch,
        )
    assert stores.memories.created == []


# ---------------------------------------------------------------------------
# Spec dataclass smoke
# ---------------------------------------------------------------------------
def test_memory_store_spec_round_trip():
    spec = MemoryStoreSpec(
        name="bb-test",
        access="read_only",
        instructions="x" * 100,
        seed_memories=[("/p.md", "c")],
    )
    assert spec.access == "read_only"
    assert spec.seed_memories == [("/p.md", "c")]
