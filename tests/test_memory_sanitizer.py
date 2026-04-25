"""Tests for the platform-promotion sanitizer + atomicity of the gate.

Covers Lucas audit asks #6 (PII / secret detection) and #7 (atomic
promotion: no partial writes when the sanitizer raises mid-batch).

All Anthropic SDK calls are stubbed; nothing hits the network. No model
calls anywhere in this file — sanitizer is pure regex.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from black_box.memory import (
    AllowList,
    UnsafePromotionContentError,
    UnverifiedMemoryPromotionError,
    assert_safe_for_platform_promotion,
    promote_verified_priors_to_managed_memory,
    scan,
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
    def __init__(self) -> None:
        self.memories = _FakeMemoriesAPI()


class _FakeBeta:
    def __init__(self) -> None:
        self.memory_stores = _FakeMemoryStoresAPI()


class _FakeClient:
    def __init__(self) -> None:
        self.beta = _FakeBeta()


# ---------------------------------------------------------------------------
# Detector unit tests — positive (catches) + negative (allow-list lets through)
# ---------------------------------------------------------------------------
def test_api_key_openai_is_blocked():
    bad = "leaked: sk-abcdef0123456789abcdefXYZ in prod logs"
    result = scan(bad)
    assert any(f.kind == "api_key" for f in result.blocked)
    with pytest.raises(UnsafePromotionContentError):
        assert_safe_for_platform_promotion(bad)


def test_api_key_github_aws_jwt_hex_all_blocked():
    samples = [
        "ghp_abcdefghijklmnopqrstuvwxyz0123",
        "AKIAABCDEFGHIJKLMNOP",
        "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.SflKxwRJSMeKKF",
        "token: deadbeefcafebabe1234567890abcdef00112233",
    ]
    for s in samples:
        with pytest.raises(UnsafePromotionContentError):
            assert_safe_for_platform_promotion(s)


def test_api_key_clean_text_passes():
    clean = "telemetry shows sensor_timeout in window 12.3-13.4s; no secrets here"
    cleaned = assert_safe_for_platform_promotion(clean)
    assert cleaned == clean


def test_private_url_blocked_localhost_and_internal():
    samples = [
        "see http://localhost:8080/admin",
        "POST https://10.0.0.4/relay",
        "https://api.acme.internal/health",
        "http://control.local",
        "https://gateway.corp.acme.io/x",
    ]
    for s in samples:
        with pytest.raises(UnsafePromotionContentError):
            assert_safe_for_platform_promotion(s)


def test_private_url_negative_public_url_passes():
    s = "see https://docs.anthropic.com/en/docs/agents/managed for spec"
    cleaned = assert_safe_for_platform_promotion(s)
    assert cleaned == s


def test_local_path_is_redacted_not_blocked():
    s = "extracted from /Users/lucas/Recordings/sanfer_drive_03.bag"
    result = scan(s)
    assert result.blocked == []
    assert any(f.kind == "local_path" for f in result.redacted)
    assert "[REDACTED:local_path]" in result.cleaned_content
    assert "/Users/lucas/Recordings" not in result.cleaned_content


def test_local_path_windows_redacted():
    s = r"telemetry from C:\Users\op\bags\drive.bag"
    result = scan(s)
    assert any(f.kind == "local_path" for f in result.redacted)
    assert r"C:\Users\op" not in result.cleaned_content


def test_license_plate_argentine_is_redacted():
    s = "vehicle plate AB 123 CD entered the loading bay"
    result = scan(s)
    assert any(f.kind == "license_plate" for f in result.redacted)
    assert "[REDACTED:license_plate]" in result.cleaned_content


def test_license_plate_us_redacted():
    s = "vehicle plate ABC-1234 was logged"
    result = scan(s)
    assert any(f.kind == "license_plate" for f in result.redacted)


def test_operator_name_blocked_when_not_in_allowlist():
    s = "operator John Smith reviewed the run"
    with pytest.raises(UnsafePromotionContentError):
        assert_safe_for_platform_promotion(s, allow_list=AllowList.empty())


def test_operator_name_passes_when_allowlisted():
    s = "operator John Smith reviewed the run"
    al = AllowList(operator_names=("John Smith",))
    cleaned = assert_safe_for_platform_promotion(s, allow_list=al)
    assert cleaned == s


def test_customer_name_blocked_then_allowed():
    s = "customer Acme Corp signed the SOW"
    with pytest.raises(UnsafePromotionContentError):
        assert_safe_for_platform_promotion(s)
    al = AllowList(customer_names=("Acme Corp",))
    assert assert_safe_for_platform_promotion(s, allow_list=al) == s


def test_site_name_blocked_then_allowed():
    s = "site Plant42 telemetry was clean"
    with pytest.raises(UnsafePromotionContentError):
        assert_safe_for_platform_promotion(s)
    al = AllowList(site_names=("Plant42",))
    assert assert_safe_for_platform_promotion(s, allow_list=al) == s


def test_allowlist_load_missing_file_is_empty(tmp_path: Path):
    al = AllowList.load(tmp_path / "nope.yaml")
    assert al == AllowList.empty()


def test_allowlist_load_yaml_round_trip(tmp_path: Path):
    p = tmp_path / "al.yaml"
    p.write_text(
        "operator_names: [Lucas Ercolano]\n"
        "customer_names: [Sanfer]\n"
        "site_names: []\n",
        encoding="utf-8",
    )
    al = AllowList.load(p)
    assert al.operator_names == ("Lucas Ercolano",)
    assert al.customer_names == ("Sanfer",)
    assert al.site_names == ()


# ---------------------------------------------------------------------------
# Integration: promote_verified_priors_to_managed_memory + sanitizer
# ---------------------------------------------------------------------------
def test_promote_refuses_batch_with_api_key():
    client = _FakeClient()
    batch = [
        {
            "path": "/priors/leak.md",
            "content": "rotate this: sk-abcdef0123456789abcdefXYZQ",
            "verified": True,
        },
    ]
    with pytest.raises(UnsafePromotionContentError):
        promote_verified_priors_to_managed_memory(
            client=client,
            store_id="memstore_platform",
            verified_priors=batch,
            allow_list=AllowList.empty(),
        )
    assert client.beta.memory_stores.memories.created == []


def test_promote_refuses_batch_with_non_allowlisted_operator():
    client = _FakeClient()
    batch = [
        {
            "path": "/priors/op.md",
            "content": "operator Jane Doe drove the rig",
            "verified": True,
        },
    ]
    with pytest.raises(UnsafePromotionContentError):
        promote_verified_priors_to_managed_memory(
            client=client,
            store_id="memstore_platform",
            verified_priors=batch,
            allow_list=AllowList.empty(),
        )
    assert client.beta.memory_stores.memories.created == []


def test_promote_passes_clean_batch_and_applies_redactions():
    client = _FakeClient()
    batch = [
        {
            "path": "/priors/clean.md",
            "content": "sensor_timeout window 12.3-13.4s; refutes operator narrative",
            "verified": True,
        },
        {
            "path": "/priors/path.md",
            "content": "extracted from /Users/lucas/Recordings/x.bag",
            "verified": True,
        },
    ]
    written = promote_verified_priors_to_managed_memory(
        client=client,
        store_id="memstore_platform",
        verified_priors=batch,
        allow_list=AllowList.empty(),
    )
    assert len(written) == 2
    created = client.beta.memory_stores.memories.created
    assert created[0]["content"] == batch[0]["content"]
    assert "[REDACTED:local_path]" in created[1]["content"]
    assert "/Users/lucas/Recordings" not in created[1]["content"]


def test_promote_atomic_no_partial_writes_when_sanitizer_blocks_second_entry():
    """Audit ask #7 — atomicity: a single blocked entry refuses the whole
    batch and `memories.create` is never called.
    """
    client = _FakeClient()
    batch = [
        {
            "path": "/priors/ok.md",
            "content": "clean prior content",
            "verified": True,
        },
        {
            "path": "/priors/leak.md",
            "content": "leaked key sk-abcdef0123456789abcdefXYZQ",
            "verified": True,
        },
        {
            "path": "/priors/also_ok.md",
            "content": "another clean prior",
            "verified": True,
        },
    ]
    with pytest.raises(UnsafePromotionContentError):
        promote_verified_priors_to_managed_memory(
            client=client,
            store_id="memstore_platform",
            verified_priors=batch,
            allow_list=AllowList.empty(),
        )
    assert client.beta.memory_stores.memories.created == []


def test_promote_verification_gate_runs_before_sanitizer():
    """Defence-in-depth: an unverified prior is rejected by the human gate
    before the sanitizer ever runs. Both errors are subclasses of
    `RuntimeError`; we just check the more specific one fires here.
    """
    client = _FakeClient()
    batch = [
        {
            "path": "/priors/unverified.md",
            "content": "totally clean content",
        },
    ]
    with pytest.raises(UnverifiedMemoryPromotionError):
        promote_verified_priors_to_managed_memory(
            client=client,
            store_id="memstore_platform",
            verified_priors=batch,
            allow_list=AllowList.empty(),
        )
    assert client.beta.memory_stores.memories.created == []


def test_promote_uses_default_allowlist_when_not_passed(monkeypatch, tmp_path: Path):
    """If `allow_list` is omitted, `AllowList.load()` is consulted. We point
    it at a tmp YAML so we can exercise the full default path without
    touching the repo file.
    """
    al_path = tmp_path / "al.yaml"
    al_path.write_text("operator_names: [Lucas Ercolano]\n", encoding="utf-8")
    monkeypatch.setattr(
        "black_box.memory.sanitizer._default_allowlist_path",
        lambda: al_path,
    )

    client = _FakeClient()
    batch = [
        {
            "path": "/priors/op.md",
            "content": "operator Lucas Ercolano signed off",
            "verified": True,
        },
    ]
    written = promote_verified_priors_to_managed_memory(
        client=client,
        store_id="memstore_platform",
        verified_priors=batch,
    )
    assert len(written) == 1
