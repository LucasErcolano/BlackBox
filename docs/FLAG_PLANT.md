# Flag-plant X thread — copy-paste ready

**Goal:** Public claim on "LLM forensic copilot for robots." Kills RISKS #13 (another team ships similar). Drives benchmark repo traffic before Day 6.

**When to post:** Day 3 or Day 4 morning (ART). Not later. The thread needs 24 to 48 h to pick up replies before submission.

**Assets required before posting:**
- [ ] Plot: rover carrier-phase vs moving-base carrier-phase over 1 h. File: `docs/assets/rtk_carrier_contrast.png`. Used in tweet 1.
- [ ] Plot: REL_POS_VALID flag (flat zero for 1 h). File: `docs/assets/rel_pos_valid.png`. Used in tweet 3.
- [ ] Screenshot: patch proposal from `runs/sample/rtk_heading_break_01.json` (RTCM3 msg IDs plus UART check). File: `docs/assets/rtk_patch.png`. Used in tweet 4.
- [ ] Optional: real frame from sanfer_sanisidro cam-lidar bag overlaid with the operator's quote. Cleared for public use. Faces and plates unblurred OK. Strengthens tweet 1's hook.
- [ ] Public URLs: repo, benchmark repo, gist.

**Rights note:** the owners of the car-AV bags cleared frames and short clips for public use on this thread, in the demo video, and in the PDF report. Faces and license plates may stay unblurred. Do NOT upload a full raw session dump in one go (not cleared); stills and brief clips are fine.

**Pinning:** pin the thread after posting. Keep it pinned through submission.

---

## Thread (7 tweets, ~1400 chars total)

### 1/ — Hook
> The operator told me the GPS failed when the car went under a tunnel.
>
> I gave the bag to the tool I built. It said he was wrong.
>
> **Black Box** — forensic copilot for robots. Claude Opus 4.7.
>
> [plot: rover vs moving-base carrier-phase over 1 h]

### 2/ — The counterfactual
> Real ROS1 bag. One hour. No labels.
>
> Operator's theory: a tunnel knocked out GPS.
>
> What the rover receiver actually did: held a 3D fix, 29 satellites median, no dropouts, sub-metre hAcc for the entire session. A tunnel would collapse numSV. It never does.

### 3/ — The real finding
> Moving-base antenna: carrier-phase FLOAT 64%, FIXED 31%. Healthy.
>
> Rover antenna: carrier-phase NONE 100%. Never locks. Once. In 3,626 seconds.
>
> REL_POS_VALID flag: flat zero for the whole bag.
>
> The dual-antenna heading pipeline was broken before the car left the lot.
>
> [plot: REL_POS_VALID over 1 h]

### 4/ — The fix
> Black Box doesn't stop at diagnosis. It prescribes.
>
> Patch: enable RTCM3 msgs 1077, 1087, 1097, 1127, 4072.0, 4072.1 on the moving-base to rover link; verify the UART baud match; the success criterion is DIFF_SOLN at 100% (currently 15%) and REL_POS_VALID above 95%.
>
> Scoped. No architectural rewrites.
>
> [screenshot: patch proposal]

### 5/ — The grounding gate
> A forensic tool that agrees with the human is a yes-man.
>
> A forensic tool that invents bugs on clean data is worse.
>
> Black Box does neither. Clean window → empty moments. Operator wrong → it says so.
>
> Cost for this whole analysis: $0.22.

### 6/ — Benchmark
> **black-box-bench** — 4 scoreable cases.
>
> 3 synthetic (PID wind-up, sensor timeout, bad gain) with ground-truth windows and source diffs.
>
> 1 real 1 h bag with the operator's wrong hypothesis encoded as the anti-hypothesis the pipeline must reject.
>
> MIT. Benchmark your own robot-forensic agent.
>
> https://github.com/LucasErcolano/BlackBox/tree/master/black-box-bench

### 7/ — Links and CTA
> Repo: https://github.com/LucasErcolano/BlackBox
> Benchmark: https://github.com/LucasErcolano/BlackBox/tree/master/black-box-bench
> Build journal: https://gist.github.com/LucasErcolano/851c5e976c6aa364f69c9e6875544061
>
> If you run a robot fleet and you have a bag where the "obvious" cause turned out to be wrong, I want to hear about it. DM open.

---

## Reply strategy

- **Engineers asking "does it handle X bug class":** point to the closed taxonomy in CLAUDE.md. Acknowledge what's out of scope (architectural bugs, multi-robot coordination failures).
- **Skeptics on LLM fabrication:** link the grounding-gate test. Do not argue; show.
- **Compliments without questions:** thank plus one-line CTA to the benchmark repo. Don't burn the hook.
- **"This is like AURA / ROSA":** acknowledge prior art. Differentiator: scoped patch emission plus cross-camera single-prompt reasoning plus grounding gate. Don't pick fights.

## Do NOT post

- Token spend numbers (judges haven't seen the ledger yet, hold for the demo video).
- Testimonial quote (hold for the demo video reveal).
- Internal Aayush split or who-did-what (handoff detail, irrelevant to public).
- Any mention of alternative ideas considered.
- NAO6 footage before it exists. If the backup cut fires, rewrite tweet 6 to car-only.

## LinkedIn adaptation

Same content, one long post (not a thread). Lead with tweet 1, merge 2 and 3 into a paragraph, keep 4 as a standalone callout quote, close with 5 through 7. Tag Anthropic and Cerebral Valley.
