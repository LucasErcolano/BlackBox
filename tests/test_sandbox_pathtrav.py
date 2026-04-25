"""#93 — path-traversal hardening + visual PII boundary."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from black_box.security.sandbox import (
    Bbox,
    NoopDetector,
    PathOutsideRootError,
    log_rejection,
    redact_image,
    resolve_within_root,
)
from black_box.security import sandbox as sandbox_mod


@pytest.fixture(autouse=True)
def isolated_rejections_log(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox_mod, "_rejections_path", lambda: tmp_path / "rejections.jsonl")
    yield tmp_path / "rejections.jsonl"


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "root"
    r.mkdir()
    yield r


def test_relative_path_inside_root_is_resolved(root):
    out = resolve_within_root(root, "case_a/file.json")
    assert str(out).startswith(str(root.resolve()))


def test_dotdot_traversal_rejected(root):
    with pytest.raises(PathOutsideRootError):
        resolve_within_root(root, "../../etc/passwd")


def test_absolute_path_outside_root_rejected(root):
    with pytest.raises(PathOutsideRootError):
        resolve_within_root(root, "/etc/passwd")


def test_nul_byte_rejected(root):
    with pytest.raises(PathOutsideRootError):
        resolve_within_root(root, "file\x00name")


def test_symlink_escape_rejected(root, tmp_path):
    # Create a sensitive file outside root and symlink to it from inside.
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = root / "alias"
    os.symlink(outside, link)
    with pytest.raises(PathOutsideRootError):
        resolve_within_root(root, "alias")


def test_symlink_inside_root_allowed(root):
    target = root / "real.txt"
    target.write_text("ok", encoding="utf-8")
    link = root / "link_to_real"
    os.symlink(target, link)
    out = resolve_within_root(root, "link_to_real")
    assert out == target.resolve()


def test_rejection_logged_with_reason(root, isolated_rejections_log):
    with pytest.raises(PathOutsideRootError):
        resolve_within_root(root, "../../etc/passwd")
    rows = [json.loads(l) for l in isolated_rejections_log.read_text().splitlines()]
    assert any(r["reason"] == "outside_root" for r in rows)


def test_redactor_calls_detector_and_returns_boxes():
    """Boundary contract: detector is called; boxes are returned alongside bytes."""
    captured = []

    class _SpyDetector:
        def detect(self, image_bytes):
            captured.append(len(image_bytes))
            return [Bbox(x=10, y=10, w=20, h=20)]

    fake_image = b"\xff\xd8\xff\xe0fake_jpeg" + b"\x00" * 100
    out_bytes, boxes = redact_image(fake_image, detector=_SpyDetector(), redact=False)
    # redact=False keeps the original bytes but still surfaces the boxes for audit.
    assert captured == [len(fake_image)]
    assert len(boxes) == 1 and boxes[0].w == 20


def test_noop_detector_returns_no_boxes():
    out, boxes = redact_image(b"x", detector=NoopDetector())
    assert out == b"x"
    assert boxes == []
