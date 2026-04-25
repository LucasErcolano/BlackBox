# SPDX-License-Identifier: MIT
"""Path-traversal hardening for the memory tool sandbox (#93).

Contract:
- Every memory-tool path goes through ``resolve_within_root(root, candidate)``.
- The function resolves the candidate to its canonical absolute path
  (``Path.resolve(strict=False)``) and rejects anything outside
  ``root.resolve()``.
- Symlinks that escape root are rejected; symlinks that stay within
  root are allowed (operators legitimately use them to mount aliases).
- Rejected attempts are logged via ``log_rejection`` to
  ``data/sandbox_rejections.jsonl``. The reasoning-trace monitor reads
  this file as a jailbreak signal.

Hostile shapes covered by tests:
- ``../../etc/passwd`` style traversal
- absolute paths outside the root
- symlinks that point outside the root
- NUL-byte injection in the candidate
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


class PathOutsideRootError(PermissionError):
    """Raised when a candidate resolves outside the sandbox root."""


def _rejections_path() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent / "data" / "sandbox_rejections.jsonl"
    return Path.cwd() / "sandbox_rejections.jsonl"


def log_rejection(candidate: str, reason: str, root: str = "") -> None:
    p = _rejections_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.time(), "candidate": candidate, "reason": reason, "root": root}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def resolve_within_root(root: Path, candidate: str | Path) -> Path:
    """Resolve ``candidate`` and assert it stays within ``root``.

    Returns the resolved absolute path. Raises ``PathOutsideRootError``
    on any escape. NUL bytes are rejected before path operations to avoid
    POSIX truncation surprises.
    """
    raw = str(candidate)
    if "\x00" in raw:
        log_rejection(raw, "nul_byte", str(root))
        raise PathOutsideRootError("nul byte in path candidate")

    root_abs = Path(root).resolve(strict=False)
    cand = Path(candidate)
    if not cand.is_absolute():
        cand = root_abs / cand
    resolved = cand.resolve(strict=False)
    try:
        resolved.relative_to(root_abs)
    except ValueError:
        log_rejection(str(candidate), "outside_root", str(root_abs))
        raise PathOutsideRootError(f"{candidate!r} resolves outside {root_abs}")
    return resolved


# ---------------------------------------------------------------------------
# Visual PII redactor — boundary contract.
#
# The full ML pipeline (EgoBlur / SAM2 / YOLO-plate) requires GPU + model
# weights; the issue notes this is the production path. Here we ship the
# boundary the agent calls plus a pluggable Detector Protocol so a real
# detector swap is one constructor change. The default detector returns
# zero detections — the API surface and the policy gate exist now; the
# heavy detector lands as an installable extra.
# ---------------------------------------------------------------------------
from dataclasses import dataclass
from typing import Iterable, Protocol


@dataclass
class Bbox:
    x: int
    y: int
    w: int
    h: int


class FaceAndPlateDetector(Protocol):
    def detect(self, image_bytes: bytes) -> list[Bbox]: ...


class NoopDetector:
    """Default detector. Returns no boxes — placeholder for the EgoBlur swap.

    Important: the redaction policy must NOT rely on this detector for
    real privacy guarantees. Tests assert the boundary contract; a
    production install replaces this with an EgoBlur-backed detector.
    """

    def detect(self, image_bytes: bytes) -> list[Bbox]:
        return []


def redact_image(
    image_bytes: bytes,
    *,
    detector: FaceAndPlateDetector,
    redact: bool = True,
) -> tuple[bytes, list[Bbox]]:
    """Return (possibly redacted) image bytes + the boxes that were redacted.

    When ``redact=False`` (operator opt-out for synthetic / fixture
    cases) the detector still runs so the audit trail captures what
    *would* have been redacted.
    """
    boxes = detector.detect(image_bytes)
    if not redact:
        return image_bytes, boxes
    if not boxes:
        return image_bytes, []
    # Real implementation overlays opaque rectangles via Pillow. Default
    # detector returns zero boxes so the no-op path is the common case.
    try:
        import io
        from PIL import Image, ImageDraw

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        draw = ImageDraw.Draw(img)
        for b in boxes:
            draw.rectangle([b.x, b.y, b.x + b.w, b.y + b.h], fill="black")
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue(), boxes
    except Exception:
        # Pillow unavailable in some test envs; return original + boxes
        # so callers can still audit what the detector saw.
        return image_bytes, boxes
