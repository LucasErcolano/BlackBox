# SPDX-License-Identifier: MIT
"""PII / secret sanitizer for the platform-priors promotion gate.

Pure-Python regex + YAML allow-list. No ML, no external services, no model
calls. Runs INSIDE :func:`promote_verified_priors_to_managed_memory` BEFORE
any ``memories.create`` is issued so that a single offending entry refuses
the whole batch.

Two severities:

* ``redact`` — content is rewritten in place with a deterministic placeholder
  (e.g. ``[REDACTED:license_plate]``). Promotion proceeds with the cleaned
  content.
* ``block`` — promotion is refused. The caller must fix the source upstream
  (operator-supplied names should be allow-listed; secrets should never have
  been written down at all).

Detector classes (closed set):

  ``api_key``           — ``sk-...``, ``ghp_...``, ``AKIA...``, JWT, long hex.
                          Always BLOCK.
  ``private_url``       — ``localhost``, RFC1918, ``*.internal``, ``*.local``,
                          ``*.corp.*``. Always BLOCK.
  ``local_path``        — absolute paths on the operator's machine. REDACT.
  ``license_plate``     — US / EU / AR-style plates. REDACT.
  ``operator_name``     — ``operator <Name>``, ``driver <First> <Last>`` etc.
                          BLOCK unless name is in the allow-list.
  ``customer_name``     — same shape as ``operator_name`` but for customer /
                          company tokens. BLOCK unless allow-listed.
  ``site_name``         — facility / site identifiers. BLOCK unless
                          allow-listed.

The closed-by-default posture is deliberate: an empty allow-list means "no
names land in `bb-platform-priors` at all", which is the desired starting
state until the team explicitly opts each name in.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional


class UnsafePromotionContentError(RuntimeError):
    """Promotion refused: at least one ``block``-severity finding."""


@dataclass(frozen=True)
class Finding:
    kind: str
    severity: str
    matched: str
    span: tuple[int, int]
    reason: str


@dataclass
class SanitizerResult:
    blocked: List[Finding] = field(default_factory=list)
    redacted: List[Finding] = field(default_factory=list)
    cleaned_content: str = ""


@dataclass(frozen=True)
class AllowList:
    operator_names: tuple[str, ...] = ()
    customer_names: tuple[str, ...] = ()
    site_names: tuple[str, ...] = ()

    @staticmethod
    def empty() -> "AllowList":
        return AllowList()

    @staticmethod
    def load(path: Path | str | None = None) -> "AllowList":
        """Load allow-list from YAML.

        ``path=None`` resolves to ``<repo>/config/sanitizer_allowlist.yaml``.
        Missing file is treated as an empty allow-list (closed-by-default).
        """
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "PyYAML is required for AllowList.load; install pyyaml."
            ) from exc

        if path is None:
            path = _default_allowlist_path()
        p = Path(path)
        if not p.exists():
            return AllowList.empty()
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(
                f"sanitizer allow-list must be a YAML mapping; got {type(raw).__name__}"
            )
        return AllowList(
            operator_names=tuple(_str_list(raw.get("operator_names", []))),
            customer_names=tuple(_str_list(raw.get("customer_names", []))),
            site_names=tuple(_str_list(raw.get("site_names", []))),
        )

    def is_allowed(self, kind: str, name: str) -> bool:
        canon = name.strip().lower()
        if not canon:
            return True
        bucket: tuple[str, ...]
        if kind == "operator_name":
            bucket = self.operator_names
        elif kind == "customer_name":
            bucket = self.customer_names
        elif kind == "site_name":
            bucket = self.site_names
        else:
            return False
        return any(canon == n.strip().lower() for n in bucket)


def _str_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"expected list, got {type(value).__name__}")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"expected string entry, got {type(item).__name__}")
        out.append(item)
    return out


def _default_allowlist_path() -> Path:
    here = Path(__file__).resolve()
    # src/black_box/memory/sanitizer.py -> repo_root/config/...
    repo_root = here.parents[3]
    return repo_root / "config" / "sanitizer_allowlist.yaml"


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------
_RE_API_KEY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("anthropic", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("github_pat", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")),
    ("hex_token", re.compile(r"\b[a-fA-F0-9]{32,}\b")),
)

_RE_PRIVATE_URL = re.compile(
    r"https?://"
    r"(?:"
    r"localhost"
    r"|127\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|[A-Za-z0-9._\-]+\.internal"
    r"|[A-Za-z0-9._\-]+\.local"
    r"|[A-Za-z0-9._\-]+\.corp\.[A-Za-z0-9._\-]+"
    r")"
    r"(?:[:/][^\s]*)?",
    re.IGNORECASE,
)

_RE_LOCAL_PATH_POSIX = re.compile(r"(?<![A-Za-z0-9_])(?:/Users/|/home/)[A-Za-z0-9._\-/]+")
_RE_LOCAL_PATH_WIN = re.compile(r"\b[A-Za-z]:\\[A-Za-z0-9._\-\\]+")

# Plates: keep the regex generous per Lucas being from Argentina.
#
# US 5-8 alphanumeric, often with dashes/spaces, optionally state-prefixed.
# AR civilian: ``AB 123 CD`` (post-2016) or ``ABC 123`` (legacy).
# EU: ``AB-123-CD`` / ``AB 12 CDE`` etc. The shared shape is two-or-more
# letter clusters separated from a digit cluster by space or dash.
_RE_PLATE_AR_NEW = re.compile(r"\b[A-Z]{2}\s?\d{3}\s?[A-Z]{2}\b")
_RE_PLATE_AR_LEGACY = re.compile(r"\b[A-Z]{3}\s?\d{3}\b")
_RE_PLATE_US = re.compile(r"\b[A-Z]{1,3}[\s\-]?\d{2,4}[\s\-]?[A-Z]{0,3}\b")
_RE_PLATE_EU = re.compile(r"\b[A-Z]{1,3}\-\d{1,4}\-[A-Z]{1,3}\b")

# Operator / driver / pilot / customer / site triggers. We capture two
# capitalised words after the keyword as the candidate name, then consult the
# allow-list before deciding block vs allow.
_RE_OPERATOR_NAME = re.compile(
    r"\b(?:operator|driver|pilot|technician)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b"
)
_RE_CUSTOMER_NAME = re.compile(
    r"\b(?:customer|client|account)\s+([A-Z][A-Za-z0-9&.\-]+(?:\s+[A-Z][A-Za-z0-9&.\-]+){0,3})\b"
)
_RE_SITE_NAME = re.compile(
    r"\b(?:site|facility|warehouse|plant|depot)\s+([A-Z][A-Za-z0-9.\-]+(?:\s+[A-Z0-9][A-Za-z0-9.\-]+){0,2})\b"
)


def _redact(content: str, span: tuple[int, int], placeholder: str) -> str:
    a, b = span
    return content[:a] + placeholder + content[b:]


def _scan_api_keys(content: str) -> list[Finding]:
    out: list[Finding] = []
    for label, pat in _RE_API_KEY_PATTERNS:
        for m in pat.finditer(content):
            out.append(
                Finding(
                    kind="api_key",
                    severity="block",
                    matched=m.group(0),
                    span=m.span(),
                    reason=f"detected {label} secret token",
                )
            )
    return out


def _scan_private_urls(content: str) -> list[Finding]:
    return [
        Finding(
            kind="private_url",
            severity="block",
            matched=m.group(0),
            span=m.span(),
            reason="detected internal/private URL host",
        )
        for m in _RE_PRIVATE_URL.finditer(content)
    ]


def _scan_local_paths(content: str) -> list[Finding]:
    out: list[Finding] = []
    for pat in (_RE_LOCAL_PATH_POSIX, _RE_LOCAL_PATH_WIN):
        for m in pat.finditer(content):
            out.append(
                Finding(
                    kind="local_path",
                    severity="redact",
                    matched=m.group(0),
                    span=m.span(),
                    reason="absolute filesystem path leaks operator workstation layout",
                )
            )
    return out


def _scan_plates(content: str) -> list[Finding]:
    out: list[Finding] = []
    seen_spans: set[tuple[int, int]] = set()
    for pat in (_RE_PLATE_AR_NEW, _RE_PLATE_AR_LEGACY, _RE_PLATE_EU, _RE_PLATE_US):
        for m in pat.finditer(content):
            if m.span() in seen_spans:
                continue
            seen_spans.add(m.span())
            out.append(
                Finding(
                    kind="license_plate",
                    severity="redact",
                    matched=m.group(0),
                    span=m.span(),
                    reason="vehicle plate shape detected",
                )
            )
    return out


def _scan_named_entities(
    content: str,
    pattern: re.Pattern[str],
    kind: str,
    allow_list: AllowList,
) -> list[Finding]:
    out: list[Finding] = []
    for m in pattern.finditer(content):
        candidate = m.group(1)
        if allow_list.is_allowed(kind, candidate):
            continue
        out.append(
            Finding(
                kind=kind,
                severity="block",
                matched=m.group(0),
                span=m.span(),
                reason=(
                    f"{kind.replace('_', ' ')} {candidate!r} is not in the "
                    f"sanitizer allow-list (config/sanitizer_allowlist.yaml)"
                ),
            )
        )
    return out


def scan(
    content: str,
    *,
    allow_list: AllowList | None = None,
) -> SanitizerResult:
    """Run every detector over ``content`` and return findings + cleaned text.

    The function never raises on unsafe content; it accumulates ``blocked``
    findings instead. Callers needing the strict raise-on-unsafe semantics
    use :func:`assert_safe_for_platform_promotion`.
    """
    if not isinstance(content, str):
        raise TypeError("sanitizer.scan expects str content")
    al = allow_list or AllowList.empty()

    findings: list[Finding] = []
    findings.extend(_scan_api_keys(content))
    findings.extend(_scan_private_urls(content))
    findings.extend(_scan_local_paths(content))
    findings.extend(_scan_plates(content))
    findings.extend(_scan_named_entities(content, _RE_OPERATOR_NAME, "operator_name", al))
    findings.extend(_scan_named_entities(content, _RE_CUSTOMER_NAME, "customer_name", al))
    findings.extend(_scan_named_entities(content, _RE_SITE_NAME, "site_name", al))

    blocked = [f for f in findings if f.severity == "block"]
    redacted = [f for f in findings if f.severity == "redact"]

    cleaned = _apply_redactions(content, redacted)

    return SanitizerResult(
        blocked=blocked,
        redacted=redacted,
        cleaned_content=cleaned,
    )


def _apply_redactions(content: str, redacted: Iterable[Finding]) -> str:
    # Apply right-to-left so spans stay valid as we splice.
    ordered = sorted(redacted, key=lambda f: f.span[0], reverse=True)
    out = content
    for f in ordered:
        placeholder = f"[REDACTED:{f.kind}]"
        out = _redact(out, f.span, placeholder)
    return out


def assert_safe_for_platform_promotion(
    content: str,
    *,
    allow_list: AllowList | None = None,
) -> str:
    """Return cleaned content or raise :class:`UnsafePromotionContentError`.

    ``redact`` findings are auto-applied; ``block`` findings refuse the
    promotion. The error message lists every blocked finding so the operator
    can fix the source.
    """
    result = scan(content, allow_list=allow_list)
    if result.blocked:
        bullet_lines = "\n".join(
            f"  - [{f.kind}] {f.reason}: {_excerpt(f.matched)}"
            for f in result.blocked
        )
        raise UnsafePromotionContentError(
            "refusing to promote prior — sanitizer found blocking content:\n"
            + bullet_lines
        )
    return result.cleaned_content


def _excerpt(s: str, *, limit: int = 60) -> str:
    s = s.replace("\n", " ")
    return s if len(s) <= limit else s[: limit - 1] + "\u2026"


__all__ = [
    "AllowList",
    "Finding",
    "SanitizerResult",
    "UnsafePromotionContentError",
    "assert_safe_for_platform_promotion",
    "scan",
]
