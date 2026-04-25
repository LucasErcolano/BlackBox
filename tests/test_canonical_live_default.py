"""#75 — default UI worker is live; no silent stub fallback."""
from __future__ import annotations

import pytest


def test_real_pipeline_default_on_when_key_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("BLACKBOX_REAL_PIPELINE", raising=False)
    from black_box.ui.app import _real_pipeline_enabled
    assert _real_pipeline_enabled() is True


def test_real_pipeline_off_when_no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("BLACKBOX_REAL_PIPELINE", raising=False)
    from black_box.ui.app import _real_pipeline_enabled
    assert _real_pipeline_enabled() is False


def test_explicit_disable_with_real_pipeline_zero(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("BLACKBOX_REAL_PIPELINE", "0")
    from black_box.ui.app import _real_pipeline_enabled
    assert _real_pipeline_enabled() is False


def test_real_pipeline_no_silent_stub_fallback_on_exception():
    """Acceptance: live pipeline failure must surface, not silently route to stub."""
    import inspect
    from black_box.ui import app as app_mod
    src = inspect.getsource(app_mod._run_pipeline_real)
    # Pre-#75 the except branch called _run_pipeline_stub. That path is gone.
    assert "_run_pipeline_stub(job_id" not in src, (
        "live pipeline silently falls back to stub — #75 forbids this; "
        "surface the error to the operator instead."
    )
    assert "_push(\"failed\"" in src or "stage='failed'" in src or '"failed"' in src
