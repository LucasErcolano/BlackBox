"""Tests for `blackbox-memory` CLI + lifecycle scripts.

Mocks the SDK surface — the installed anthropic 0.96.0 does not expose
`memory_stores`, so we monkeypatch a `_FakeClient` everywhere.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from black_box.memory import cli as memcli


# ---------------------------------------------------------------------------
# Fakes (mirror the patterns used in test_memory_stores.py)
# ---------------------------------------------------------------------------
class _FakeMemoriesAPI:
    def __init__(self, items: dict[str, list[Any]] | None = None) -> None:
        self.items: dict[str, list[Any]] = items or {}
        self.created: list[dict] = []

    def list(self, *, memory_store_id, path=None, history=False):
        if path is not None:
            v = []
            for mem in self.items.get(memory_store_id, []):
                if getattr(mem, "path", None) == path:
                    v.extend(getattr(mem, "_versions", []))
            return SimpleNamespace(data=v)
        return SimpleNamespace(data=list(self.items.get(memory_store_id, [])))

    def create(self, *, memory_store_id, path, content, **_):
        self.created.append({"memory_store_id": memory_store_id, "path": path, "content": content})
        rec = SimpleNamespace(
            id=f"mem_{len(self.created):04d}",
            memory_store_id=memory_store_id,
            path=path,
            content=content,
            _versions=[SimpleNamespace(id=f"ver_{len(self.created):04d}", content=content)],
        )
        self.items.setdefault(memory_store_id, []).append(rec)
        return rec

    def redact(self, *, version_id, reason):
        return SimpleNamespace(id=version_id, redacted=True, reason=reason)


class _FakeMemoryStoresAPI:
    def __init__(self, preexisting: list[Any] | None = None, mems: dict[str, list[Any]] | None = None) -> None:
        self._stores: list[Any] = list(preexisting or [])
        self.created: list[dict] = []
        self.deleted: list[str] = []
        self.memories = _FakeMemoriesAPI(mems)

    def list(self):
        return SimpleNamespace(data=list(self._stores))

    def create(self, *, name, description=None, metadata=None, **_):
        store = SimpleNamespace(
            id=f"memstore_{len(self._stores) + 1:04d}",
            name=name,
            description=description,
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._stores.append(store)
        self.created.append({"name": name, "description": description})
        return store

    def delete(self, store_id: str):
        self._stores = [s for s in self._stores if getattr(s, "id", None) != store_id]
        self.deleted.append(store_id)
        return SimpleNamespace(deleted=True, id=store_id)


class _FakeBeta:
    def __init__(self, stores: _FakeMemoryStoresAPI) -> None:
        self.memory_stores = stores


class _FakeClient:
    def __init__(self, stores: _FakeMemoryStoresAPI) -> None:
        self.beta = _FakeBeta(stores)


def _store(id_: str, name: str, *, days_old: int = 0) -> Any:
    created = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat(timespec="seconds")
    return SimpleNamespace(id=id_, name=name, created_at=created)


@pytest.fixture
def cwd_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(memcli, "PROPOSED_DIR", tmp_path / "data/memory/proposed_promotions")
    monkeypatch.setattr(memcli, "REJECTED_DIR", tmp_path / "data/memory/rejected_promotions")
    monkeypatch.setattr(memcli, "PROMOTION_LOG", tmp_path / "data/memory/promotion_log.jsonl")
    return tmp_path


# ---------------------------------------------------------------------------
# 1. list_managed_memory_stores
# ---------------------------------------------------------------------------
def test_list_managed_memory_stores_table_and_json(capsys: pytest.CaptureFixture):
    from scripts import list_managed_memory_stores as lms

    stores = _FakeMemoryStoresAPI(
        preexisting=[
            _store("memstore_a", "bb-platform-priors", days_old=10),
            _store("memstore_b", "bb-case-foo", days_old=5),
        ]
    )
    client = _FakeClient(stores)

    rows = lms.list_stores(client)
    assert {r["name"] for r in rows} == {"bb-platform-priors", "bb-case-foo"}
    assert all("id" in r and "created_at" in r for r in rows)


# ---------------------------------------------------------------------------
# 2. archive dry-run
# ---------------------------------------------------------------------------
def test_archive_dry_run_lists_old_case_stores(capsys: pytest.CaptureFixture):
    from scripts import archive_old_case_memory_stores as arc

    stores = _FakeMemoryStoresAPI(
        preexisting=[
            _store("memstore_p", "bb-platform-priors", days_old=99),
            _store("memstore_old", "bb-case-old", days_old=45),
            _store("memstore_new", "bb-case-new", days_old=2),
            _store("memstore_legacy", "bb-forensic-learnings-x", days_old=60),
        ]
    )
    client = _FakeClient(stores)

    rc = arc.archive(client, days=30, apply=False)
    assert rc == 0
    assert stores.deleted == []
    out = capsys.readouterr().out
    assert "DRY-RUN" in out
    assert "bb-case-old" in out
    assert "bb-forensic-learnings-x" in out
    assert "bb-platform-priors" not in out
    assert "bb-case-new" not in out


# ---------------------------------------------------------------------------
# 3. archive guard against platform-priors
# ---------------------------------------------------------------------------
def test_archive_apply_never_deletes_platform_priors():
    from scripts import archive_old_case_memory_stores as arc

    stores = _FakeMemoryStoresAPI(
        preexisting=[
            _store("memstore_p", "bb-platform-priors", days_old=99),
            _store("memstore_old", "bb-case-old", days_old=45),
        ]
    )
    client = _FakeClient(stores)

    rc = arc.archive(client, days=30, apply=True)
    assert rc == 0
    assert "memstore_old" in stores.deleted
    assert "memstore_p" not in stores.deleted


# ---------------------------------------------------------------------------
# 4. delete guard against platform-priors
# ---------------------------------------------------------------------------
def test_delete_case_memory_store_refuses_platform(capsys: pytest.CaptureFixture):
    from scripts import delete_case_memory_store as dcs

    stores = _FakeMemoryStoresAPI(
        preexisting=[_store("memstore_p", "bb-platform-priors", days_old=1)]
    )
    client = _FakeClient(stores)

    rc = dcs.delete_store(client, id_=None, name="bb-platform-priors", yes=True)
    assert rc == 3
    assert stores.deleted == []
    err = capsys.readouterr().err
    assert "refused" in err


def test_delete_case_memory_store_deletes_named_case_store():
    from scripts import delete_case_memory_store as dcs

    stores = _FakeMemoryStoresAPI(
        preexisting=[
            _store("memstore_p", "bb-platform-priors", days_old=1),
            _store("memstore_old", "bb-case-old", days_old=1),
        ]
    )
    client = _FakeClient(stores)
    rc = dcs.delete_store(client, id_=None, name="bb-case-old", yes=True)
    assert rc == 0
    assert stores.deleted == ["memstore_old"]


# ---------------------------------------------------------------------------
# 5. propose-promotion
# ---------------------------------------------------------------------------
def test_propose_promotion_prints_proposal(cwd_tmp: Path, capsys: pytest.CaptureFixture):
    memcli.PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "analysis_id": "case_42",
        "priors": [{"path": "/priors/foo.md", "content": "hello"}],
    }
    (memcli.PROPOSED_DIR / "case_42.json").write_text(json.dumps(payload))

    rc = memcli.main(["propose-promotion", "case_42"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "case_42" in out
    assert "/priors/foo.md" in out


def test_propose_promotion_missing_returns_error(cwd_tmp: Path, capsys: pytest.CaptureFixture):
    rc = memcli.main(["propose-promotion", "nope"])
    assert rc == 1
    assert "no proposal" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 6. diff-promotion
# ---------------------------------------------------------------------------
def test_diff_promotion_shows_new_path(cwd_tmp: Path, capsys: pytest.CaptureFixture):
    memcli.PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "analysis_id": "case_43",
        "priors": [{"path": "/priors/new.md", "content": "freshly verified"}],
    }
    (memcli.PROPOSED_DIR / "case_43.json").write_text(json.dumps(payload))

    stores = _FakeMemoryStoresAPI(
        preexisting=[_store("memstore_p", "bb-platform-priors", days_old=1)],
        mems={"memstore_p": []},
    )
    client = _FakeClient(stores)

    rc = memcli.main(["diff-promotion", "case_43"], client=client)
    assert rc == 0
    out = capsys.readouterr().out
    assert "/priors/new.md" in out
    assert "NEW" in out


def test_diff_promotion_shows_textual_diff(cwd_tmp: Path, capsys: pytest.CaptureFixture):
    memcli.PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "analysis_id": "case_44",
        "priors": [{"path": "/priors/x.md", "content": "v2 content\nline\n"}],
    }
    (memcli.PROPOSED_DIR / "case_44.json").write_text(json.dumps(payload))

    existing = SimpleNamespace(
        id="mem_1",
        path="/priors/x.md",
        content="v1 content\nline\n",
        _versions=[],
    )
    stores = _FakeMemoryStoresAPI(
        preexisting=[_store("memstore_p", "bb-platform-priors", days_old=1)],
        mems={"memstore_p": [existing]},
    )
    client = _FakeClient(stores)

    rc = memcli.main(["diff-promotion", "case_44"], client=client)
    assert rc == 0
    out = capsys.readouterr().out
    assert "v1 content" in out
    assert "v2 content" in out


# ---------------------------------------------------------------------------
# 7. approve-promotion roundtrip
# ---------------------------------------------------------------------------
def test_approve_promotion_writes_and_audits(cwd_tmp: Path, capsys: pytest.CaptureFixture):
    memcli.PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "analysis_id": "case_45",
        "priors": [{"path": "/priors/verified.md", "content": "rtk break confirmed"}],
    }
    (memcli.PROPOSED_DIR / "case_45.json").write_text(json.dumps(payload))

    stores = _FakeMemoryStoresAPI(
        preexisting=[_store("memstore_p", "bb-platform-priors", days_old=1)],
    )
    client = _FakeClient(stores)

    rc = memcli.main(["approve-promotion", "case_45"], client=client)
    assert rc == 0
    assert any(c["path"] == "/priors/verified.md" for c in stores.memories.created)

    log = memcli.PROMOTION_LOG.read_text(encoding="utf-8").strip().splitlines()
    assert len(log) == 1
    entry = json.loads(log[0])
    assert entry["kind"] == "approve"
    assert entry["analysis_id"] == "case_45"
    assert "/priors/verified.md" in entry["paths"]


def test_approve_promotion_fails_when_platform_missing(cwd_tmp: Path, capsys: pytest.CaptureFixture):
    memcli.PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"analysis_id": "case_46", "priors": [{"path": "/p.md", "content": "x"}]}
    (memcli.PROPOSED_DIR / "case_46.json").write_text(json.dumps(payload))

    stores = _FakeMemoryStoresAPI(preexisting=[])
    client = _FakeClient(stores)

    rc = memcli.main(["approve-promotion", "case_46"], client=client)
    assert rc == 1
    assert "platform store" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# 8. reject-promotion roundtrip
# ---------------------------------------------------------------------------
def test_reject_promotion_moves_proposal_and_audits(cwd_tmp: Path):
    memcli.PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"analysis_id": "case_47", "priors": [{"path": "/p.md", "content": "x"}]}
    src = memcli.PROPOSED_DIR / "case_47.json"
    src.write_text(json.dumps(payload))

    rc = memcli.main(["reject-promotion", "case_47", "--reason", "operator narrative, not verified"])
    assert rc == 0
    assert not src.exists()
    dest = memcli.REJECTED_DIR / "case_47.json"
    assert dest.exists()
    rejected = json.loads(dest.read_text(encoding="utf-8"))
    assert rejected["_rejected"]["reason"] == "operator narrative, not verified"

    log = memcli.PROMOTION_LOG.read_text(encoding="utf-8").strip().splitlines()
    assert len(log) == 1
    entry = json.loads(log[0])
    assert entry["kind"] == "reject"
    assert entry["analysis_id"] == "case_47"


def test_reject_promotion_requires_reason(cwd_tmp: Path):
    with pytest.raises(SystemExit):
        memcli.main(["reject-promotion", "case_48"])


# ---------------------------------------------------------------------------
# 9. audit-native
# ---------------------------------------------------------------------------
def test_audit_native_prints_paths_and_sha(capsys: pytest.CaptureFixture):
    existing = SimpleNamespace(
        id="mem_1",
        path="/priors/foo.md",
        content="hello world",
        updated_at="2026-04-25T00:00:00+00:00",
        _versions=[SimpleNamespace(id="ver_a", content="hello world")],
    )
    stores = _FakeMemoryStoresAPI(
        preexisting=[_store("memstore_p", "bb-platform-priors", days_old=1)],
        mems={"memstore_p": [existing]},
    )
    client = _FakeClient(stores)

    rc = memcli.main(["audit-native", "--store", "bb-platform-priors"], client=client)
    assert rc == 0
    out = capsys.readouterr().out
    blob = json.loads(out)
    assert blob["store"] == "bb-platform-priors"
    assert blob["memories"][0]["path"] == "/priors/foo.md"
    assert len(blob["memories"][0]["sha256"]) == 64


# ---------------------------------------------------------------------------
# 10. redact-native-version
# ---------------------------------------------------------------------------
def test_redact_native_version_audits(cwd_tmp: Path, capsys: pytest.CaptureFixture):
    stores = _FakeMemoryStoresAPI(
        preexisting=[_store("memstore_p", "bb-platform-priors", days_old=1)],
    )
    client = _FakeClient(stores)
    rc = memcli.main(
        ["redact-native-version", "--version", "ver_42", "--reason", "PII removal"],
        client=client,
    )
    assert rc == 0
    log = memcli.PROMOTION_LOG.read_text(encoding="utf-8").strip().splitlines()
    assert len(log) == 1
    entry = json.loads(log[0])
    assert entry["kind"] == "redact"
    assert entry["version_id"] == "ver_42"
    assert entry["reason"] == "PII removal"
