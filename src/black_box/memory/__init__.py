# SPDX-License-Identifier: MIT
"""4-layer memory stack for Black Box.

Layers, each a flat JSONL store under ``data/memory/``:

* **L1 case**      — per-case session scratchpad (hypotheses, evidence, steering).
* **L2 platform**  — per-platform priors (signal signature -> bug_class, confidence).
* **L3 taxonomy**  — global bug-class hit counts across all runs.
* **L4 eval**      — synthetic QA ground-truth pairs for self-eval calibration.

No vector DBs, no embeddings, no RAG. Flat append-only files, deterministic retrieval.
"""

from .layers import (
    CaseMemory,
    EvalMemory,
    MemoryStack,
    PlatformMemory,
    TaxonomyMemory,
)
from .records import (
    CaseRecord,
    EvalRecord,
    PlatformPrior,
    TaxonomyCount,
)
from .verification import (
    UnverifiedMemoryPromotionError,
    VerificationNote,
    add_note,
    disputes_for_class,
    iter_notes_for,
    now_utc_iso,
    promote_verified_priors_to_managed_memory,
)
from .decisions import (
    DecisionRecord,
    PatchNotApprovedError,
    apply_patch_if_approved,
    history_for,
    latest_for,
    record_decision,
    rejected_classes_count,
)

__all__ = [
    "CaseMemory",
    "PlatformMemory",
    "TaxonomyMemory",
    "EvalMemory",
    "MemoryStack",
    "CaseRecord",
    "PlatformPrior",
    "TaxonomyCount",
    "EvalRecord",
    "VerificationNote",
    "UnverifiedMemoryPromotionError",
    "add_note",
    "disputes_for_class",
    "iter_notes_for",
    "now_utc_iso",
    "promote_verified_priors_to_managed_memory",
    "DecisionRecord",
    "PatchNotApprovedError",
    "apply_patch_if_approved",
    "history_for",
    "latest_for",
    "record_decision",
    "rejected_classes_count",
]
