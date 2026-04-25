# SPDX-License-Identifier: MIT
"""HTTP Basic auth gate for mutating UI routes.

Hackathon-shape access control: a single op-role keyed off two env vars
(`BLACKBOX_AUTH_USER`, `BLACKBOX_AUTH_PASSWORD`). The gate is **off by
default** (`BLACKBOX_AUTH_REQUIRED!="1"`) so the local-trust path of
`network=none` (#79) keeps working unchanged. Operators who expose the
FastAPI server beyond localhost flip the flag to `1`.

Scope is deliberately tiny: no sessions, no OAuth, no multi-role RBAC.
The only role gated is "may mutate forensic state".

Credentials live in the credential vault (#80) — passwords are
credential-shaped (`*_PASSWORD`) so the vault lint accepts them.
"""

from __future__ import annotations

import os
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .vault import EnvVault, SecretMissingError

_BASIC = HTTPBasic(auto_error=False)


def _auth_required() -> bool:
    return os.environ.get("BLACKBOX_AUTH_REQUIRED") == "1"


def _expected_user() -> str:
    return os.environ.get("BLACKBOX_AUTH_USER", "operator")


def _expected_password() -> Optional[str]:
    """Fetch the configured op-role password from the vault.

    Returns None if not provisioned — callers treat this as a misconfig
    when auth is required (503), separate from a 401 wrong-password.
    """
    try:
        return EnvVault(allow_names=("BLACKBOX_AUTH_PASSWORD",)).get(
            "BLACKBOX_AUTH_PASSWORD", caller="ui_auth_gate"
        )
    except SecretMissingError:
        return None


def require_auth(
    credentials: Optional[HTTPBasicCredentials] = Depends(_BASIC),
) -> str:
    """FastAPI dependency: 401 unless valid Basic creds when gate is on.

    Returns the authenticated username so handlers can log it. When the
    gate is off (default), returns "anonymous" without inspecting the
    request — preserves the back-compat behaviour of the open server.
    """
    if not _auth_required():
        return "anonymous"
    expected_pw = _expected_password()
    if expected_pw is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="auth required but BLACKBOX_AUTH_PASSWORD is not provisioned",
        )
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing Basic credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    user_ok = secrets.compare_digest(credentials.username, _expected_user())
    pw_ok = secrets.compare_digest(credentials.password, expected_pw)
    if not (user_ok and pw_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
