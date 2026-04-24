---
name: Feature request
about: Propose a new capability or enhancement for Black Box
title: "[FEAT] "
labels: enhancement
assignees: ''
---

## Motivation
What problem does this solve? Who is the user (operator, evaluator, judge, bench contributor)? Why now?

## Proposal
One paragraph of the happy-path behavior. Be concrete about inputs and outputs.

## Scope
- In scope:
- Out of scope:
- Affected modules (`ingestion/`, `analysis/`, `synthesis/`, `reporting/`, `ui/`, `eval/`, `memory/`, `platforms/`):

## Hackathon hard rules (must not violate)
Confirm this proposal respects the project's non-negotiable constraints from `CLAUDE.md`. Check each box.

- [ ] No ROS 2 runtime. `rosbags` lib only.
- [ ] No RAG, no vector DBs, no LangChain / AutoGen / LlamaIndex. Flat code.
- [ ] No training. Inference-only over Opus 4.7 (`claude-opus-4-7`).
- [ ] No ComfyUI / Wan 2.2 / Nano Banana runtime install. Synthesis emits text prompts only.
- [ ] No architectural rewrites in patches. Scoped fixes only (clamp / timeout / null check / gain adjust).
- [ ] Respects the closed 7-class bug taxonomy for benchmark scoring.

If any box is unchecked, explain why the exception is justified.

## Token / cost impact
Does this add Claude calls, frames, or cached prompt segments? Estimate delta in `data/costs.jsonl` per case.

## Alternatives considered
Brief. Why this over the simpler option.

## Acceptance criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Tests added or updated
- [ ] Docs / README updated if user-visible

## Additional context
Links to related issues, prior art, or research.
