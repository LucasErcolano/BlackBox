# SPDX-License-Identifier: MIT
"""`blackbox-memory` — lifecycle, audit, and promotion CLI for native managed memory stores.

Subcommands:
    audit-native --store NAME              paths, last_modified, version_count, sha256
    export-native-versions --store NAME    full version history dump (delegates to script)
    redact-native-version --version ID --reason TXT
                                            redact a specific memory version (SDK redaction API)
    propose-promotion ANALYSIS_ID          show candidate priors emitted by an agent run
    diff-promotion ANALYSIS_ID             diff proposal against current bb-platform-priors
    approve-promotion ANALYSIS_ID          promote (verified=True) and audit-log
    reject-promotion ANALYSIS_ID --reason  move proposal to rejected/, audit-log

Designed to run on anthropic 0.96.0 (no `memory_stores` exposed) for tests by
guarding every SDK touchpoint with `getattr(client.beta, "memory_stores", None)`.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PLATFORM_STORE_NAME = "bb-platform-priors"

PROPOSED_DIR = Path("data/memory/proposed_promotions")
REJECTED_DIR = Path("data/memory/rejected_promotions")
PROMOTION_LOG = Path("data/memory/promotion_log.jsonl")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stores_api(client: Any) -> Any:
    beta = getattr(client, "beta", None)
    api = getattr(beta, "memory_stores", None)
    if api is None:
        raise RuntimeError(
            "client.beta.memory_stores not available on this anthropic SDK; "
            "upgrade to a build that exposes managed memory stores."
        )
    return api


def _memories_api(client: Any) -> Any:
    api = getattr(_stores_api(client), "memories", None)
    if api is None:
        raise RuntimeError("client.beta.memory_stores.memories not available on this SDK.")
    return api


def _resolve_store(stores_api: Any, key: str) -> Any:
    page = stores_api.list()
    items = getattr(page, "data", None)
    if items is None:
        try:
            items = list(page)
        except TypeError:
            items = []
    for item in items:
        if getattr(item, "id", None) == key or getattr(item, "name", None) == key:
            return item
    return None


def _iter_data(page: Any) -> list[Any]:
    items = getattr(page, "data", None)
    if items is None:
        try:
            items = list(page)
        except TypeError:
            items = []
    return list(items)


def _content_sha(content: Any) -> str | None:
    if isinstance(content, str):
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    return None


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _append_audit(entry: dict[str, Any]) -> None:
    PROMOTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with PROMOTION_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def _platform_content(client: Any) -> dict[str, str]:
    stores_api = _stores_api(client)
    target = _resolve_store(stores_api, PLATFORM_STORE_NAME)
    if target is None:
        return {}
    memories_api = _memories_api(client)
    out: dict[str, str] = {}
    page = memories_api.list(memory_store_id=getattr(target, "id"))
    for m in _iter_data(page):
        path = getattr(m, "path", None)
        content = getattr(m, "content", None)
        if path is not None and isinstance(content, str):
            out[path] = content
    return out


# ---------------------------------------------------------------------------
# audit-native
# ---------------------------------------------------------------------------
def audit_native(client: Any, *, store: str) -> int:
    stores_api = _stores_api(client)
    target = _resolve_store(stores_api, store)
    if target is None:
        print(f"error: no store matched {store!r}", file=sys.stderr)
        return 1
    memories_api = _memories_api(client)
    store_id = getattr(target, "id")
    page = memories_api.list(memory_store_id=store_id)
    rows: list[dict[str, Any]] = []
    for m in _iter_data(page):
        path = getattr(m, "path", None)
        last_modified = str(getattr(m, "updated_at", "") or getattr(m, "created_at", "") or "")
        version_count = getattr(m, "version_count", None)
        if version_count is None:
            versions_api = getattr(memories_api, "versions", None)
            if versions_api is not None:
                try:
                    vpage = versions_api.list(memory_store_id=store_id, path=path)
                    version_count = len(_iter_data(vpage))
                except Exception:
                    version_count = None
        content = getattr(m, "content", None)
        sha = _content_sha(content) or getattr(m, "sha256", None)
        rows.append(
            {
                "path": path,
                "last_modified": last_modified,
                "version_count": version_count,
                "sha256": sha,
            }
        )
    print(json.dumps({"store": store, "store_id": store_id, "memories": rows}, indent=2, sort_keys=True))
    return 0


# ---------------------------------------------------------------------------
# export-native-versions (delegate to script for real API; reuse logic)
# ---------------------------------------------------------------------------
def export_native_versions(client: Any, *, store: str, include_content: bool, output: Path) -> int:
    from scripts.export_memory_versions import export_versions  # type: ignore

    paths, versions = export_versions(
        client, store=store, output_root=output, include_content=include_content
    )
    print(f"done. paths={paths} versions={versions}")
    return 0


# ---------------------------------------------------------------------------
# redact-native-version
# ---------------------------------------------------------------------------
def redact_native_version(client: Any, *, version_id: str, reason: str) -> int:
    if not reason or not reason.strip():
        print("error: --reason is required and must be non-empty.", file=sys.stderr)
        return 2
    memories_api = _memories_api(client)
    redact_fn = (
        getattr(memories_api, "redact", None)
        or getattr(getattr(memories_api, "versions", None), "redact", None)
    )
    if redact_fn is None:
        raise RuntimeError(
            "memories.redact not available on this SDK; upgrade to a build that "
            "exposes the redaction API."
        )
    result = redact_fn(version_id=version_id, reason=reason)
    rid = getattr(result, "id", None) or getattr(result, "version_id", None)
    print(f"redacted version: {rid or version_id}")
    _append_audit(
        {
            "kind": "redact",
            "version_id": version_id,
            "reason": reason,
            "ts": _now_iso(),
        }
    )
    return 0


# ---------------------------------------------------------------------------
# propose-promotion
# ---------------------------------------------------------------------------
def propose_promotion(*, analysis_id: str) -> int:
    proposal_path = PROPOSED_DIR / f"{analysis_id}.json"
    if not proposal_path.exists():
        print(f"error: no proposal at {proposal_path}", file=sys.stderr)
        return 1
    proposal = _load_json(proposal_path)
    print(json.dumps(proposal, indent=2, sort_keys=True))
    return 0


# ---------------------------------------------------------------------------
# diff-promotion
# ---------------------------------------------------------------------------
def _diff_one(path: str, old: str, new: str) -> str:
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a{path}",
        tofile=f"b{path}",
        n=3,
    )
    return "".join(diff)


def diff_promotion(client: Any, *, analysis_id: str) -> int:
    proposal_path = PROPOSED_DIR / f"{analysis_id}.json"
    if not proposal_path.exists():
        print(f"error: no proposal at {proposal_path}", file=sys.stderr)
        return 1
    proposal = _load_json(proposal_path)
    priors: list[dict[str, Any]] = list(proposal.get("priors") or proposal.get("verified_priors") or [])
    if not priors:
        print("(proposal has no priors)")
        return 0

    current = _platform_content(client)
    any_diff = False
    for prior in priors:
        path = prior.get("path")
        new_content = prior.get("content") or ""
        old_content = current.get(path or "", "")
        if old_content == new_content:
            print(f"== {path} (no change)")
            continue
        any_diff = True
        if not old_content:
            print(f"++ {path} (NEW)")
            for ln in new_content.splitlines():
                print(f"+ {ln}")
        else:
            d = _diff_one(path or "", old_content, new_content)
            print(d if d else f"~~ {path} (binary or no textual diff)")
    if not any_diff:
        print("no differences vs current platform priors.")
    return 0


# ---------------------------------------------------------------------------
# approve-promotion
# ---------------------------------------------------------------------------
def approve_promotion(client: Any, *, analysis_id: str) -> int:
    from black_box.memory.verification import promote_verified_priors_to_managed_memory

    proposal_path = PROPOSED_DIR / f"{analysis_id}.json"
    if not proposal_path.exists():
        print(f"error: no proposal at {proposal_path}", file=sys.stderr)
        return 1
    proposal = _load_json(proposal_path)
    priors: list[dict[str, Any]] = list(proposal.get("priors") or proposal.get("verified_priors") or [])
    if not priors:
        print("error: proposal has no priors to promote.", file=sys.stderr)
        return 1

    stores_api = _stores_api(client)
    target = _resolve_store(stores_api, PLATFORM_STORE_NAME)
    if target is None:
        print(f"error: platform store {PLATFORM_STORE_NAME!r} does not exist.", file=sys.stderr)
        return 1
    store_id = getattr(target, "id")

    flagged = [{**p, "verified": True} for p in priors]
    written = promote_verified_priors_to_managed_memory(
        client=client,
        store_id=store_id,
        verified_priors=flagged,
    )
    print(f"approved: promoted {len(written)} priors into {PLATFORM_STORE_NAME} ({store_id}).")
    _append_audit(
        {
            "kind": "approve",
            "analysis_id": analysis_id,
            "store_id": store_id,
            "memory_ids": written,
            "paths": [p.get("path") for p in priors],
            "ts": _now_iso(),
        }
    )
    return 0


# ---------------------------------------------------------------------------
# reject-promotion
# ---------------------------------------------------------------------------
def reject_promotion(*, analysis_id: str, reason: str) -> int:
    if not reason or not reason.strip():
        print("error: --reason is required and must be non-empty.", file=sys.stderr)
        return 2
    proposal_path = PROPOSED_DIR / f"{analysis_id}.json"
    if not proposal_path.exists():
        print(f"error: no proposal at {proposal_path}", file=sys.stderr)
        return 1
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    dest = REJECTED_DIR / f"{analysis_id}.json"
    proposal = _load_json(proposal_path)
    proposal["_rejected"] = {"reason": reason, "ts": _now_iso()}
    with dest.open("w", encoding="utf-8") as fh:
        json.dump(proposal, fh, indent=2, sort_keys=True)
    proposal_path.unlink()
    print(f"rejected: moved {proposal_path} -> {dest}")
    _append_audit(
        {
            "kind": "reject",
            "analysis_id": analysis_id,
            "reason": reason,
            "ts": _now_iso(),
        }
    )
    return 0


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="blackbox-memory",
        description="Lifecycle, audit, and promotion CLI for native managed memory stores.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("audit-native", help="audit memories in a store")
    s.add_argument("--store", required=True)

    s = sub.add_parser("export-native-versions", help="dump version history of a store")
    s.add_argument("--store", required=True)
    s.add_argument("--output", default="data/memory_exports")
    s.add_argument("--include-content", action="store_true")

    s = sub.add_parser("redact-native-version", help="redact one memory version")
    s.add_argument("--version", dest="version_id", required=True)
    s.add_argument("--reason", required=True)

    s = sub.add_parser("propose-promotion", help="show a candidate promotion proposal")
    s.add_argument("analysis_id")

    s = sub.add_parser("diff-promotion", help="diff proposal vs current platform priors")
    s.add_argument("analysis_id")

    s = sub.add_parser("approve-promotion", help="promote a proposal as verified")
    s.add_argument("analysis_id")

    s = sub.add_parser("reject-promotion", help="reject a proposal with reason")
    s.add_argument("analysis_id")
    s.add_argument("--reason", required=True)

    return p


def main(argv: list[str] | None = None, *, client: Any | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    needs_client = args.cmd in {
        "audit-native",
        "export-native-versions",
        "redact-native-version",
        "diff-promotion",
        "approve-promotion",
    }
    if needs_client and client is None:
        from black_box.analysis.client import build_client

        client = build_client()

    try:
        if args.cmd == "audit-native":
            return audit_native(client, store=args.store)
        if args.cmd == "export-native-versions":
            return export_native_versions(
                client,
                store=args.store,
                include_content=args.include_content,
                output=Path(args.output),
            )
        if args.cmd == "redact-native-version":
            return redact_native_version(client, version_id=args.version_id, reason=args.reason)
        if args.cmd == "propose-promotion":
            return propose_promotion(analysis_id=args.analysis_id)
        if args.cmd == "diff-promotion":
            return diff_promotion(client, analysis_id=args.analysis_id)
        if args.cmd == "approve-promotion":
            return approve_promotion(client, analysis_id=args.analysis_id)
        if args.cmd == "reject-promotion":
            return reject_promotion(analysis_id=args.analysis_id, reason=args.reason)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
