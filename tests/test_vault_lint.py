"""#80 — lint guard: only the vault module reads credential-shaped env vars."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "black_box"

# Allowed-readers list. Anything else hitting an env name matching the regex
# below is a boundary violation.
ALLOWED = {
    "src/black_box/security/vault.py",
    "src/black_box/cli.py",  # only generic args, no credential names
}

# Pattern: os.environ['*KEY'], os.environ.get('*KEY'), os.getenv('*KEY')
# where the literal name matches credential shape.
CRED_NAME = r"[A-Z][A-Z0-9_]*?(?:KEY|TOKEN|PASSWORD|SECRET|API_KEY)"
PATTERNS = [
    re.compile(rf"os\.environ\[\s*['\"]({CRED_NAME})['\"]\s*\]"),
    re.compile(rf"os\.environ\.get\(\s*['\"]({CRED_NAME})['\"]"),
    re.compile(rf"os\.getenv\(\s*['\"]({CRED_NAME})['\"]"),
]


def test_no_raw_credential_env_reads_outside_vault():
    offenders: list[tuple[str, str, str]] = []
    for py in SRC.rglob("*.py"):
        rel = str(py.relative_to(ROOT))
        if rel in ALLOWED:
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        for pat in PATTERNS:
            for m in pat.finditer(text):
                offenders.append((rel, m.group(0), m.group(1)))
    assert not offenders, (
        "credential-shaped env reads outside the vault module (#80):\n"
        + "\n".join(f"  {f}: {snippet}" for f, snippet, _ in offenders)
        + "\nRoute these through black_box.security.vault.* capabilities."
    )
