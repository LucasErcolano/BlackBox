# SPDX-License-Identifier: MIT
"""Auth gate semantics for mutating UI routes (#117).

Off by default → mutating POSTs unchanged (back-compat). Flag on with
provisioned creds → 401 missing/wrong, accepts valid Basic. Flag on
without provisioned creds → 503 misconfig.
"""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from black_box.ui.app import app


def _basic(user: str, pw: str) -> dict[str, str]:
    raw = f"{user}:{pw}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_gate_off_by_default_get_routes_open(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BLACKBOX_AUTH_REQUIRED", raising=False)
    r = client.get("/")
    assert r.status_code == 200


def test_gate_off_post_verify_does_not_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BLACKBOX_AUTH_REQUIRED", raising=False)
    r = client.post("/verify/no_such_job", data={"severity": "dispute"})
    assert r.status_code != 401


def test_gate_on_missing_creds_returns_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLACKBOX_AUTH_REQUIRED", "1")
    monkeypatch.setenv("BLACKBOX_AUTH_PASSWORD", "s3cret")
    r = client.post("/verify/no_such_job", data={})
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate", "").startswith("Basic")


def test_gate_on_wrong_password_returns_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLACKBOX_AUTH_REQUIRED", "1")
    monkeypatch.setenv("BLACKBOX_AUTH_PASSWORD", "s3cret")
    r = client.post(
        "/verify/no_such_job",
        data={},
        headers=_basic("operator", "wrong"),
    )
    assert r.status_code == 401


def test_gate_on_valid_creds_passes_through(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLACKBOX_AUTH_REQUIRED", "1")
    monkeypatch.setenv("BLACKBOX_AUTH_PASSWORD", "s3cret")
    r = client.post(
        "/verify/no_such_job",
        data={"severity": "dispute"},
        headers=_basic("operator", "s3cret"),
    )
    assert r.status_code != 401


def test_gate_on_unprovisioned_password_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BLACKBOX_AUTH_REQUIRED", "1")
    monkeypatch.delenv("BLACKBOX_AUTH_PASSWORD", raising=False)
    r = client.post("/verify/no_such_job", data={}, headers=_basic("operator", "any"))
    assert r.status_code == 503


def test_gate_on_get_routes_still_open(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLACKBOX_AUTH_REQUIRED", "1")
    monkeypatch.setenv("BLACKBOX_AUTH_PASSWORD", "s3cret")
    r = client.get("/")
    assert r.status_code == 200
