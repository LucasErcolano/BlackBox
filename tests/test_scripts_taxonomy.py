"""#90 — every executable in scripts/ must be classified in scripts/README.md.

Catches the case where a new script lands without a one-line purpose row.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
README = SCRIPTS / "README.md"

# Files in scripts/ that are not runnable scripts and don't need rows.
NON_SCRIPT_FILES = {"README.md", "NAO6_CAPTURE_GUIDE.md"}


def test_every_script_is_classified():
    actual = {p.name for p in SCRIPTS.iterdir() if p.is_file()}
    actual -= NON_SCRIPT_FILES
    text = README.read_text(encoding="utf-8")
    missing = sorted(name for name in actual if f"`{name}`" not in text)
    assert not missing, (
        f"scripts/README.md is missing rows for {len(missing)} scripts: {missing}. "
        f"Add a one-line purpose row under the appropriate category (eval / demo / ops / dev)."
    )
