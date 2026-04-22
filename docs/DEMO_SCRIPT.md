# Demo video — beat sheet

**Target length:** 2:50 – 3:00
**Format:** screen recording + voice-over + 1–2 webcam inserts (Lucas on camera for personal-narrative beats)
**Climax:** the unified diff, not the PDF

## Timing

| Time | Beat | Shot | VO |
|------|------|------|-----|
| 0:00 – 0:15 | **Hook** | Webcam Lucas in front of the autonomous car | *"This is my autonomous car. Last week it did something weird. Nobody noticed."* |
| 0:15 – 0:30 | **Problem** | Bag file icon, terminal showing 206 GB | *"AV labs process hundreds of bags per week. Nobody reads them end-to-end. What do they miss?"* |
| 0:30 – 0:45 | **The setup** | Upload UI, 5-camera preview grid | *"I give Black Box a bag it has never seen. No labels. Five cameras. No telemetry."* |
| 0:45 – 1:15 | **Analysis live** | Streaming reasoning view (HTMX), Claude working through the window | *"Opus 4.7 sees all five views at once. It's looking for moments a human would want to review — not crashes it was told about."* |
| 1:15 – 1:40 | **First moment** | Report opens to moment #1, front-cam overexposure frame | *"Here. Both front cameras blown out for 4.5 seconds at scene entry. Auto-exposure convergence failure."* |
| 1:40 – 2:00 | **Second moment** | Bag 0 indoor-scene finding with annotation | *"Here. The vehicle is parked at the lab entrance. Rear and left cameras see into open doorways. The bag's tail is not driving footage. Training on it would poison a road-scene model."* |
| 2:00 – 2:20 | **The money shot** | Split screen: original controller code vs unified diff patching AE init | *"This is the bug. This is the fix. It's a diff, not a redesign."* |
| 2:20 – 2:35 | **The second platform** | Cut to NAO6 fall, same UI, same output | *"Same tool. Different robot. Humanoid fall, same three artifacts, same ranked hypothesis."* |
| 2:35 – 2:50 | **Punchline + credibility** | Testimonial quote card from roboticist contact + benchmark repo URL | *"This ran while I slept. Benchmark open on GitHub. Two builders, six days."* |
| 2:50 – 3:00 | **Outro** | Logo, hackathon tag, team credit | silent |

## Non-negotiables

1. **Diff as climax.** Not the PDF. The PDF is the artifact; the diff is the *payoff*. Everything else stops at explanation — we don't.
2. **Grounding gate visible.** At least once show Claude saying *"nothing anomalous detected"* on a clean window. Proves we don't hallucinate. Inoculates credibility early.
3. **Real data, on camera.** Lucas in front of the actual car for the hook. Not a stock shot. Winner pattern is *"built from what I know"* — show you know it.
4. **NAO6 cameo.** Second platform in last 15 seconds. Proves tool is not one-hardware bespoke.
5. **Testimonial quote.** From a roboticist in the network (ex-NASA or ex-NVIDIA preferred). Capture by Day 5 — not Day 6.
6. **URL visible.** `github.com/.../black-box-bench` on screen at punchline. Judges will look.

## What we do NOT show

- Synthesis pipeline (Wan 2.2 / Nano Banana). It's backend QA, not product pitch.
- Token cost dashboard. Insider detail, off-pitch for 3-min video.
- Any hypothesis we couldn't verify. Honesty beats drama.
- The word *"multimodal."* Say *"heterogeneous artifact fusion"* or *"video + logs + code."*

## Required assets by Day 5

- [ ] 1 clean recording of UI analysis on bag 1 (overexposure moment) — 800×600 frames OK
- [ ] 1 recording of analysis on bag 0 end window (indoor-scene finding)
- [ ] 1 recording of NAO6 fall analysis (3 artifacts fused)
- [ ] 1 unified-diff screenshot (real code, real fix) — readable at 1080p
- [ ] 1 testimonial quote, text + name + affiliation
- [ ] 1 webcam clip of Lucas at the car (15 s)
- [ ] Benchmark repo public with README + at least 2 cases

## Backup cut

If NAO6 recordings slip, replace beat 2:20 – 2:35 with *"batch run overnight over 20 bags"* — Managed Agents angle. Still captures the depth story, keeps duo narrative intact.

## Day-5 rehearsal

One full voice-over dry run before recording. Time it. If over 3:05, cut the second moment (keep overexposure as sole moment). Under no circumstances ship a 4-minute video.
