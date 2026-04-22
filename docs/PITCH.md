# Pitch

Reusable copy for submission form, README, X thread, demo intro.

## One-liner

> **Black Box is the NTSB for robots.** Feed it a ROS bag, get back a ranked root-cause report and a scoped code patch.

## Twitter / X (280 chars)

> When a robot crashes, the flight data recorder tells you *what* happened.
> Black Box tells you *why* — and hands you the diff.
>
> Forensic copilot for robots. Video + logs + code → ranked hypotheses + unified patch. Built with Claude Opus 4.7.

## 30-second elevator

Autonomous-vehicle labs process hundreds of bags per week. Nobody reads them end-to-end. When something crashes, root-cause analysis takes days of engineer time. Black Box is Opus 4.7 as the NTSB for robots: it ingests the bag, fuses five camera views with telemetry and controller source, returns ranked hypotheses with cross-camera evidence, and emits a scoped unified diff. Post-mortem in minutes, not days. Two platforms — autonomous car + NAO6 humanoid — real bags, no labels, open benchmark.

## 90-second elevator

Robots fail silently. Even when they don't crash outright, bags hide near-misses, perception drift, calibration faults that never get reviewed because nobody has time. Existing LLM tools for ROS — AURA, ROSA, CoExp — are either live-ops or explanation-only. None of them fuse heterogeneous artifacts, none of them emit a code fix.

Black Box does. It reads the bag with pure-Python `rosbags`, renders synchronized frames across up to five cameras at 3.75 MP, and passes them in a single prompt to Opus 4.7. Cross-view consistency checking that telemetry alone can't provide. Claude returns structured hypotheses with visual and temporal evidence. A grounding gate rejects low-evidence outputs — if nothing is anomalous, the tool says so. We don't hallucinate. Then Claude writes a scoped patch — clamps, timeouts, null checks, gain adjustments — never architectural rewrites. Output: NTSB-style PDF + unified diff.

Managed Agents run overnight batches with persistent filesystems and mid-run steering. Memory stack remembers failure patterns across bags and primes prompts on new ones — the pipeline self-improves. Three evaluation tiers: synthetic bugs with ground truth, public incidents from REFLECT and FAA drone reports, and our own autonomous-vehicle + humanoid footage. Open benchmark repo, MIT.

Two builders, six days, real data, shipped artifact.

## Positioning one-liners (for the video)

- **ROSA** (NASA-JPL) is *air traffic control* — operational, live.
- **AURA** is *telemetry-only, live, no patch.*
- **CoExp** stops at *explanation.*
- **Black Box** is the *NTSB* — arrives after the accident, fuses camera + code + logs + plots, returns the report **and** the patch.

## Hashtag / tagline options

- `The flight data recorder was invented in 1953. The NTSB for robots is invented today.`
- `Video + logs + code → ranked hypotheses + unified patch.`
- `Post-mortem in minutes, not days.`
- `More pixels ≠ more ground truth. Human verification is a layer, not polish.`

## Anti-pitches (things we don't say)

- We don't say *"we train models"* — we're inference-only over Opus 4.7.
- We don't say *"replaces engineers"* — human verifies hypotheses and applies patches.
- We don't say *"autonomous debugging"* — it's forensic, post-mortem, human-in-the-loop.
- We don't say *"multimodal"* — we say *"heterogeneous artifact fusion."*
