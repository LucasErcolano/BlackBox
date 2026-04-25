# Submission checklist

**Deadline:** 2026-04-26 20:00 EST (Day 6 evening)

Submit before Day 6 18:00 EST to leave 2 h buffer for form glitches, re-upload, or last-minute edits.

## Final-form deliverables

- [ ] **Demo video** — 2:50 – 3:00, hosted on YouTube (unlisted OK, public preferred) or Loom. URL pastable into submission form.
- [ ] **Public GitHub repo** — `black-box/` with:
  - [ ] README with pitch, one-liner, quickstart, links to gist + onboarding + benchmark repo
  - [ ] MIT LICENSE
  - [ ] `CLAUDE.md` visible (judges read this)
  - [ ] Final commit on `master`, signed-off, no uncommitted state
- [x] **Public benchmark repo** — `black-box-bench/` with MIT license, README, at least 3 cases (2 synthetic + 1 public-dataset) — 3 scoreable synthetic (`pid_saturation_01`, `sensor_timeout_01`, `bad_gain_01`) + `reflect_public_01` public-dataset skeleton wired to `src/black_box/eval/public_data.py`. Polished README + scoring table shipped 2026-04-22 (commit `0502cc8`).
- [ ] **Gist build journal** — https://gist.github.com/LucasErcolano/851c5e976c6aa364f69c9e6875544061 (public, linked from README)
- [ ] **Hackathon submission form** filled:
  - [ ] Project name: `Black Box`
  - [ ] Tagline (one-liner, see PITCH.md)
  - [ ] Team members: Lucas Ercolano, Aayush
  - [ ] Video URL
  - [ ] Repo URL
  - [ ] Short description (90-second pitch, see PITCH.md)
  - [ ] Special-prize opt-ins: *Best use of Managed Agents* + *Most Creative Opus 4.7 Exploration* if offered as checkboxes
- [ ] **Testimonial quote** — text + name + affiliation, in video and/or README
- [ ] **Flag-plant X thread** — posted by Day 4, pinned, linked from README "press"

## Repo hygiene (before final commit)

- [ ] `.env` / secrets scrubbed, not in history
- [ ] `data/bags/`, `data/synthetic/`, `data/reports/`, `data/session/analyses/` gitignored (large artifacts out)
- [ ] `data/costs.jsonl` included (evidence of token discipline)
- [ ] `data/session/SESSION_SUMMARY.md` + `session_log.md` committed (audit trail)
- [ ] `docs/` fully populated (ONBOARDING, PITCH, DEMO_SCRIPT, RISKS, SUBMISSION, TESTIMONIAL)
- [ ] README links verified (all external URLs resolve, all relative paths exist)
- [ ] Smoke tests pass on clean clone: `pip install -e . && pytest tests/`

## Judging criteria — self-check per axis

### Opus 4.7 Use (25%)
- [ ] Demo video explicitly says *"Claude Opus 4.7"* within first 60 seconds
- [ ] Hi-res vision used as central capability (not decoration)
- [x] Prompt caching visible in cost ledger (cached input > 0 on at least one call) — `data/costs.jsonl` line 1 `cached_input_tokens: 2058`; cost-accounting bug (negative uncached on cache hits) fixed 2026-04-22 (commit `daeb9f2`).
- [ ] 5-camera cross-view reasoning in a single prompt — screenshot in repo

### Depth (20%)
- [ ] Real bags used, not only synthetic
- [x] Benchmark repo with ground-truth cases — 3 synthetic with full `ground_truth.json` (bug_class, window_s, patch_target, evidence_hints).
- [x] Eval harness output table committed — `black-box-bench/results/sample_eval_2026-04-22.md` (6.00/6.00 on scoreable set).

### Impact (30%)
- [ ] NTSB framing in pitch
- [ ] Market-size claim backed by concrete user (*"AV labs process petabytes"*)
- [ ] Testimonial quote from qualified roboticist
- [ ] Addressable use case beyond the demo (QA regression, training-data hygiene, post-incident review)

### Creativity (25%)
- [x] Grounding gate demonstrated (tool refuses to hallucinate on clean window) — `tests/test_grounding_gate.py` 5 tests green (empty moments valid, `interesting=False` propagates, system prompt forbids fabrication, cached block allows empty). Live fixture runner at `scripts/grounding_gate_live.py`. Full suite 36/36 on 2026-04-22.
- [ ] Memory stack / self-improving pipeline documented and shown
- [ ] Synthetic failure injection framed as feature, not hack
- [ ] Managed Agents used for real long-horizon work (overnight batch)

## Bonus (shipped, not on critical path)

- [x] NAO6 (SoftBank Aldebaran) platform adapter — scaffolded under `src/black_box/platforms/nao6/` with synthetic fall fixture, humanoid taxonomy mapping to global closed set, controller snapshots. Proves adapter shape generalizes. Primary pitch is rover/marine; NAO6 lives in bonus section per `SCOPE_FREEZE.md`.

## Do NOT include in submission

- ❌ Mentions of alternative ideas considered before committing
- ❌ API key or any credentials
- ❌ Full raw bag sessions dumped wholesale. Bag owners cleared frames and short clips for demo / thread / PDF use (faces + plates unblurred OK); the one constraint is we do not re-upload an entire session's recording as a single bundle. Stills and brief clips: green light.
- ❌ Unreviewed hypotheses (pipeline output that we didn't verify)
- ❌ Internal handoff notes that weren't cleaned for external readers

## Post-submission

- [ ] Confirmation email captured, URL archived
- [ ] Social posts: X announcement, LinkedIn, any robotics community we have access to
- [ ] Rest.
