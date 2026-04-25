# Claims & evidence

Every strong claim in the README, pitch, and demo gets one row here, paired with the strongest committed evidence (file path, committed run, screenshot, or test). Judges should be able to verify each line in under a minute.

| # | Claim | Evidence |
|---|-------|----------|
| 1 | Live path is the canonical UI worker | `src/black_box/ui/app.py::_real_pipeline_enabled` defaults true when `ANTHROPIC_API_KEY` is set; stub is opt-in via `?source=stub`. PR #108. |
| 2 | Memory improves run-2 over run-1 (visible) | `scripts/memory_loop_demo.py` — two-run sequence prints the L1–L4 priors that fired on run-2. PR #112. |
| 3 | Tool refuses to hallucinate on a clean window | `tests/test_grounding_gate.py` (5 tests, empty-moments-valid + system-prompt-forbids-fabrication). Live fixture: `scripts/grounding_gate_live.py`. |
| 4 | Cross-modal vision (5 cameras in one prompt) | `src/black_box/analysis/visual_mining.py` — 800×600 thumbnails, 3.75 MP escalation only on demand, single-prompt cross-camera reasoning. README "Cross-modal hero mode" section. PRs #87 / #114. |
| 5 | $0.22 per session at Opus 4.7 list price | `data/costs.jsonl` cost ledger (cached/uncached/output tokens, USD per call). Cumulative & per-prompt CSV via `scripts/cost_report.py`. Curve at `docs/assets/cost_curve.png`. |
| 6 | Open public benchmark | `black-box-bench/cases/` (9 cases, MIT). Reference live run committed at `data/bench_runs/opus47_20260423T140758Z.json` — 2/3 non-skeleton match at $0.46 total. |
| 7 | Patches are scoped (clamp / timeout / null-check / gain), no auto-apply | `src/black_box/memory/decisions.py::apply_patch_if_approved` raises `PatchNotApprovedError` unless an explicit operator decision was logged. Banner + diff visible in UI; never written to disk by the agent. PR #104. |
| 8 | Network-isolated by default | `network=none` enforced in `src/black_box/security/sandbox.py`; documented in `SECURITY.md`. PR #103. |
| 9 | Secrets never enter the model's input | Credential vault in `src/black_box/security/vault.py` — capability wrappers, repo-wide lint at `tests/test_vault_lint.py` rejects raw `os.getenv("*_KEY")` outside the vault. PR #109. |
| 10 | Visual PII redaction + path-traversal sandbox | `src/black_box/security/redact.py` (faces/plates), `src/black_box/security/sandbox.py` (path resolver). PR #116. |
| 11 | Glass-box evidence trace (citations, replayable) | `GET /trace/{job_id}` route in `src/black_box/ui/app.py`; per-step citations rendered from the `ForensicAgent` event stream. PR #106. |
| 12 | Time-travel rollback to a pre-bad-ingest state | `POST /checkpoints/{id}/rollback` in `src/black_box/ui/app.py` + `memory/checkpoint.py`. PR #110. |
| 13 | Long-horizon batch via Managed Agents | `scripts/overnight_batch.py` with resume + cost cap (PR #111); asciinema at `docs/recordings/offline_batch.cast` (PR #115). |
| 14 | Tunnel **did not** cause the sanfer failure | Grounding asset in `demo_assets/grounding_gate/README.md`: tunnel caused mild GNSS degradation (`numSV 29→16`, `h_acc 645mm→1294mm`), but RTK `carr_soln=none` was already present 43 min pre-tunnel and DBW was never engaged. The narrative in PITCH.md / DEMO_SCRIPT.md / FLAG_PLANT.md matches this evidence (PR #132 for #125). |

## How to use this table

If you make a strong claim in the README, the pitch, the demo VO, or any video frame, add a row here that points at the artifact a skeptic could open. If the artifact does not yet exist, the claim does not yet ship — soften the wording or remove the claim until the row can land.

## Out-of-table claims

These are positioning claims, not capability claims. They do not need an evidence anchor:

- "NTSB for robots" — analogy.
- "We don't replace engineers" — anti-pitch.
- "Forensic, post-mortem, human-in-the-loop" — disposition statement.
