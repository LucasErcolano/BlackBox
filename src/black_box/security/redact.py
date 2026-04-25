# SPDX-License-Identifier: MIT
"""Text redactor for prompts + reports.

Targets (in order of precedence):
1. Common API key shapes — Anthropic ``sk-ant-...``, OpenAI ``sk-...``,
   AWS access keys ``AKIA...``, GitHub PATs ``ghp_...`` / ``github_pat_``,
   generic ``Bearer <hex>`` headers.
2. Email addresses.
3. IPv4 + IPv6 + non-loopback hostnames.
4. Absolute filesystem paths under ``/home/<user>/``, ``/Users/<user>/``,
   ``C:\\Users\\<user>\\`` — strip the user prefix while keeping the
   relative tail so the path is still useful in debugging.
5. Generic high-entropy 32+ char base64-ish tokens not whitelisted by an
   earlier rule.

The redactor is deliberately conservative — it lets through plain text
and structured forensic findings; it bites on identifiable secret/PII
shapes. False negatives are expected; false positives on body text are
the worse failure mode for a forensic report.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------
# Order matters — secret patterns first so a key embedded inside a path is
# still redacted.

_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "[REDACTED:anthropic_key]"),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}"), "[REDACTED:openai_key]"),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED:aws_access_key]"),
    ("github_pat", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"), "[REDACTED:github_pat]"),
    ("github_pat_new", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"), "[REDACTED:github_pat]"),
    ("bearer", re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{20,}", re.IGNORECASE), "Bearer [REDACTED:token]"),
    (
        "email",
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED:email]",
    ),
    (
        "ipv4",
        re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d?\d)\b"),
        "[REDACTED:ipv4]",
    ),
    (
        "ipv6",
        re.compile(r"\b(?:[A-Fa-f0-9]{1,4}:){2,7}[A-Fa-f0-9]{1,4}\b"),
        "[REDACTED:ipv6]",
    ),
    (
        "abs_home_unix",
        re.compile(r"/home/[A-Za-z0-9._\-]+"),
        "/home/<user>",
    ),
    (
        "abs_users_macos",
        re.compile(r"/Users/[A-Za-z0-9._\-]+"),
        "/Users/<user>",
    ),
    (
        "abs_users_win",
        re.compile(r"[A-Za-z]:\\Users\\[A-Za-z0-9._\-]+", re.IGNORECASE),
        r"C:\\Users\\<user>",
    ),
]

# Loopback / private hostnames that are safe to keep verbatim. Anything else
# matching the hostname shape is redacted at end-of-pipeline.
_HOSTNAME_RE = re.compile(r"\b(?=[A-Za-z0-9-]{1,63}\.)(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}\b")
_HOSTNAME_ALLOW = {
    "localhost",
    "anthropic.com",
    "claude.ai",
    "github.com",
    "githubusercontent.com",
    "claude.com",
}

# Generic high-entropy base64-ish token. Run *after* known shapes so we don't
# double-redact. Threshold tuned to avoid eating SHA-1/2 hashes that legitimately
# appear in commit references (those stay verbatim — 7-40 hex chars).
_TOKEN_LOOKING = re.compile(r"\b[A-Za-z0-9+/=_\-]{40,}\b")


@dataclass
class RedactionStats:
    counts: dict[str, int]

    def total(self) -> int:
        return sum(self.counts.values())


def _redact_hostnames(text: str) -> tuple[str, int]:
    n = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal n
        host = m.group(0).lower()
        for allow in _HOSTNAME_ALLOW:
            if host == allow or host.endswith("." + allow):
                return m.group(0)
        n += 1
        return "[REDACTED:hostname]"

    return _HOSTNAME_RE.sub(repl, text), n


def _redact_high_entropy(text: str) -> tuple[str, int]:
    n = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal n
        s = m.group(0)
        # Skip already-redacted markers and pure hex (commit-shape).
        if "[REDACTED" in s:
            return s
        if re.fullmatch(r"[0-9a-fA-F]+", s) and len(s) <= 64:
            return s  # likely a SHA-1/2 hash, keep
        n += 1
        return "[REDACTED:token]"

    return _TOKEN_LOOKING.sub(repl, text), n


def redact_text(text: str) -> tuple[str, RedactionStats]:
    """Run the redactor over ``text``. Returns redacted text + per-rule stats."""
    counts: dict[str, int] = {}
    for name, pat, replacement in _PATTERNS:
        new_text, n = pat.subn(replacement, text)
        if n:
            counts[name] = n
            text = new_text
    text, n = _redact_hostnames(text)
    if n:
        counts["hostname"] = n
    text, n = _redact_high_entropy(text)
    if n:
        counts["high_entropy"] = n
    return text, RedactionStats(counts=counts)


def redact_paths(paths: list[str]) -> list[str]:
    """Apply path-only rules to a list of strings (e.g. file index entries)."""
    out: list[str] = []
    for p in paths:
        red, _ = redact_text(p)
        out.append(red)
    return out
