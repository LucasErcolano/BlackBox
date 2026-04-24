# SPDX-License-Identifier: MIT
"""L1..L4 typed memory layers.

Each layer is a thin wrapper around ``JsonlStore`` that owns its own file
and exposes retrieval helpers tailored to how the analysis pipeline uses
that layer. All files live under ``<memory_root>/<layer>.jsonl``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .records import CaseRecord, EvalRecord, PlatformPrior, TaxonomyCount
from .store import JsonlStore, default_memory_root


class CaseMemory:
    """L1 — per-case session scratchpad."""

    def __init__(self, root: Path | None = None) -> None:
        self._store = JsonlStore((root or default_memory_root()) / "L1_case.jsonl", CaseRecord)

    def log(self, record: CaseRecord) -> None:
        self._store.append(record)

    def for_case(self, case_key: str) -> list[CaseRecord]:
        return [r for r in self._store.iter_all() if r.case_key == case_key]  # type: ignore[misc]


class PlatformMemory:
    """L2 — platform priors: signal signature -> bug class."""

    def __init__(self, root: Path | None = None) -> None:
        self._store = JsonlStore(
            (root or default_memory_root()) / "L2_platform.jsonl", PlatformPrior
        )

    def log(self, prior: PlatformPrior) -> None:
        self._store.append(prior)

    def priors_for(self, platform: str) -> list[PlatformPrior]:
        return [r for r in self._store.iter_all() if r.platform == platform]  # type: ignore[misc]

    def top_signatures(self, platform: str, k: int = 5) -> list[PlatformPrior]:
        """Return the k highest-confidence priors for a platform.

        Ties break on `hits` (more hits wins). Stable within ties.
        """
        priors = self.priors_for(platform)
        return sorted(priors, key=lambda p: (p.confidence, p.hits), reverse=True)[:k]


class TaxonomyMemory:
    """L3 — global bug_class x signature tally."""

    def __init__(self, root: Path | None = None) -> None:
        self._store = JsonlStore(
            (root or default_memory_root()) / "L3_taxonomy.jsonl", TaxonomyCount
        )

    def log(self, row: TaxonomyCount) -> None:
        self._store.append(row)

    def totals_by_class(self) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for r in self._store.iter_all():
            counter[r.bug_class] += r.count  # type: ignore[attr-defined]
        return dict(counter)

    def totals_by_signature(self) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for r in self._store.iter_all():
            counter[r.signature] += r.count  # type: ignore[attr-defined]
        return dict(counter)


class EvalMemory:
    """L4 — synthetic QA ground truth / prediction pairs."""

    def __init__(self, root: Path | None = None) -> None:
        self._store = JsonlStore((root or default_memory_root()) / "L4_eval.jsonl", EvalRecord)

    def log(self, record: EvalRecord) -> None:
        self._store.append(record)

    def all(self) -> list[EvalRecord]:
        return self._store.all()  # type: ignore[return-value]

    def accuracy(self) -> float:
        """Overall predicted-bug == ground-truth-bug accuracy. Empty store -> 0.0."""
        records = self.all()
        if not records:
            return 0.0
        return sum(1 for r in records if r.match) / len(records)

    def accuracy_by_case(self) -> dict[str, float]:
        """Per-case_key accuracy — used by the hackathon eval harness."""
        buckets: dict[str, list[bool]] = {}
        for r in self.all():
            buckets.setdefault(r.case_key, []).append(r.match)
        return {k: sum(vs) / len(vs) for k, vs in buckets.items()}

    def accuracy_by_bug_class(self) -> dict[str, float]:
        """Per-ground-truth-bug_class accuracy.

        Buckets by the ground-truth class so a per-class weakness shows up
        even when the model predicted something else entirely.
        """
        buckets: dict[str, list[bool]] = {}
        for r in self.all():
            buckets.setdefault(r.ground_truth_bug, []).append(r.match)
        return {k: sum(vs) / len(vs) for k, vs in buckets.items()}


@dataclass
class MemoryStack:
    """Bundle of all 4 layers, rooted at a common directory."""

    case: CaseMemory
    platform: PlatformMemory
    taxonomy: TaxonomyMemory
    eval: EvalMemory

    @classmethod
    def open(cls, root: Path | None = None) -> "MemoryStack":
        r = root or default_memory_root()
        return cls(
            case=CaseMemory(r),
            platform=PlatformMemory(r),
            taxonomy=TaxonomyMemory(r),
            eval=EvalMemory(r),
        )
