# Pitch

Reusable copy for submission form, README, X thread, demo intro.

## One-liner

> **Black Box is the NTSB for robots.** Feed it a ROS bag, get back the root cause — even when the operator's own hypothesis is wrong.

## Twitter / X (280 chars)

> When a robot crashes, the flight data recorder tells you *what* happened.
> Black Box tells you *why* — and it will disagree with you if you're wrong.
>
> Forensic copilot for robots. Telemetry + video + code → ranked hypotheses + scoped patch. Built with Claude Opus 4.7.

## 30-second elevator

Autonomous-vehicle operators all have theories about what went wrong in their bags. Most theories are wrong; nobody has time to prove it. Black Box is Opus 4.7 as the NTSB for robots: it ingests the bag, cross-checks telemetry against hardware-level flags, returns a ranked hypothesis, and disagrees with the operator when the data doesn't support their theory. On a real 1-hour ROS1 session the operator blamed a tunnel for GPS failure. The tool ran in 35 seconds for 22 cents, rejected the tunnel theory on numSV and fix-quality metrics, and located the real bug: a dead RTCM bridge between the dual antennas. Open benchmark, MIT.

## 90-second elevator

Robots fail silently, but nobody fails silently about robots. Every operator has a theory about what their bag is hiding. Existing LLM tools for ROS — AURA, ROSA, CoExp — either run live-ops or stop at explanation. None of them tell the operator they're wrong, and none of them emit a fix.

Black Box does. It reads the bag with pure-Python `rosbags`, extracts hardware-level telemetry — carrier-phase, fix type, satellite count, validity flags — and asks Opus 4.7 to verify or refute the operator's self-reported hypothesis against the data. A grounding gate rejects low-evidence outputs: on a clean bag the tool returns empty moments. We don't hallucinate, and we don't confirm.

Hero case: one hour of real autonomous-car driving, ROS1 Noetic, 375 gigabytes. Operator told us the GPS failed under a tunnel. Tool ran in 35 seconds. The tunnel did cause mild GNSS degradation (`numSV 29→16`, `h_acc 645mm→1294mm`), but the RTK-heading failure the operator blamed on it was already present 43 minutes pre-tunnel and drive-by-wire was never engaged — the tunnel could not have caused the reported behavior change. Real root cause: the moving-base antenna's RTCM correction stream to the rover was broken before the car left the lot. Claude returned a scoped patch — specific RTCM3 message IDs to enable, specific UART link to verify. Twenty-two cents per analysis.

Four evaluation cases in an open benchmark: three synthetic with injected bugs and ground-truth windows, one real bag with the operator's wrong hypothesis encoded as the anti-hypothesis the tool must reject. MIT. Use it to benchmark your own agent.

Six days, one builder on the hot path, real data, shipped artifact.

## Market & impact

AV programs generate **1–8 TB per vehicle per day** (Waymo disclosed ~2 TB/car/day; Mobileye ~11 PB/year across the fleet). A 50-car test fleet at the low end is ~50 TB/day — roughly 500 ROS sessions daily, each one a candidate post-mortem. Current state: a senior robotics engineer burns 4–8 hours chasing one bag to root cause, at a loaded cost of ~$150–$250/hr. That's **$600–$2000 per investigated incident**, and most incidents are never investigated at all — they sit in cold storage.

Black Box runs a full forensic pass for **$0.22 per session** at Opus 4.7 list price (measured, not modeled — see `data/costs.jsonl`). Three orders of magnitude cheaper than the human baseline, which inverts the economics: every session can be triaged, not just the ones that make it to a weekly review meeting. Addressable use cases beyond the hackathon demo: QA regression gating on CI, training-data hygiene (reject corrupted labels before they poison a model), post-incident review in AV/drone/humanoid programs, and fleet-wide drift detection.

Anchor user archetype: a robotics program manager at a Series B–C AV/drone startup with a 20–100 engineer team, 10+ test vehicles, and petabytes of archived bags that nobody has the budget to audit.

## Positioning one-liners (for the video)

- **ROSA** (NASA-JPL) is *air traffic control* — operational, live.
- **AURA** is *telemetry-only, live, no patch.*
- **CoExp** stops at *explanation.*
- **Black Box** is the *NTSB* — post-mortem, disagrees with the operator when the data says so, returns the report **and** the patch.

## Hashtag / tagline options

- `The flight data recorder was invented in 1953. The NTSB for robots is invented today.`
- `The operator said tunnel. The data said bad wiring. The tool sided with the data.`
- `Post-mortem in minutes. Twenty-two cents per bag.`
- `A forensic tool that agrees with you is a yes-man. Ours disagrees.`

## Anti-pitches (things we don't say)

- We don't say *"we train models"* — inference-only over Opus 4.7.
- We don't say *"replaces engineers"* — human applies the patch.
- We don't say *"autonomous debugging"* — forensic, post-mortem, human-in-the-loop.
- We don't say *"multimodal"* — we say *"heterogeneous artifact fusion."*
- We don't say *"two platforms"* — real NAO6 recordings didn't land. One platform, real data, one real counterfactual.
