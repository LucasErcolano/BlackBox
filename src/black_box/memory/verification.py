# SPDX-License-Identifier: MIT
"""Append-only human-verification ledger.

Operators record "agent concluded X, real cause was Y" without rewriting the
original L1 record. Notes are tamper-evident by being append-only at two
levels:

1. Per-analysis `verification_note.md` — markdown block appended next to L1
   so a human reading the case folder sees the dispute.
2. Global `data/memory/verification.jsonl` — structured records cross-run, so
   PolicyAdvisor can downweight a hypothesis class that has been disputed.

Both files are write-only-append. There is no delete or edit API. A
correction is itself a new appended note.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from pydantic import BaseModel, Field

from .store import JsonlStore, default_memory_root


class VerificationNote(BaseModel):
    """One operator-authored verification entry. Append-only."""

    analysis_id: str = Field(description="job_id or session slug the note is about")
    operator_id: str = Field(description="who wrote the note (login / email / handle)")
    written_at: str = Field(description="ISO-8601 UTC timestamp")
    agent_conclusion: str = Field(description="what the agent said — quoted verbatim, do not paraphrase")
    real_cause: str = Field(description="what actually happened, per the operator")
    disputed_class: Optional[str] = Field(
        default=None,
        description="bug-taxonomy class the operator disputes (PolicyAdvisor uses this as a negative prior)",
    )
    severity: str = Field(default="dispute", description="dispute | correction | confirmation")


def _global_ledger_path() -> Path:
    return default_memory_root() / "verification.jsonl"


def _global_store() -> JsonlStore:
    return JsonlStore(_global_ledger_path(), VerificationNote)


def _per_analysis_path(analysis_root: Path) -> Path:
    return Path(analysis_root) / "verification_note.md"


def _markdown_block(note: VerificationNote) -> str:
    sev = note.severity.upper()
    disputed = f" — disputed_class=`{note.disputed_class}`" if note.disputed_class else ""
    return (
        f"\n---\n"
        f"### {sev} — {note.written_at}{disputed}\n"
        f"**Operator:** `{note.operator_id}`\n\n"
        f"**Agent concluded:**\n\n"
        f"> {note.agent_conclusion}\n\n"
        f"**Real cause (per operator):**\n\n"
        f"> {note.real_cause}\n"
    )


def add_note(
    analysis_root: Path,
    note: VerificationNote,
) -> Path:
    """Append a note to both the per-analysis MD and the global JSONL.

    Returns the path of the per-analysis MD that was appended to.
    """
    md_path = _per_analysis_path(analysis_root)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    if not md_path.exists():
        md_path.write_text(
            f"# Human verification ledger — `{note.analysis_id}`\n\n"
            "Append-only. Each entry below is a human override of, or commentary on, "
            "the agent's conclusion for this analysis. Edits are forbidden by convention; "
            "corrections are themselves new entries.\n",
            encoding="utf-8",
        )

    with md_path.open("a", encoding="utf-8") as f:
        f.write(_markdown_block(note))

    _global_store().append(note)
    return md_path


def iter_notes_for(analysis_id: str) -> Iterator[VerificationNote]:
    for n in _global_store().iter_all():
        if n.analysis_id == analysis_id:
            yield n  # type: ignore[misc]


def disputes_for_class(disputed_class: str) -> list[VerificationNote]:
    """Return every note that disputes a given taxonomy class.

    PolicyAdvisor consumes this as a negative prior — repeated disputes on a
    bug class lower the confidence floor for new hypotheses of that class.
    """
    return [
        n  # type: ignore[misc]
        for n in _global_store().iter_all()
        if getattr(n, "disputed_class", None) == disputed_class
    ]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Promotion gate for native managed-agents memory stores
# ---------------------------------------------------------------------------
class UnverifiedMemoryPromotionError(RuntimeError):
    """Raised when promotion to the read-only platform store is attempted
    with an entry that is not flagged as human-verified.

    The native platform store represents verified human-curated knowledge.
    Promoting unverified L1 case records or freshly-extracted operator
    narratives into it would defeat the safety contract. This error is
    deliberately loud — callers must opt in by either passing
    `verified=True` per-entry or by sourcing entries from the global
    verification ledger with `severity == "confirmation"`.
    """


def promote_verified_priors_to_managed_memory(
    client,
    store_id: str,
    verified_priors: list[dict],
    *,
    require_verified: bool = True,
    allow_list: "AllowList | None" = None,
) -> list[str]:
    """Write human-verified priors into the read-only platform memory store.

    `verified_priors` is a list of dicts shaped like:
        {"path": "/priors/foo.md", "content": "...", "verified": True}

    Pipeline (atomic — every check runs over the whole batch before any
    SDK mutation):

      1. structural validation (`path` + `content` present)
      2. human-verification gate (this module)
      3. PII / secret sanitizer (``black_box.memory.sanitizer``)

    Each entry is rejected unless ``verified is True`` OR the entry
    references an analysis_id whose verification ledger contains a
    `severity == "confirmation"` note. Failures raise
    `UnverifiedMemoryPromotionError` BEFORE any SDK call; the platform
    store is never partially mutated by an unverified or unsafe batch.

    This is the load-bearing safety contract: untrusted recording content
    cannot reach the platform store without passing through both the human
    ledger and the sanitizer.
    """
    from .sanitizer import (
        AllowList,
        UnsafePromotionContentError,
        assert_safe_for_platform_promotion,
    )

    stores_api = getattr(getattr(client, "beta", None), "memory_stores", None)
    if stores_api is None:
        raise RuntimeError(
            "client.beta.memory_stores is not available; cannot promote priors."
        )
    memories_api = getattr(stores_api, "memories", None)
    if memories_api is None:
        raise RuntimeError(
            "client.beta.memory_stores.memories is not available; cannot promote priors."
        )

    if allow_list is None:
        allow_list = AllowList.load()

    # Validate the whole batch before mutating.
    cleaned: list[tuple[str, str]] = []
    for prior in verified_priors:
        path = prior.get("path")
        content = prior.get("content")
        if not path or content is None:
            raise ValueError(
                f"prior must include 'path' and 'content' keys; got {prior!r}"
            )
        if require_verified and not _is_verified(prior):
            raise UnverifiedMemoryPromotionError(
                f"refusing to promote {path!r}: entry is not flagged "
                "verified=True and has no confirmation note in the "
                "verification ledger. Untrusted recording content cannot "
                "reach the platform store."
            )
        try:
            safe_content = assert_safe_for_platform_promotion(
                content, allow_list=allow_list
            )
        except UnsafePromotionContentError as exc:
            raise UnsafePromotionContentError(
                f"refusing to promote {path!r}: {exc}"
            ) from exc
        cleaned.append((path, safe_content))

    written: list[str] = []
    for path, safe_content in cleaned:
        result = memories_api.create(
            memory_store_id=store_id,
            path=path,
            content=safe_content,
        )
        rid = getattr(result, "id", None)
        if rid is not None:
            written.append(rid)
    return written


def _is_verified(prior: dict) -> bool:
    """An entry passes the gate if either:

    1. It carries an explicit ``verified=True`` flag (caller takes
       responsibility — used for human-curated bootstrap seeds), OR
    2. Its `analysis_id` has at least one `severity == "confirmation"`
       note in the global verification ledger.
    """
    if prior.get("verified") is True:
        return True
    analysis_id = prior.get("analysis_id")
    if not analysis_id:
        return False
    for note in iter_notes_for(analysis_id):
        if getattr(note, "severity", None) == "confirmation":
            return True
    return False
