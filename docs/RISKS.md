# Risk register

Mitigate on sight. Update as risks fire or new ones emerge.

## P0 — kills the demo

| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|------|------------|--------|------------|-------|
| 1 | API budget overrun ($500 cap) | med | hard stop | Cost ledger per call. Hard stop alert at $350. Cache-padding fix in `prompts_v2.py` (>1024 tok) to enable caching on deep calls. Subscription covers dev loop, not product runtime. | Lucas |
| 2 | NAO6 recordings not captured | med-high | demo loses second platform | Start **tonight.** 3–5 falls, 3 artifacts each. Don't batch Day 5. Backup cut in DEMO_SCRIPT drops NAO6 beat if it slips. | Aayush |
| 3 | Grounding gate regresses — tool hallucinates on clean window | med | kills credibility, Anthropic judges see it | Integration test: run on 1 known-clean window, assert `no anomalies detected`. Ship in eval harness Tier 2. | Aayush |
| 4 | Hi-res re-analysis over-commits to wrong hypothesis (bag-0 case repeating) | med | lose trust, mislead patch output | Keep human-in-the-loop layer explicit. Confidence threshold on patch emission. Pre-loading prior flags in prompt is banned. | Shared |
| 5 | Patch output looks dumb on real bag | low-med | kills credibility of whole tool | Scoped taxonomy enforced (clamps, timeouts, null checks, gains, calibration, latency). Reject any patch that touches architecture. Manual sanity check before demo recording. | Lucas |
| 6 | Demo video record / edit slips | med | no submission | Dry-run Day 5 morning. Final cut Day 5 evening. Day 6 buffer for re-record, not first take. | Lucas |

## P1 — degrades the demo

| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|------|------------|--------|------------|-------|
| 7 | Bag 0 re-open cold (needs 11-min index rebuild) | high if rerun | 11 min wall time loss per attempt | Keep reader open across passes. Or run `rosbag reindex` once if we get ROS on a secondary machine. Documented in SESSION_SUMMARY. | Lucas |
| 8 | Wan 2.2 render variance on impact physics | med | synthetic demo looks fake | 3–5 iterations per scene, keep best. Cut clip before final impact frame to hide rebound artifacts. | Lucas |
| 9 | Max-plan rate limit during heavy Claude Code session | low-med | pauses build for ~hours | Run heavy loops during off-peak. Rate-limit reset is 5 h. Not blocking if planned. | Shared |
| 10 | Handoff gaps between Lucas / Aayush (16 h overlap window) | med | decisions diverge | Standup 10:00 ART / 08:00 EST. Handoff sync 20:00 ART / 18:00 EST. Decisions logged in session_log.md. | Shared |
| 11 | Testimonial quote not captured | med | loses Impact (30%) boost | Ask contacts **Day 4 latest.** Pre-drafted script in TESTIMONIAL.md. Follow up same day. | Lucas |
| 12 | Benchmark repo not public by Day 3 | med | loses "tangible artifact" + flag-plant urgency | Push skeleton Day 2 with 2 cases + README. Fill in more cases as they come. | Lucas |
| 13 | LLM-agent-for-ROS convergence — another team ships similar | low-med | novelty erodes | Public repo + X thread Day 3–4 with first functional clip. Plant flag. | Lucas |

## P2 — trackable, not urgent

| # | Risk | Mitigation |
|---|------|-----------|
| 14 | Cost-log bug: `uncached_input_tokens: -656` in synthetic smoke entry | Cosmetic. Fix if time. |
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
- **End of Day 4, no testimonial** → ship without it. Don't delay submission.
- **End of Day 5, no NAO6 footage** → invoke DEMO_SCRIPT backup cut. Ship car-only + batch-run narrative.
- **End of Day 6 09:00 EST, no video draft** → abandon polish, ship roughest viable cut. Submission > polish.
