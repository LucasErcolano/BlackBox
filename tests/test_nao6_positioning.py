"""Doc-lint: NAO6 must remain a bonus adapter, not a judged-beat platform.

Per #91, NAO6 should appear only as a one-line generalization proof. Catches
regressions where pitch/demo/onboarding docs reintroduce NAO6 as a primary
platform.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Paths that drive the judged demo. Stronger constraint here.
HERO_DOCS = [
    "docs/PITCH.md",
    "docs/DEMO_SCRIPT.md",
    "docs/SUBMISSION.md",
]

# Phrases that imply NAO6 is a primary / hero / live-demoed platform.
FORBIDDEN_PATTERNS = [
    r"two platforms[^.]*nao6",
    r"nao6[^.]*hero",
    r"nao6 (live|hero) demo",
    r"nao6 footage",
]


NEGATION = re.compile(r"\b(don't|didn'?t|not|never|no longer|won't|deprec|descop|bonus|adapter)\b")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8").lower()


def test_hero_docs_do_not_promote_nao6_to_primary():
    for doc in HERO_DOCS:
        for line in _read(doc).splitlines():
            if NEGATION.search(line):
                continue
            for pat in FORBIDDEN_PATTERNS:
                if re.search(pat, line):
                    raise AssertionError(
                        f"{doc} line '{line.strip()}' positively asserts a NAO6 "
                        f"primary/hero claim; per #91 NAO6 is bonus only."
                    )


def test_pitch_carries_bonus_framing_for_nao6():
    text = _read("docs/SUBMISSION.md")
    if "nao6" in text:
        assert "bonus" in text or "adapter" in text, (
            "SUBMISSION.md mentions NAO6 without 'bonus' / 'adapter' framing."
        )
