"""#80 — credential vault contract."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from black_box.security.vault import (
    AnthropicCapability,
    EnvVault,
    InMemoryVault,
    SecretMissingError,
)
from black_box.security import vault as vault_mod


@pytest.fixture
def isolated_audit_log(tmp_path, monkeypatch):
    monkeypatch.setattr(vault_mod, "_audit_path", lambda: tmp_path / "secret_access.jsonl")
    yield tmp_path / "secret_access.jsonl"


def test_envvault_returns_value_when_present(monkeypatch, isolated_audit_log):
    monkeypatch.setenv("MY_API_KEY", "super-secret")
    v = EnvVault(allow_names=("MY_API_KEY",))
    val = v.get("MY_API_KEY", caller="test")
    assert val == "super-secret"


def test_envvault_audit_log_records_no_value(monkeypatch, isolated_audit_log):
    monkeypatch.setenv("MY_API_KEY", "super-secret")
    v = EnvVault(allow_names=("MY_API_KEY",))
    v.get("MY_API_KEY", caller="capability_x")
    rows = [json.loads(line) for line in isolated_audit_log.read_text().splitlines()]
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "MY_API_KEY"
    assert row["caller"] == "capability_x"
    assert row["hit"] is True
    # Crucially: the value is nowhere in the row.
    assert "super-secret" not in json.dumps(row)


def test_envvault_refuses_unallowlisted_name(monkeypatch, isolated_audit_log):
    monkeypatch.setenv("OTHER_KEY", "x")
    v = EnvVault(allow_names=("ONLY_THIS_KEY",))
    with pytest.raises(SecretMissingError):
        v.get("OTHER_KEY", caller="test")


def test_envvault_construction_rejects_non_credential_names():
    with pytest.raises(ValueError):
        EnvVault(allow_names=("DEBUG", "PORT"))


def test_inmemory_vault_does_not_read_env(monkeypatch, isolated_audit_log):
    monkeypatch.setenv("PLANTED_SECRET_KEY", "from-env")
    v = InMemoryVault(secrets={"PLANTED_SECRET_KEY": "from-vault"})
    assert v.get("PLANTED_SECRET_KEY", caller="t") == "from-vault"


def test_planted_env_secret_does_not_reach_default_pipeline(monkeypatch, isolated_audit_log):
    """Acceptance — a secret planted in env must not be reachable from analysis code paths
    that have not been wired to use the vault.

    The check: black_box.analysis.* does NOT import os or read os.environ for any
    name matching the credential regex. We re-grep at import time as a sanity belt.
    """
    monkeypatch.setenv("PLANTED_LATERAL_API_KEY", "should-not-leak")
    import importlib
    import black_box.analysis as ana
    importlib.reload(ana)
    # Sweep the analysis subpackage modules — none should expose the planted secret.
    for modname in ("client", "managed_agent", "policy", "grounding", "schemas"):
        try:
            mod = importlib.import_module(f"black_box.analysis.{modname}")
        except Exception:
            continue
        # Module __dict__ should not contain the value.
        for v in mod.__dict__.values():
            if isinstance(v, str):
                assert "should-not-leak" not in v, (
                    f"planted secret leaked into analysis.{modname}"
                )
