"""Unit tests for the central Anthropic client factory.

Guards the managed-agents-2026-04-01 beta header contract. The Managed Agents
endpoint rejects any request missing the header; schema tests cannot catch
that because the failure is in the transport layer.
"""
from __future__ import annotations

from unittest import mock

import pytest

from black_box.analysis import client as client_mod
from black_box.analysis.client import (
    MANAGED_AGENTS_BETA,
    build_client,
    default_headers,
)


def test_managed_agents_beta_constant_is_exact():
    assert MANAGED_AGENTS_BETA == "managed-agents-2026-04-01"


def test_default_headers_contains_beta_token():
    headers = default_headers()
    assert "anthropic-beta" in headers
    assert MANAGED_AGENTS_BETA in headers["anthropic-beta"]


def test_default_headers_merges_extra_betas_without_duplicates():
    headers = default_headers(extra_betas=["foo-2026-01-01", MANAGED_AGENTS_BETA])
    parts = headers["anthropic-beta"].split(",")
    assert parts.count(MANAGED_AGENTS_BETA) == 1
    assert "foo-2026-01-01" in parts


def test_build_client_passes_beta_header_to_sdk():
    with mock.patch.object(client_mod, "Anthropic") as fake_anthropic:
        build_client(api_key="sk-test")
        fake_anthropic.assert_called_once()
        kwargs = fake_anthropic.call_args.kwargs
        assert kwargs["api_key"] == "sk-test"
        beta = kwargs["default_headers"]["anthropic-beta"]
        assert MANAGED_AGENTS_BETA in beta


def test_build_client_merges_extra_headers_over_defaults():
    with mock.patch.object(client_mod, "Anthropic") as fake_anthropic:
        build_client(api_key="sk-test", extra_headers={"x-trace-id": "abc123"})
        kwargs = fake_anthropic.call_args.kwargs
        assert kwargs["default_headers"]["x-trace-id"] == "abc123"
        # beta must still be present after merge
        assert MANAGED_AGENTS_BETA in kwargs["default_headers"]["anthropic-beta"]


def test_build_client_falls_back_to_env_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
    with mock.patch.object(client_mod, "Anthropic") as fake_anthropic:
        build_client()
        assert fake_anthropic.call_args.kwargs["api_key"] == "sk-env"


def test_no_direct_anthropic_instantiation_in_analysis_package():
    """Repo-wide guard: outside client.py, nothing may instantiate Anthropic()."""
    import pathlib
    import re

    analysis_dir = pathlib.Path(client_mod.__file__).parent
    offenders = []
    pattern = re.compile(r"\bAnthropic\s*\(")
    for py in analysis_dir.rglob("*.py"):
        if py.name == "client.py":
            continue
        text = py.read_text()
        for i, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{py.name}:{i}: {line.strip()}")
    assert not offenders, (
        "Direct Anthropic(...) instantiations found outside client.py:\n"
        + "\n".join(offenders)
    )
