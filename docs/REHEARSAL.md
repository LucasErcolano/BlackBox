# Rehearsal — timing, breath points, landmines

Rehearse the 90-second elevator until it's muscle memory. Then cut it to the 30-second version for pitch-judge gaps. Record yourself on phone; compare against the budget below.

## 90-second budget (target: 88–92 s spoken aloud)

Spoken cadence target: **155–165 words per minute**. The 90 s script in PITCH.md is ~245 words = ~90 s at 163 wpm. If you run long, you're narrating instead of asserting.

### Beat sheet (cumulative seconds)

| Beat | Line | Seconds | Cumulative |
|------|------|---------|------------|
| Hook | "Robots fail silently…" → "…never get reviewed." | 10 | 0:10 |
| Prior art | "Existing LLM tools…none of them emit a code fix." | 12 | 0:22 |
| What it does | "Black Box does. It reads the bag…single prompt to Opus 4.7." | 14 | 0:36 |
| Grounding gate | "Cross-view checking…We don't hallucinate." | 12 | 0:48 |
| Patch | "Then Claude writes a scoped patch…never architectural rewrites." | 10 | 0:58 |
| Output | "NTSB-style PDF + unified diff." | 4 | 1:02 |
| Managed Agents + memory | "Managed Agents run overnight…self-improves." | 12 | 1:14 |
| Eval | "Three tiers…MIT." | 10 | 1:24 |
| Close | "Two builders, six days, real data, shipped artifact." | 4 | 1:28 |

Leave ~2 s of silence at the end. Don't sprint to the edge.

## Breath points (hard pauses, 250–400 ms)

Mark these with a comma in the script; they land the assertion:

1. After "…never get reviewed."
2. After "…none of them emit a code fix."
3. After "…single prompt to Opus 4.7."
4. After "**We don't hallucinate.**" ← this is the longest pause, 500 ms
5. After "…never architectural rewrites."
6. After "…shipped artifact." → end

## Punch words (stress these, do not swallow)

- *silently*, *drift*, *faults*, *time*
- *none* (of them emit a code fix)
- *cross-view*, *single prompt*, *Opus 4.7*
- *grounding gate*, *reject*, *hallucinate*
- *scoped*, *never*
- *NTSB-style*, *unified diff*
- *two builders, six days*

## Landmine phrases — avoid

| Don't say | Say instead | Why |
|-----------|-------------|-----|
| "We believe this could…" | "It does…" | Hedging reads as low-confidence; hedge in Q&A, not pitch |
| "Kind of like…" | "Unlike X, which is Y, we…" | Comparatives work, analogies soften |
| "Basically…" | [delete] | Filler, burns budget, caveman rule |
| "AI-powered" | "Claude Opus 4.7" | Specificity wins; judges are from the AI lab |
| "Game-changer" | [delete] | Red flag for VC-pitch pastiche |
| "We spent X days on…" | "Six days, two builders, shipped." | Process talk drains impact |
| "As you can see…" | [point, don't narrate] | Video shows it; narrating it is redundant |

## Q&A prep — likely judge questions

Pre-answered, 2 sentences each:

**"How do you know it's not fabricating?"**
> Grounding gate. Regression test on known-clean windows asserts empty output. If the model hallucinates, CI breaks before the demo does.

**"What's the token spend on a 55 GB bag?"**
> Two-stage triage at 800×600 thumbnails on the summary pass, 3.75 MP only on flagged windows. Heaviest run to date was ~$1.16 with ~67k tokens. Ledger is in the repo.

**"Why closed-set bug taxonomy?"**
> It's what makes the patch output safe to apply. Open-set would invite architectural rewrites, which we refuse to emit.

**"What happens on a bug class you don't know?"**
> The tool reports the evidence and labels the hypothesis `unknown`. No patch emitted. Human takes the handoff.

**"GPS failure isn't in your taxonomy. How does this fit?"**
> The taxonomy describes failure *mode*, not *sensor*. A GPS failure partitions into one of three modes: `sensor_timeout` (stale / no fix / dropouts), `calibration_drift` (dual-antenna baseline, wheel-odom sync), or `missing_null_check` (downstream consumer not validating freshness or fix quality). The sanfer hero case is exactly this — rover antenna never resolves, NTRIP flapping, downstream bridge publishes a frozen latitude: three different bug classes, one broken GPS pipeline.

**"Your first analysis missed the camera. How do you know you aren't missing more?"**
> Two-pass discipline is in the system now. Pass 1 is telemetry-only and produces a timeline of suspect moments. Pass 2 extracts vision *anchored on those timestamps* — not uniform stride. A single AnyReader pass, so the 27-minute index build on the 364 GB cam-lidar bag is paid once. Session-folder discovery auto-bundles sibling bags (`2_sensors.bag`, `2_cam-lidar.bag`, `2_audio.wav`, `chrony/`) so an operator handing over a folder does not have to pick the right file.

**"Why Opus 4.7 specifically?"**
> Hi-res vision handles 3.75 MP without degradation. Prompt caching makes the two-stage pipeline affordable. Cross-view reasoning in a single prompt is the unlock.

**"How does this differ from AURA / ROSA?"**
> AURA is telemetry-only, live, no patch. ROSA is NASA-JPL's air-traffic-control layer. We're post-mortem, fuse camera + code + logs, and emit a scoped diff. Different axis.

**"Real data or synthetic?"**
> Both. Three synthetic cases with ground truth for eval; real AV bags (5-camera, multi-minute) for the hero findings. NAO6 humanoid recordings land on Day 4–5.

**"What's the business?"**
> AV labs and humanoid teams process petabytes of bags. Post-incident review is a staffing problem. If this saves one engineer-week per incident, it pays for itself on the first bag.

**"What if the model proposes a patch that breaks the robot?"**
> The patch is text, not a deployment. It lands next to a unified diff and an evidence trail in a PDF; a human reviews and applies it. Scope is restricted to clamps, timeouts, null checks, and gain adjustments. Architectural rewrites are refused at the prompt level.

**"Where does this fall over?"**
> Three places. One, bug classes outside the closed taxonomy return `unknown`; we don't guess. Two, extremely noisy real bags without telemetry handles degrade gracefully to scenario mining, not post-mortem. Three, cross-robot coordination failures are out of scope; single-platform only for this submission.

**"What's the top-five anticipated judge question you have not rehearsed?"**
> "What happens when you point this at your own crash." Honest answer: the pipeline is built on someone else's crash. We ran it dry on our own synthetic bugs and on the rtk_heading_break_01 real bag. The first real crash of a Black Box-instrumented robot is the first real adversarial test.

**"What ships after the hackathon?"**
> Three things: web UI for drag-drop bag review, humanoid platform adapters beyond NAO6, and the benchmark opened for third-party submissions. The forensic post-mortem core stays single-builder and MIT.

## Dry-run protocol

- **Day 5 morning**: Record 3 takes of the 90 s pitch on phone. Listen back, mark every filler word, rerun.
- **Day 5 afternoon**: Record with screen capture lined up. Sync demo beats to pitch beats (diff lands under "scoped patch"; PDF shows under "NTSB-style PDF").
- **Day 5 evening**: Final cut.
- **Day 6 morning**: Only re-record if a beat is broken. Otherwise polish audio levels, ship.

## If you flub a line during recording

- Don't restart from the top. Pause, breathe 2 s, pick up from the last clean beat boundary. Editing cuts silence cleanly; it does not cut stumbles cleanly.
- Save three full takes regardless of how you feel about them. The one that feels worst in the moment is often the best on playback.
