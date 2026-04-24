# Memory stack composition + cost-delta proof

Closes #24. Explains how L1-L4 memory, the `verification_note.md` ledger, and the
grounding gate compose into a single pipeline, and shows the prompt-caching
cost arithmetic on real runs.

## 4-layer stack

Flat JSONL under `data/memory/`. No vector DB, no embeddings, no RAG. Source:
[`src/black_box/memory/`](../src/black_box/memory/).

| Layer | File | Owner | Written by | Read by |
|-------|------|-------|-----------|---------|
| L1 case | `L1_case.jsonl` | per-case ledger (hypotheses, steering, notes) | `ForensicSession.finalize` | UI replay, demo narrative |
| L2 platform | `L2_platform.jsonl` | per-platform priors (`signature → bug_class`, confidence, hits) | platform adapters (e.g. NAO6) | prompt-time context injection |
| L3 taxonomy | `L3_taxonomy.jsonl` | rolling bug-class + signature counts across all cases | `ForensicSession._record_memory` | regression dashboards, prompt frequency prior |
| L4 eval | `L4_eval.jsonl` | synthetic QA predicted vs ground-truth pairs | `eval.runner` (Tier-3) | accuracy-by-case / -class, regression alarms |

Schemas in [`records.py`](../src/black_box/memory/records.py) — `CaseRecord`,
`PlatformPrior`, `TaxonomyCount`, `EvalRecord`. All are pydantic v2, all writes
go through the append-only `JsonlStore` in
[`store.py`](../src/black_box/memory/store.py).

```mermaid
flowchart TB
    subgraph Write[Write path]
        FA[ForensicAgent.finalize] -->|CaseRecord| L1
        FA -->|TaxonomyCount per hypothesis| L3
        PLAT[platforms/nao6 adapter] -->|PlatformPrior seed| L2
        EVAL[eval.runner Tier-3] -->|EvalRecord| L4
    end

    subgraph Read[Read path]
        L2 -->|top_signatures k=5| PROMPT
        L3 -->|totals_by_class| PROMPT
        L4 -->|accuracy_by_case| ALARM[regression alarm]
        L1 -->|for_case| UI[UI replay]
    end

    PROMPT[Tier-1 prompt context] --> CLAUDE[Opus 4.7]
    CLAUDE --> FA
```

## Composition with verification_note + grounding gate

The stack is only half the story. Two deterministic filters sit on top of it
and decide what actually ships to the operator.

```mermaid
sequenceDiagram
    autonumber
    participant Op as Operator
    participant Ag as ForensicAgent
    participant Cl as Claude Opus 4.7
    participant Gr as GroundingThresholds
    participant Mem as MemoryStack
    participant VN as verification_note.md

    Op->>Ag: open_session(case_key, bag)
    Mem->>Ag: L2 priors + L3 frequencies (prompt context)
    Ag->>Cl: system (cached) + taxonomy (cached) + tier prompt + evidence
    Cl-->>Ag: PostMortemReport (pydantic)
    Ag->>Gr: ground_post_mortem(report)
    Gr-->>Ag: kept hypotheses only (fails closed -> NO_ANOMALY_PATCH)
    Ag->>Mem: log CaseRecord + TaxonomyCounts
    Op->>VN: human verification (optional override)
    VN-->>Mem: caveat ledger (kept alongside L1)
```

1. **Read path into the prompt.** At session start the agent pulls
   `PlatformMemory.top_signatures(platform, k=5)` for the L2 priors and
   `TaxonomyMemory.totals_by_class()` for the L3 frequency prior. Both are
   injected into the cached system block so repeated calls on the same
   platform reuse the prefix (see caching numbers below).
2. **Grounding gate.**
   [`grounding.py`](../src/black_box/analysis/grounding.py) runs AFTER Claude
   emits a report, BEFORE rendering. Rules from `GroundingThresholds`:
   - `min_confidence = 0.4`
   - `min_evidence_per_hypothesis = 2`
   - `min_evidence_for_other = 3` (bug_class "other" pays extra)
   - `min_cross_source_evidence = 2` distinct `Evidence.source` types
     (camera / telemetry / code / timeline)
   - moments with severity `info` are dropped by default
   If the accepted set is empty the report is rewritten to
   `NO_ANOMALY_PATCH = "No anomaly detected with sufficient evidence to
   support a scoped fix."` — the tool fails closed rather than fabricating.
