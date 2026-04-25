# Risk register

Mitigate on sight. Update as risks fire or new ones emerge.

## P0 — kills the demo

| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|------|------------|--------|------------|-------|
| 1 | API budget overrun ($500 cap) | **low (2026-04-25: $39.37 / $500 spent)** | hard stop | Cost ledger per call. Cache-padding active. Plenty of headroom for demo + final bench passes. | Lucas |
| 2 | ~~NAO6 recordings not captured~~ | — | — | **RESOLVED** — NAO6 reframed as bonus adapter (synthetic fall fixture only). Pitch is single-platform (rover/marine) per `SCOPE_FREEZE.md`. Backup cut now the primary. | Aayush |
| 3 | ~~Grounding gate regresses~~ | — | — | **RESOLVED** — `tests/test_grounding_gate.py` + `test_grounding.py` green (22 tests). Live fixture runner at `scripts/grounding_gate_live.py`. Refutation path proven on sanfer hero. | Aayush |
| 4 | Hi-res re-analysis over-commits to wrong hypothesis (bag-0 case repeating) | med | lose trust, mislead patch output | Keep human-in-the-loop layer explicit. Confidence threshold on patch emission. Pre-loading prior flags in prompt is banned. | Shared |
| 5 | Patch output looks dumb on real bag | low-med | kills credibility of whole tool | Scoped taxonomy enforced (clamps, timeouts, null checks, gains, calibration, latency). Reject any patch that touches architecture. Manual sanity check before demo recording. | Lucas |
| 6 | Demo video record / edit slips | **HIGH (active 2026-04-25)** | no submission | All 10 blocks rendered. Master cut + upload pending — Day 6 work. Compose variants ready (`scripts/compose_demo_v4_xfade_exp.sh`). | Lucas |

## P1 — degrades the demo

| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|------|------------|--------|------------|-------|
| 7 | Bag 0 re-open cold (needs 11-min index rebuild) | high if rerun | 11 min wall time loss per attempt | Keep reader open across passes. Or run `rosbag reindex` once if we get ROS on a secondary machine. Documented in SESSION_SUMMARY. | Lucas |
| 8 | Wan 2.2 render variance on impact physics | med | synthetic demo looks fake | 3–5 iterations per scene, keep best. Cut clip before final impact frame to hide rebound artifacts. | Lucas |
| 9 | Max-plan rate limit during heavy Claude Code session | low-med | pauses build for ~hours | Run heavy loops during off-peak. Rate-limit reset is 5 h. Not blocking if planned. | Shared |
| 10 | ~~Handoff gaps between Lucas / Aayush~~ | — | — | **RESOLVED** — Aayush shipped 10+ merged PRs (client factory, grounding, role split, bench consolidation, overnight batch). Async-via-PR worked; active sync window closed. | Shared |
| 11 | ~~Testimonial quote not captured~~ | — | — | **DROPPED 2026-04-25** — out of scope for submission. Ship without. | — |
| 12 | ~~Benchmark repo not public by Day 3~~ | — | — | **RESOLVED** — `black-box-bench/` public with MIT license, README, scoring table. Reference run committed at `data/bench_runs/opus47_20260423T140758Z.json`. | Lucas |
| 13 | ~~LLM-agent-for-ROS convergence — another team ships similar~~ | — | — | **DROPPED 2026-04-25** — flag-plant X/LinkedIn thread skipped. Public repo at submission ships the same signal. | — |

## P2 — trackable, not urgent

| # | Risk | Mitigation |
|---|------|-----------|
| 14 | ~~Cost-log bug: `uncached_input_tokens: -656` in synthetic smoke entry~~ | **RESOLVED 2026-04-22** (commit `daeb9f2`). Root cause: Anthropic `usage.input_tokens` already excludes cache reads; client was subtracting `cache_read_input_tokens` twice. Retroactive fix applied to line 1 of `data/costs.jsonl` (uncached 1402, usd 0.086067). Test mock updated, 36/36 tests green. |
| 15 | HDD → SSD bag copy time | Copy in background while analyzing. Not critical path. |
| 16 | FastAPI UI polish incomplete | Ship minimal. Demo is the recording, not the UI tour. |
| 17 | Prior hackathon prior-art scan missed LessWrong alignment coverage (corrigibility, approval-directed agents) | Cite Christiano approval-directed + Orseau/Armstrong interruptibility if safety frame gets questioned in judging Q&A. |

## When a P0 fires

1. Log in `data/session/session_log.md` with timestamp and observed symptom.
2. Ping partner in handoff sync channel.
3. Decide: mitigate, accept + document, or invoke fallback (see DEMO_SCRIPT backup cut).
4. Do **not** silently keep going on a broken assumption.

## Stop-loss triggers

- **$400 API spend** → freeze new analyses. Demo-only budget from here.
- **End of Day 6 09:00 EST, no video draft** → abandon polish, ship roughest viable cut. Submission > polish.
