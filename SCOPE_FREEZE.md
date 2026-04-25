# Scope freeze — Black Box (hackathon deadline 2026-04-26)

Frozen at commit time of the branch that introduced this file. No new features between here and submission. Bugfixes, tightening, and demo polish only.

## Hero case (critical path)

**`sanfer_sanisidro` RTK-heading finding.** Real operator recording. Operator submitted the bag tagged "tunnel caused the anomaly." Black Box's grounding gate promoted a ranked **refutation** hypothesis: RTK `carr_soln = none` was already present 43 minutes pre-tunnel, drive-by-wire never engaged, so the tunnel could not have caused the reported behavior change. This is the one demo beat that has to work end-to-end.

Bench mirror: `black-box-bench/cases/rtk_heading_break_01/` (telemetry-only reproduction).
Demo proof: `demo_assets/grounding_gate/README.md`.

## In scope — on the demo critical path

- **Ingestion** — `rosbags`-based ROS1+ROS2 reader, session discovery, platform-agnostic manifest, telemetry-anchored frame sampling.
- **Analysis** — `ClaudeClient` with prompt caching, three prompt templates (post-mortem / scenario-mining / synthetic-QA), pydantic schemas, `ForensicAgent` over the Managed Agents SDK.
- **Grounding gate** — deterministic post-filter with two visible exits: refutation (sanfer hero case) and silence (`nothing anomalous detected`). Rules in `src/black_box/analysis/grounding.py`.
- **Reporting** — markdown / PDF case report + unified-diff HTML side-by-side.
- **Memory stack** — append-only L1–L4 JSONL substrate (case / platform / taxonomy / eval). Self-improvement **loop** is explicitly deferred and labelled as such in the README.
- **Benchmark** — `black-box-bench/cases/` + `scripts/run_opus_bench.py`. Committed run artifact: `data/bench_runs/opus47_20260423T140758Z.json` (2 of 3 non-skeleton cases match on Opus 4.7 at $0.46 total).
- **UI** — FastAPI + HTMX upload → streaming reasoning → side-by-side diff, served against either the streaming stub or `BLACKBOX_REAL_PIPELINE=1`.
- **Hero-case reproduction** — `scripts/run_session.py` (end-to-end) and `scripts/run_rtk_heading_case.py` (telemetry-only one-shot).

## Out of scope — frozen, not built, not promised

- **Self-improving memory loop** (L2 priors priming the system prompt, L3 tie-breaking, L4 regression alarms). Substrate ships; loop does not. README calls this out explicitly.
- **Tier-1 / Tier-2 batch runners.** Single-case paths work; batched CLI is skeleton only.
- **Public-data downloader path** (`eval.public_data`). Stub only.
- ~~**Real rosbag upload path in the deployed UI**~~ — promoted to canonical via #75. Live is the default worker whenever `ANTHROPIC_API_KEY` is set; the streaming stub is now opt-in via `?source=stub` for the deterministic demo cut.
- **Video synthesis execution** (Wan 2.2, Nano Banana Pro, ComfyUI). We emit text prompts only. Operator runs video tools on their own GPU.
- **ROS 2 runtime.** Never installed. `rosbags` library only.
- **LangChain / AutoGen / LlamaIndex / vector DBs / RAG.** None, ever.
- **Model downgrades.** Always `claude-opus-4-7` for vision + reasoning.
- **Architectural patch shapes.** Patches are scoped primitives: clamp / timeout / null-check / gain-adjust. No rewrites.
- **Additional bug classes** beyond the closed 7 + `other`.

## Bonus (shipped, not on the critical path)

- **NAO6 (SoftBank Aldebaran) platform adapter.** Scaffolded under `src/black_box/platforms/nao6/` with a synthetic fall fixture, a humanoid taxonomy mapping to the global closed set, and controller snapshots. Presence proves the adapter shape generalizes; the primary README pitch is rover / marine. NAO6 lives in a dedicated "bonus" section, not in the hero beat.
- **Synthesis module** — injected-bug recordings + text video prompts. Useful for Tier-3 eval; not in the hero beat.

## Freeze rules until submission

1. No new demo assets that don't already exist in-tree.
2. No new prompt templates.
3. No new bug classes.
4. No silent model swaps.
5. Every benchmark claim must link to a committed run artifact under `data/bench_runs/`.
6. Every asset mentioned in README or the video script must carry a `live | replay | sample` tag.

If a change doesn't support the sanfer hero case or the honesty-tag discipline, it does not ship before 2026-04-26.
