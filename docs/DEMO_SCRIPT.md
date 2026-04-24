# Demo video — beat sheet

**Target length:** 2:50 to 3:00 (hard cap 3:00)
**Format:** screen recording + voice-over + 1 to 2 webcam inserts (Lucas on camera for personal-narrative beats)
**Climax:** the unified diff, not the PDF

## Timing

Every beat has an explicit in-point and duration. Cumulative end-time stays at or under 3:00.

| In | Out | Dur | Beat | Shot | VO |
|----|-----|-----|------|------|-----|
| 00:00 | 00:15 | 0:15 | **Hook** | Webcam Lucas in front of the autonomous car | *"Last week the operator told me the GPS failed when the car went under a tunnel. I gave the bag to Black Box. It said he was wrong."* |
| 00:15 | 00:30 | 0:15 | **Problem** | Bag file icon, terminal showing 375 GB | *"AV labs process hundreds of bags per week. Nobody reads them end-to-end. Everybody has a theory. Most theories are wrong."* |
| 00:30 | 00:45 | 0:15 | **The setup** | Upload UI, topic list for `sanfer_sanisidro` session | *"One hour of real driving. ROS1 bag. No labels. The operator gave me one sentence of prior: 'check the tunnel.'"* |
| 00:45 | 01:15 | 0:30 | **Analysis live** | Streaming reasoning view, Claude working through carrier-phase timeline | *"Opus 4.7 reads the telemetry. Carrier-phase, fix quality, relative-position validity. It's checking whether the operator's theory survives the data."* |
| 01:15 | 01:45 | 0:30 | **The counterfactual** | Side-by-side: operator's quote on the left, Claude's refutation card on the right | *"Here. The rover receiver keeps a 3D fix with 29 satellites the entire session. No dropouts anywhere. If a tunnel killed the GPS, numSV would collapse. It never does. The operator is wrong."* |
| 01:45 | 02:05 | 0:20 | **The real finding** | Two plots: moving-base carrier-phase (healthy) vs rover carrier-phase (flat zero). REL_POS_VALID flat zero. | *"Moving-base antenna: clean RTK, float and fixed 94% of the bag. Rover antenna: never locks. Once. The whole hour. REL_POS_VALID never sets. The dual-antenna heading pipeline is broken, and it was broken before the car left the lot."* |
| 02:05 | 02:25 | 0:20 | **The money shot** | Report page opens to patch proposal: enable RTCM3 msgs 1077/1087/1097/1127/4072.0/4072.1, verify UART link | *"This is the fix. Specific message IDs. Specific checkpoint. It's a config diff, not a redesign."* |
| 02:25 | 02:45 | 0:20 | **Grounding** | Clean synthetic window runs through the same pipeline; Claude returns empty moments | *"Same tool, clean bag. It says nothing anomalous. It will not fabricate a bug. That's the rule."* |
| 02:45 | 02:55 | 0:10 | **Punchline + credibility** | Benchmark repo URL + cost ledger ($0.22 per run) | *"One hour of real driving, twenty-two cents. Benchmark open on GitHub."* |
| 02:55 | 03:00 | 0:05 | **Outro** | Logo, hackathon tag | silent |

**Cumulative runtime check:** 15 + 15 + 15 + 30 + 30 + 20 + 20 + 20 + 10 + 5 = 180 s = 3:00 exactly.

## Non-negotiables

1. **Disagreement as climax.** The tool rejecting the operator's own hypothesis is the money shot. Diff is the follow-up payoff. Everything else stops at explanation — we don't.
2. **Grounding gate visible.** Show the clean-bag pass where Claude returns empty moments. Proves we don't hallucinate. Inoculates credibility before the counterfactual.
3. **Real data, on camera.** Lucas in front of the actual car for the hook. Not a stock shot. Real session. Real operator quote.
4. **Cost visible.** $0.22 per bag on screen at punchline. Judges care about token discipline.
5. **URL visible.** `github.com/.../black-box-bench` on screen at punchline. Judges will look.

## What we do NOT show

- Synthesis pipeline (Wan 2.2 / Nano Banana). Backend QA, not product pitch.
- NAO6 beat. Real humanoid recordings not captured in time. Single-platform cut.
- Any hypothesis we couldn't verify. Honesty beats drama.
- The word *"multimodal."* Say *"heterogeneous artifact fusion"* or *"video + logs + code."*

## Required assets by Day 5

- [ ] 1 recording of the RTK counterfactual pass on `sanfer_sanisidro` — streaming reasoning visible, operator-quote overlay on first card
- [ ] 2 matplotlib plots rendered from `rtk_heading_break_01/telemetry.npz`: moving-base vs rover carrier-phase over time; REL_POS_VALID flag over time
- [ ] 1 patch-proposal screenshot (RTCM3 message IDs + UART check) — readable at 1080p
- [ ] 1 clean-window pass showing empty moments (grounding gate visible)
- [ ] 1 webcam clip of Lucas at the car with operator-quote voice-over (15 s)
- [ ] 3–5 real frames/short clips from the sanfer_sanisidro cam-lidar bag for the hook and counterfactual beat. Owners cleared public use, faces + plates unblurred OK. Do not ship the full session dump.
- [ ] Benchmark repo public with README + 4 scoreable cases incl. `rtk_heading_break_01`

## Backup cut

If any beat slips, collapse 1:45 – 2:05 and 2:05 – 2:25 into a single 30 s beat showing the plot + patch in one panel. Total comes in at 2:45 with room for the outro. Keep the counterfactual. Cut the grounding-gate beat first — its content is in the PITCH one-liner and the benchmark README.

## Day-5 rehearsal

One full voice-over dry run before recording. Time it. If over 3:05, cut the grounding-gate beat (keep the counterfactual + patch). Under no circumstances ship a 4-minute video.