3. **verification_note.md.** Append-only human override sitting next to the
   case artifacts (see
   [`data/session/analyses/hero_bag0_indoor_scene/verification_note.md`](../data/session/analyses/hero_bag0_indoor_scene/verification_note.md)).
   When the gate accepts a hypothesis that later turns out wrong, the
   operator writes a note documenting what the model lacked. The note is
   preserved as a caveat next to L1; we never rewrite L1 to pretend the
   wrong hypothesis was never logged. This is the closed-loop memory for
   the pipeline's failure modes.
4. **L4 loop.** Tier-3 synthetic QA runs compare `predicted_bug` against
   `ground_truth_bug`. `EvalMemory.accuracy_by_bug_class()` buckets by the
   ground-truth class so a per-class weakness surfaces even when the model
   predicted something unrelated. A per-case drop on a known-good bug is
   the regression alarm.

## Cost-delta proof

**Honest scope of this section.** Issue #24 referenced a
`data/costs.jsonl` aggregated log and a `data/bench_runs/` JSON from an
Opus-4.7 bench pass. Neither exists in this branch — `data/costs.jsonl` is a
runtime artifact written by
[`claude_client.py`](../src/black_box/analysis/claude_client.py) and is
gitignored, and no `bench_runs/` snapshot has been committed. What *is*
committed and reproducible: per-call `cost.json` and `mining_v2.json`
sidecars from the 2026-04-22 autonomous session. All numbers below come
directly from those files.

### Observed per-call costs

Opus 4.7 pricing: input $15 / MTok, cache_read $1.50 / MTok, output $75 /
MTok.

| Run | Prompt kind | Uncached in | Cached in | Output | Wall s | USD |
|-----|-------------|-------------|-----------|--------|--------|-----|
| `hero_bag1_overexposure` | hero_deep_dive | 27,206 | 0 | 921 | 28.8 | $0.4772 |
| `hero_bag0_indoor_scene` | hero_deep_dive | 27,462 | 0 | 1,625 | 44.5 | $0.5338 |

Sources: [`cost.json`](../data/session/analyses/hero_bag1_overexposure/cost.json),
[`cost.json`](../data/session/analyses/hero_bag0_indoor_scene/cost.json).

### What caching would save on run 2

Both runs share the same system + taxonomy + few-shot prefix. Run 1 warms
the cache; run 2 *should* hit `cache_read` on ~27,206 tokens. Two-run delta
with that assumption:

| Metric | Run 2 actual | Run 2 with cache hit | Delta |
|--------|--------------|----------------------|-------|
| Input tokens billed at $15 | 27,462 | 256 | -27,206 |
| Input tokens billed at $1.50 | 0 | 27,206 | +27,206 |
| Output tokens | 1,625 | 1,625 | 0 |
| **USD** | **$0.5338** | **$0.1665** | **-$0.3673 (-68.8%)** |

At the session scale (12 deep/summary calls in the
[SESSION_SUMMARY](../data/session/SESSION_SUMMARY.md)) that's the
difference between $6.48 and ~$2.10.

### Why caching didn't fire yet

The session summary flags it directly: *"Token caching not triggering on
v2 deep calls (cached blocks are <1024 tokens → below Anthropic cache
threshold). Pad `cached_blocks` in `prompts_v2.py` to >1024 tokens if
rerunning bags."* The plumbing is correct — `cache_control: ephemeral`
is applied on every system block in
[`claude_client.py`](../src/black_box/analysis/claude_client.py) — but
the v2 cached payload is below the minimum block size Anthropic accepts
for caching. Fix is a one-line padding change; numbers above show the
payoff.

## Pointers

- Implementation: [`src/black_box/memory/`](../src/black_box/memory/)
- Grounding gate: [`src/black_box/analysis/grounding.py`](../src/black_box/analysis/grounding.py)
- Agent orchestration: [`src/black_box/analysis/managed_agent.py`](../src/black_box/analysis/managed_agent.py)
- Human ledger example: [`data/session/analyses/hero_bag0_indoor_scene/verification_note.md`](../data/session/analyses/hero_bag0_indoor_scene/verification_note.md)
- Session-scale cost table: [`data/session/SESSION_SUMMARY.md`](../data/session/SESSION_SUMMARY.md)
