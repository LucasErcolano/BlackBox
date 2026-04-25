# SPDX-License-Identifier: MIT
"""Credential vault — capabilities, not secrets.

Per #80 the boundary is: **secrets never enter the model's input**. The
agent calls capability wrappers; the wrappers know which secret they
need, fetch it from the vault, perform the action, and return sanitized
results. The model sees ``{"status": "ok", "rows_returned": 3}`` shape,
not the connection string.

This module is the only sanctioned reader of credential-shaped env vars
(``*_KEY``, ``*_TOKEN``, ``*_PASSWORD``, ``*_SECRET``). A repo-wide lint
in ``tests/test_vault_lint.py`` rejects raw reads outside this module.

Storage strategy:
- Pluggable. Default is a ``EnvVault`` reading from process env, kept
  process-local (no ``__repr__`` of values, no logging of values).
- An ``AgeFileVault`` is documented in ``SECURITY.md`` as the production
  path; its implementation depends on ``pyrage`` / ``age`` and is left
  as an installable extra (out of scope for this hackathon submission).

Audit log:
- Every ``get_secret`` call appends a row to ``data/secret_access.jsonl``
  with timestamp, secret name, and caller — **never the value**.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol

# Bare module: no top-level imports of black_box internals.

CREDENTIAL_NAME_RE = re.compile(r".*(KEY|TOKEN|PASSWORD|SECRET|API_KEY)$")


def has_credential(name: str) -> bool:
    """Cheap presence check for a credential. Does not return the value.

    The lint guard in tests/test_vault_lint.py treats the vault module as
    the only sanctioned reader of credential-shaped env names. Code that
    only needs to know *whether* a credential is provisioned (e.g. to
    decide between live vs stub mode) calls this helper instead of
    reading the env directly.
    """
    return bool(os.environ.get(name))


def get_credential(name: str, *, caller: str) -> str:
    """Capability fetch with audit. Wraps EnvVault for callers that
    legitimately need the bytes (Anthropic SDK construction, etc.).
    """
    return EnvVault(allow_names=(name,)).get(name, caller=caller)


def _audit_path() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent / "data" / "secret_access.jsonl"
    return Path.cwd() / "secret_access.jsonl"


def _audit(name: str, caller: str, hit: bool) -> None:
    p = _audit_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "name": name,
        "caller": caller,
        "hit": bool(hit),
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


class SecretMissingError(KeyError):
    """Raised when a requested secret is not provisioned."""


class Vault(Protocol):
    def get(self, name: str, *, caller: str) -> str: ...


@dataclass
class EnvVault:
    """Reads credentials from process env. Audit log on every access.

    Values are never returned via ``__repr__`` and the dataclass holds
    no plaintext fields itself.
    """

    allow_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for n in self.allow_names:
            if not CREDENTIAL_NAME_RE.match(n):
                raise ValueError(
                    f"vault refuses to manage {n!r}; name must end with "
                    f"KEY/TOKEN/PASSWORD/SECRET/API_KEY."
                )

    def get(self, name: str, *, caller: str) -> str:
        if self.allow_names and name not in self.allow_names:
            _audit(name, caller, hit=False)
            raise SecretMissingError(f"secret {name!r} not in vault allowlist")
        val = os.environ.get(name)
        _audit(name, caller, hit=val is not None)
        if val is None:
            raise SecretMissingError(f"secret {name!r} not provisioned")
        return val


# ---------------------------------------------------------------------------
# Capability wrappers — what the agent calls instead of asking for secrets.
# ---------------------------------------------------------------------------
@dataclass
class AnthropicCapability:
    """Constructs and returns an authenticated Anthropic client.

    The client itself contains the key in a closure; callers see only
    the client object, never the bytes. This is the canonical entry
    point for any code path that needs to call Anthropic.
    """

    vault: Vault = field(default_factory=lambda: EnvVault(allow_names=("ANTHROPIC_API_KEY",)))

    def client(self, *, caller: str = "anthropic_capability"):
        try:
            from anthropic import Anthropic  # local import keeps tests light
        except Exception as exc:  # pragma: no cover - dep failure path
            raise RuntimeError(f"anthropic SDK unavailable: {exc}") from exc
        key = self.vault.get("ANTHROPIC_API_KEY", caller=caller)
        return Anthropic(api_key=key)


# ---------------------------------------------------------------------------
# Helper for tests — deterministic in-memory vault that does NOT touch env.
# ---------------------------------------------------------------------------
@dataclass
class InMemoryVault:
    secrets: dict[str, str] = field(default_factory=dict)

    def get(self, name: str, *, caller: str) -> str:
        _audit(name, caller, hit=name in self.secrets)
        if name not in self.secrets:
            raise SecretMissingError(name)
        return self.secrets[name]
