# Submission checklist

**Deadline:** 2026-04-26 20:00 EST (Day 6 evening)

Submit before Day 6 18:00 EST to leave 2 h buffer for form glitches, re-upload, or last-minute edits.

## Final-form deliverables

- [ ] **Demo video** — 2:50 – 3:00, hosted on YouTube (unlisted OK, public preferred) or Loom. URL pastable into submission form.
- [x] **Public GitHub repo** — `black-box/` with:
  - [x] README with pitch, one-liner, quickstart, links to gist + onboarding + benchmark repo
  - [x] MIT LICENSE
  - [x] `CLAUDE.md` visible (judges read this)
  - [ ] Final commit on `master`, signed-off, no uncommitted state (last-mile check)
- [x] **Public benchmark repo** — `black-box-bench/` with MIT license, README, at least 3 cases (2 synthetic + 1 public-dataset) — 3 scoreable synthetic (`pid_saturation_01`, `sensor_timeout_01`, `bad_gain_01`) + `reflect_public_01` public-dataset skeleton wired to `src/black_box/eval/public_data.py`. Polished README + scoring table shipped 2026-04-22 (commit `0502cc8`).
- [x] **Gist build journal** — https://gist.github.com/LucasErcolano/851c5e976c6aa364f69c9e6875544061 (public, linked from README)
- [ ] **Hackathon submission form** filled:
  - [ ] Project name: `Black Box`
  - [ ] Tagline (one-liner, see PITCH.md)
  - [ ] Team members: Lucas Ercolano, Aayush
  - [ ] Video URL
  - [ ] Repo URL
  - [ ] Short description (90-second pitch, see PITCH.md)
  - [ ] Special-prize opt-ins: *Best use of Managed Agents* + *Most Creative Opus 4.7 Exploration* if offered as checkboxes

## Repo hygiene (before final commit)

- [ ] `.env` / secrets scrubbed, not in history (last-mile audit-grep)
- [x] `data/bags/`, `data/synthetic/`, `data/reports/`, `data/session/analyses/` gitignored (large artifacts out)
- [x] `data/costs.jsonl` included (evidence of token discipline)
- [x] `data/session/SESSION_SUMMARY.md` + `session_log.md` committed (audit trail)
- [x] `docs/` fully populated (ONBOARDING, PITCH, DEMO_SCRIPT, RISKS, SUBMISSION)
- [ ] README links verified (all external URLs resolve, all relative paths exist) (last-mile)
- [ ] Smoke tests pass on clean clone: `pip install -e . && pytest tests/` (tracked in #126)

## Judging criteria — self-check per axis

### Opus 4.7 Use (25%)
- [ ] Demo video explicitly says *"Claude Opus 4.7"* within first 60 seconds
- [ ] Hi-res vision used as central capability (not decoration)
- [x] Prompt caching visible in cost ledger (cached input > 0 on at least one call) — `data/costs.jsonl` line 1 `cached_input_tokens: 2058`; cost-accounting bug (negative uncached on cache hits) fixed 2026-04-22 (commit `daeb9f2`).
- [x] 5-camera cross-view reasoning in a single prompt — `visual_mining_v2` shipped (#87/#114); see README "Cross-modal hero mode" section. Demo screenshot tracked in #128.

### Depth (20%)
- [ ] Real bags used, not only synthetic
- [x] Benchmark repo with ground-truth cases — 3 synthetic with full `ground_truth.json` (bug_class, window_s, patch_target, evidence_hints).
- [x] Eval harness output table committed — `black-box-bench/results/sample_eval_2026-04-22.md` (6.00/6.00 on scoreable set).

### Impact (30%)
- [ ] NTSB framing in pitch
- [ ] Market-size claim backed by concrete user (*"AV labs process petabytes"*)
- [ ] Addressable use case beyond the demo (QA regression, training-data hygiene, post-incident review)

### Creativity (25%)
- [x] Grounding gate demonstrated (tool refuses to hallucinate on clean window) — `tests/test_grounding_gate.py` 5 tests green (empty moments valid, `interesting=False` propagates, system prompt forbids fabrication, cached block allows empty). Live fixture runner at `scripts/grounding_gate_live.py`. Full suite 36/36 on 2026-04-22.
- [x] Memory stack / self-improving pipeline documented and shown — `scripts/memory_loop_demo.py` (#76); 4-layer L1–L4 stack in `src/black_box/memory/`; pruning + compaction in `memory/maintenance.py` (#118).
- [ ] Synthetic failure injection framed as feature, not hack
- [x] Managed Agents used for real long-horizon work (overnight batch) — `scripts/overnight_batch.py` async resume + cost cap (#84); asciinema recording (#88) at `docs/recordings/offline_batch.cast`.

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
