# Memory promotion pipeline

This is the contract for moving a prior from the local 4-layer stack
(`L1 case → L2 platform → L3 taxonomy → L4 eval`) into the **native Anthropic
Managed Agents memory store** (`bb-platform-priors`). The native store is
shared across cases / customers, read-only at session time, and survives the
session, so the bar for landing content there is much higher than for the
local JSONL.

Audit context: this document covers Lucas's audit asks **#6** (PII / secret
sanitization on the way in) and **#7** (concurrency / atomicity guarantees
for the create-only platform seed).

## Pipeline

```
verify  →  sanitize  →  diff (review)  →  promote
```

Each stage is a hard gate. A failure at any stage refuses the whole batch;
nothing partial reaches the platform store.

### 1. verify  (`black_box.memory.verification`)

The human-verification ledger is append-only at two levels (per-analysis MD
and global JSONL). A prior is allowed past this stage iff:

- it carries an explicit `verified=True` flag (caller takes responsibility,
  e.g. human-curated bootstrap seeds), **or**
- it references an `analysis_id` that has at least one ledger note with
  `severity == "confirmation"`.

Failures raise `UnverifiedMemoryPromotionError`.

### 2. sanitize  (`black_box.memory.sanitizer`)

Pure-Python regex pass over `content`. No ML, no model calls. Two
severities:

| severity   | action            | typical kinds                                           |
|------------|-------------------|---------------------------------------------------------|
| `block`    | refuse whole batch | `api_key`, `private_url`, `operator_name`, `customer_name`, `site_name` |
| `redact`   | rewrite content   | `local_path`, `license_plate`                           |

Operator / customer / site names are **closed-by-default**: the empty
allow-list at `config/sanitizer_allowlist.yaml` means no names land in the
platform store until a human edits the YAML and adds them. Adding a name
to the allow-list is itself a deliberate, reviewable change.

Public API:

```python
from black_box.memory import scan, assert_safe_for_platform_promotion, AllowList

result = scan(content)                        # never raises; returns SanitizerResult
clean = assert_safe_for_platform_promotion(   # raises UnsafePromotionContentError on block
    content,
    allow_list=AllowList.load(),
)
```

The promotion function calls `assert_safe_for_platform_promotion` per
prior **before any** `memories.create` call (see atomicity below).

### 3. diff (review)

Today: the sanitized `cleaned_content` differs from the original whenever
a `local_path` or `license_plate` was redacted. Operators inspect this
diff via the per-analysis verification MD before flipping the
`severity == "confirmation"` bit. We do not auto-promote.

This is the slot where a UI-driven approval flow would land if the team
later wants a one-click promote button. The current implementation keeps
the gate code-driven and reviewable.

### 4. promote  (`promote_verified_priors_to_managed_memory`)

Only after every prior in the batch has cleared stages 1–2 do we issue
the SDK calls. Each call is `client.beta.memory_stores.memories.create`
via the `build_client()` factory in `src/black_box/analysis/client.py`.

## Why platform memories are append-only today

The platform seed (`bb-platform-priors`) is **create-only** in our
codebase. We never call `memories.update`. Reasons:

- **Concurrency.** Two forensic sessions running in parallel could both
  read the same prior, both decide to refine it, and race on the write.
  The native API exposes per-version preconditions
  (`If-Match` / `content_sha256`) so updates would have to be coded with
  optimistic concurrency control. Append-only sidesteps this entirely:
  a refinement is a new path (`/priors/v2/...`), not a mutation.
- **Auditability.** With no in-place mutation, every prior the agent
  reads at session time corresponds to a single git-reviewable
  `memories.create` call. Diff `git log -- src/black_box/memory/seed/`
  to see exactly what entered the store and when.
- **Rollback.** Removing a bad prior is `memories.delete` plus a new
  create on a fresh path; we never have to reconstruct a prior version
  from a write-ahead log.

When the team eventually needs in-place updates, the path is documented
in the Anthropic memory_versions docs:

> Updates require a `content_sha256` precondition matching the current
> version. The server rejects with `412 Precondition Failed` if another
> writer landed first.
> — [Anthropic Managed Agents memory_versions](https://docs.anthropic.com/en/docs/agents/managed-agents/memory#versions)

Until that day, **only `create`** is sanctioned in
`src/black_box/memory/verification.py::promote_verified_priors_to_managed_memory`.

## Atomicity guarantee

`promote_verified_priors_to_managed_memory` is atomic at the batch level:

1. The function validates **every** prior in `verified_priors` for
   structural shape, verification status, and sanitizer safety.
2. Only after the whole batch passes does it issue the first
   `memories.create` call.
3. If the sanitizer raises mid-validation, the SDK is **never touched** —
   `client.beta.memory_stores.memories.create` is not called even once.

The test
[`test_memory_sanitizer.py::test_promote_atomic_no_partial_writes_when_sanitizer_blocks_second_entry`](../tests/test_memory_sanitizer.py)
pins this behaviour: a 3-prior batch with a leaked API key in the middle
entry refuses the batch and the fake `memories` API records zero
`create` calls.

What atomicity does **not** cover:

- Network failure between two `create` calls within the same accepted
  batch. We currently let the partial write stand (this is the same
  semantics as L1-L4 JSONL appends — every line is independent). The
  paths are deterministic, so a retry of the same batch is idempotent
  at the *path* level only if the operator uses fresh paths; reusing a
  path raises a server-side conflict.
- Cross-process concurrent promotions targeting the same path. See the
  "append-only today" section — we avoid this by never reusing paths.

## File map

```
config/sanitizer_allowlist.yaml             — operator/customer/site allow-list
src/black_box/memory/sanitizer.py           — detectors, AllowList, scan()
src/black_box/memory/verification.py        — promote_…() pipeline glue
src/black_box/analysis/client.py            — build_client() (managed-agents beta)
tests/test_memory_sanitizer.py              — 21 tests, atomicity included
docs/MEMORY_PROMOTION_PIPELINE.md           — this file
```
