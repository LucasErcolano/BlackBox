"""Unit tests for `scripts/managed_memory_smoke.py`.

These tests must NEVER call the model. They cover the prechecks and the
artifact filename contract Lucas asked for. Live-edge behavior is covered
by running the harness manually after an SDK bump.
"""
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "managed_memory_smoke.py"


def _load_smoke_module():
    spec = importlib.util.spec_from_file_location("managed_memory_smoke_under_test", SCRIPT_PATH)
    assert spec and spec.loader, "spec_from_file_location must succeed for the smoke script"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def smoke():
    return _load_smoke_module()


def test_help_runs_clean(smoke):
    with mock.patch.object(sys, "argv", ["managed_memory_smoke", "--help"]):
        with pytest.raises(SystemExit) as exc_info:
            smoke.parse_args(["--help"])
        assert exc_info.value.code == 0


def test_sdk_precheck_fails_when_memory_stores_missing(smoke, capsys):
    """0.96.0 lacks beta.memory_stores; harness must exit 2 with the pip hint."""
    fake_beta_class = type("Beta", (), {})  # no memory_stores attribute
    fake_resources_beta = SimpleNamespace(Beta=fake_beta_class)
    fake_anthropic = SimpleNamespace(__version__="0.96.0", Anthropic=object)

    with mock.patch.dict(
        sys.modules,
        {
            "anthropic": fake_anthropic,
            "anthropic.resources": SimpleNamespace(beta=fake_resources_beta),
            "anthropic.resources.beta": fake_resources_beta,
        },
    ):
        rc = smoke.main(["--bag", "/tmp/fake.bag", "--case-key", "smoke_t"])
    assert rc == 2, "SDK precheck must exit with code 2"
    captured = capsys.readouterr()
    assert "memory_stores" in captured.err
    assert "pip install -U anthropic" in captured.err


def test_api_key_precheck_fails_when_unset(smoke, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rc = smoke.main(["--bag", "/tmp/fake.bag", "--case-key", "smoke_t"])
    assert rc == 2, "API key precheck must exit with code 2"
    captured = capsys.readouterr()
    assert "ANTHROPIC_API_KEY" in captured.err


def test_yes_precheck_fails_without_confirmation(smoke, monkeypatch, capsys):
    """Even with SDK + API key satisfied, --yes is required to proceed."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-precheck-only")

    rc = smoke.main(["--bag", "/tmp/fake.bag", "--case-key", "smoke_t"])
    assert rc == 2, "confirmation precheck must exit with code 2"
    captured = capsys.readouterr()
    assert "--yes" in captured.err
    assert "$0.50" in captured.err and "$1.50" in captured.err


def test_budget_cap_rejects_above_hard_cap(smoke, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-precheck-only")
    rc = smoke.main(
        [
            "--bag",
            "/tmp/fake.bag",
            "--case-key",
            "smoke_t",
            "--budget-usd",
            "10.00",
            "--yes",
        ]
    )
    assert rc == 2
    captured = capsys.readouterr()
    assert "exceeds hard cap" in captured.err


def test_artifact_filenames_match_lucas_contract(smoke):
    """Lucas asked for these exact filenames. Lock the contract."""
    expected = {
        "session_events_excerpt.jsonl",
        "mounted_memory_listing.txt",
        "platform_read_attempt.txt",
        "platform_write_rejected.txt",
        "case_store_write_success.txt",
        "final_report.json",
        "README.md",
    }
    assert set(smoke.ARTIFACT_NAMES) == expected


def test_atomic_write_round_trips(smoke, tmp_path):
    target = tmp_path / "nested" / "out.txt"
    smoke.atomic_write(target, "hello\n")
    assert target.read_text() == "hello\n"
    assert not (target.parent / "out.txt.tmp").exists(), "tmp must be renamed away"


def test_atomic_write_accepts_bytes(smoke, tmp_path):
    target = tmp_path / "blob.bin"
    smoke.atomic_write(target, b"\x00\x01\x02")
    assert target.read_bytes() == b"\x00\x01\x02"
