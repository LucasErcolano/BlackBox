# Flag-plant X thread — copy-paste ready

**Goal:** Public claim on "LLM forensic copilot for robots." Kills RISKS #13 (another team ships similar). Drives benchmark repo traffic before Day 6.

**When to post:** Day 3 or Day 4 morning (ART). Not later — thread needs 24–48 h to pick up replies before submission.

**Assets required before posting:**
- [x] Bag-1 overexposure GIF (4-frame loop, saturated → mid → recovered → mid). File: `docs/assets/bag1_ae_failure.gif`. Used in tweet 1.
- [x] Screenshot of unified diff from `pid_saturation_01` (GitHub-style dark theme). File: `docs/assets/pid_saturation_diff.png`. Used in tweet 3.
- [ ] Public URLs: repo, benchmark repo, gist.

**Dropped**: PDF report page. Synthetic case's telemetry plots would mislead viewers into thinking the real hero bag (bag-1 AE failure, image-only) was analyzed with the same telemetry surface. Report asset re-added only if a vision-only PDF template exists for bag-1.

**Pinning:** Pin thread after posting. Keep pinned through submission.

---

## Thread (7 tweets, ~1400 chars total)

### 1/ — Hook + clip
> When a robot crashes, the flight data recorder tells you *what* happened.
>
> I built **Black Box** — a forensic copilot that tells you *why*, and hands you the diff.
>
> Powered by Claude Opus 4.7.
>
> [video: bag-1 overexposure clip]

### 2/ — What it does
> Feed it a ROS bag. Out comes:
> • ranked root-cause hypotheses (closed-set taxonomy, no hand-waving)
> • cross-camera evidence (5 cameras reasoned in one prompt)
> • a scoped code patch — clamp, timeout, null check, gain — never an architectural rewrite

### 3/ — The hero finding
> Real AV bag, 55 GB, 5 cameras.
>
> Black Box found a 4.5 s auto-exposure convergence failure on the front-left camera that a human review missed on first pass.
>
> Patch: widen AE range + add a glare-detect fallback.
>
> [screenshot: unified diff]

### 4/ — The grounding gate
> An LLM that fabricates a bug on a clean bag is worse than useless.
>
> Black Box runs a gate: on known-clean windows, it MUST return "no anomalies detected." Regression-tested in CI.
>
> Conservative by default. If it flags something, it's because something is there.

### 5/ — Benchmark
> Shipping a public benchmark alongside: **black-box-bench**.
>
> 3 synthetic cases with injected bugs, ground-truth windows, source diffs, scoring harness. MIT. Use it to evaluate your own robot-forensic agent.
>
> [link: github.com/.../black-box-bench]

### 6/ — Built for hackathon, but…
> Built during the Cerebral Valley × Anthropic "Built with Opus 4.7" hackathon. 6 days, two builders, two platforms (5-camera AV + NAO6 humanoid).
>
> But the actual use case — post-incident review at AV / humanoid labs — is a petabyte problem, not a week-long one.

### 7/ — Links + CTA
> Repo: [link]
> Benchmark: [link]
> Build journal (decisions, failures, findings): [gist link]
>
> If you run a robot fleet and this would've saved you a week of oncall: DM open. If you think it wouldn't: reply and tell me why.

---

## Reply strategy

- **Engineers asking "does it handle X bug class":** Point to the closed taxonomy in CLAUDE.md. Acknowledge what's out of scope (architectural bugs, multi-robot coordination failures).
- **Skeptics on LLM fabrication:** Link the grounding-gate test. Do not argue; show.
- **Compliments without questions:** Thank + one-line CTA to the benchmark repo. Don't burn the hook.
- **"This is like AURA / ROSA":** Acknowledge prior art. Differentiator: scoped patch emission + cross-camera single-prompt reasoning + grounding gate. Don't pick fights.

## Do NOT post

- Token spend numbers (judges haven't seen the ledger yet — hold for demo video).
- Testimonial quote (hold for demo video reveal).
- Internal Aayush split or who-did-what (handoff detail, irrelevant to public).
- Any mention of alternative ideas considered.
- NAO6 footage before it exists. If backup cut fires, rewrite tweet 6 to car-only.

## LinkedIn adaptation

Same content, one long post (not a thread). Lead with tweet 1, merge 2–3 into a paragraph, keep 4 as a standalone callout quote, close with 5–7. Tag Anthropic + Cerebral Valley.
