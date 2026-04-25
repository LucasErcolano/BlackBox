# Onboarding brief — Aayush

**Project:** Black Box — forensic copilot for robots
**Target:** top-3 at [Built with Opus 4.7](https://cerebralvalley.ai/e/built-with-4-7-hackathon) + *Best use of Managed Agents* ($5k)
**Deadline:** 2026-04-26 20:00 EST

## Core thesis

Heterogeneous artifact fusion (video + logs + controller code) → ranked hypotheses + code patch. No prior work ships this (closest: AURA telemetry-only, ROSA live ops, CoExp explanation-only). Framed as the **NTSB for robots** — post-mortem, not live monitoring.

Judging weights: Opus 4.7 Use 25% + Depth 20% + Impact 30% + Creativity 25%.

## Your scope

### 1. ~~NAO6 recordings — critical path~~ (descoped)

> **Status (2026-04-25):** real-hardware NAO6 captures did not land. NAO6 is now a **bonus adapter only** — synthetic fall fixture under `src/black_box/platforms/nao6/` proves the adapter shape generalizes, but the judged demo runs on rover (`sanfer_sanisidro`) and marine bags only. Do **not** invest more time on NAO6 hardware.

### 2. NAO6 ingestion adapter — keep as bonus, do not extend

Existing scaffold under `src/black_box/platforms/nao6/` (synthetic fall fixture, humanoid taxonomy → global closed set, controller snapshots) stays. It is referenced in the pitch with **one line only**: *"platform adapter shape already validated on NAO6"*. No NAO6 footage in the judged beat, no NAO6 hero asset in the landing UI.

### 3. Managed Agents — real implementation

Current repo has a skeleton with TODOs. Replace it. Requirements:

- persistent filesystem with bag / artifacts mounted
- `task_budget` in minutes
- mid-run steering via user messages (user injects *"focus on the left arm"* mid-analysis, agent adapts)
- long-horizon sessions (overnight batch runs as a demo beat)

Docs: https://docs.claude.com/en/docs/managed-agents/overview — read tonight.

### 4. Memory stack port from Kairos

Your 4-layer memory → forensic memory across bags. Value: Claude remembers failure patterns from previous analyses and self-improves prompts on new ones (*"this PID saturation pattern matches incident #3 from last week"*). The "nightly self-improving pipeline" framing applied to robotics forensics. Maps directly to the Managed Agents prize.

### 5. Grounding gate — from CS Navigator

Critical: Claude must refuse to hallucinate. If no anomaly is present, say so. Your grounding gate pattern is exactly what we need — port it to reject low-evidence hypotheses before they reach the report. Biggest credibility risk.

### 6. UI + PDF polish

FastAPI + HTMX already scaffolded. You own:

- diff viewer (side-by-side original vs patched)
- PDF report aesthetics (NTSB-style: exec summary, timeline, annotated frames, ranked hypotheses, patch proposal)
- streaming reasoning view during analysis

## What Lucas owns (don't duplicate)

- Car AV bags (5-camera ingestion, in progress)
- Synthetic failure injection for Tier 1 benchmark (bugs + telemetry + AI-generated video via Wan 2.2 / Nano Banana — runs on his GPU)
- Public dataset integration (REFLECT, FAA drone incidents — Tier 2)
- Demo video script, recording, editing
- Pitch delivery

## Shared

- Forensic prompt templates (A: post-mortem, B: scenario mining, C: synthetic QA)
- Eval harness across 3 tiers
- Patch-generation taxonomy — **scoped fixes only, no architectural rewrites**:
  1. PID saturation / wind-up
  2. Sensor timeout / stale data
  3. State-machine deadlock
  4. Bad gain tuning
  5. Missing null check in path planning
  6. Calibration drift between cameras
  7. Latency spike / sync issue

## Repo conventions

- Platform-specific code: `src/black_box/platforms/<name>/`
- Agent infra: `src/black_box/agents/`
- Shared analysis: `src/black_box/analysis/`
- Shared reporting: `src/black_box/reporting/`
- `CLAUDE.md` is strict — terse responses, no preamble, edits over rewrites
- Token discipline: prompt caching on system prompt + taxonomy, adaptive resolution (800×600 default, 3.75 MP only when justified), 5 cameras in a single prompt for cross-view reasoning

## Cadence

- Standup 10:00 ART / 08:00 EST
- Handoff sync 20:00 ART / 18:00 EST
- Async the rest. ~16 h daily overlap window.

## Day-by-day

| Day | Focus |
|-----|-------|
| 1–2 | ~~NAO6 recordings~~ (descoped). Read Opus 4.7 + Managed Agents docs. Fork repo, get local setup running. |
| 3 | ~~NAO6 ingestion adapter~~ — synthetic fixture only, scaffolded. Move to managed agent + memory stack port early. |
| 4 | Managed Agents real implementation + memory stack port. Joint prompt iteration with Lucas. |
| 5 | Grounding gate + UI polish + PDF templates final. Demo rehearsal on rover/marine bags. |
| 6 | Buffer + submit. |

## Watch-outs

- **Kairos was Gemini, this is Anthropic.** Not everything ports 1:1. Flag uncertain patterns on tomorrow's call — we'll review what's portable vs needs adaptation.
- **No scope creep.** Single judged platform (rover/marine, real bags) with depth beats two shallow. NAO6 stays a bonus adapter, not a demo beat.
- **Patches stay scoped.** Clamps, timeouts, null checks, gain adjustments — never rewrites. A dumb patch kills credibility of the whole tool.
