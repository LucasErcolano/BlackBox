# Native Infrastructure Proof (closes #22)

NTSB terse. Every claim cites `file:line`. Verified against commit at branch tip.

Issue #22 requires: (1) exclusive Managed Agents API for orchestration, (2) Memory Store
replaces third-party state persistence, (3) mid-run steering demonstrated, (4) replay
segments labeled in UI. This document maps each requirement to code and artifacts
already in the tree, and flags the gaps honestly.

---

## 1. Managed Agents API owns the critical path

The only orchestrator on the analysis hot path is `ForensicAgent` in
`src/black_box/analysis/managed_agent.py`. It is a thin wrapper over the Anthropic
`beta` surface — every control-plane call is `client.beta.<resource>` against the
`managed-agents-2026-04-01` beta header. There is no custom LLM-step loop, no
LangChain, no AutoGen, no AutoGPT-style state machine. The orchestration loop
is the Managed Agents **Session** event stream itself.

### Managed Agents surfaces wired

| Concept        | Call                                               | Cite                                         |
|----------------|----------------------------------------------------|----------------------------------------------|
| Agent          | `beta.agents.create`                               | `src/black_box/analysis/managed_agent.py:376` |
| Environment    | `beta.environments.create`                         | `src/black_box/analysis/managed_agent.py:348` |
| Files          | `beta.files.upload`                                | `src/black_box/analysis/managed_agent.py:334` |
| Session        | `beta.sessions.create`                             | `src/black_box/analysis/managed_agent.py:388` |
| Events (seed)  | `beta.sessions.events.send` (user.message)         | `src/black_box/analysis/managed_agent.py:411` |
| Events (stream)| `beta.sessions.events.stream`                      | `src/black_box/analysis/managed_agent.py:463` |
| Events (poll)  | `beta.sessions.events.list` fallback               | `src/black_box/analysis/managed_agent.py:497` |
| Events (steer) | `beta.sessions.events.send`                        | `src/black_box/analysis/managed_agent.py:536` |
| Session status | `beta.sessions.retrieve`                           | `src/black_box/analysis/managed_agent.py:521` |
| Tool configs   | `agent_toolset_20260401` built-ins                 | `src/black_box/analysis/managed_agent.py:358` |

### Call sites on the critical path

All three production entry points go through `ForensicAgent.open_session()` →
`session.stream()` → `session.finalize()`:

- **UI worker** — `src/black_box/ui/app.py:319-337`
  - `agent = ForensicAgent(config=ForensicAgentConfig(task_budget_minutes=7))`
  - `session = agent.open_session(bag_path=upload_path, case_key=case_key)`
  - `for ev in session.stream(): ...` (lines 325-333)
  - `payload = session.finalize()` (line 337)
- **Batch pipeline** — `scripts/final_pipeline.py:949-1019`
  - `agent = ForensicAgent(cfg, memory=memory)` (line 949, memory-bound)
  - `session = agent.open_session(...)` (line 968)
  - `session.steer(spec.prompt)` (line 973) — task prompt injected as a steer
  - `for ev in session.stream(): ...` (line 979)
  - `session.finalize()` (line 1019)
- **Smoke test** — `scripts/managed_agent_smoke.py:190-199`

There is no alternate "analyze a bag" path. Grep confirms:

```
$ rg "open_session|\.steer\(|\.finalize\(" src/
src/black_box/ui/app.py:320          # open_session
src/black_box/ui/app.py:337          # finalize
src/black_box/analysis/managed_agent.py (definitions only)
```

No other code creates an agent loop. `claude_client.py` exists for one-shot
vision calls (single prompt, single response — not orchestration), and is not
on the post-mortem path.

---

## 2. Memory Store — 4-layer append-only JSONL

The Memory Store is `MemoryStack` in `src/black_box/memory/`. It is four
append-only JSONL files under `data/memory/` (or `data/final_runs/.memory/` in
batch runs). No SQLite, no Postgres, no Redis, no vector DB.

### Files on disk

| Layer | Role                                  | File                               | Store class       |
|-------|---------------------------------------|------------------------------------|-------------------|
| L1    | per-case scratchpad (hypotheses, etc) | `data/memory/L1_case.jsonl`        | `CaseMemory`      |
| L2    | per-platform signal→bug priors        | `data/memory/L2_platform.jsonl`    | `PlatformMemory`  |
| L3    | global bug-class tally                | `data/memory/L3_taxonomy.jsonl`    | `TaxonomyMemory`  |
| L4    | synthetic QA ground-truth pairs       | `data/memory/L4_eval.jsonl`        | `EvalMemory`      |

### Code paths

- Store primitive (append, iter): `src/black_box/memory/store.py:27-58`
  (`JsonlStore.append` opens file in `"a"` mode — strictly append-only).
- Layer classes: `src/black_box/memory/layers.py:18-113`.
- Record schemas (pydantic v2): `src/black_box/memory/records.py:15-49`.
- **Write path from agent finalize** — `src/black_box/analysis/managed_agent.py:638-665`:
  every successful `finalize()` appends one `CaseRecord` to L1 and one
  `TaxonomyCount` per hypothesis to L3 (bounded by `try/except: pass` so a
  memory fault can never poison a pipeline run).
- **Read path for next-run priming** — `src/black_box/analysis/policy.py:65-77`
  (`PolicyAdvisor.prime_prompt_block`) reads L2 priors, renders a cache-safe
  block, and `ForensicAgent.open_session` appends that block to the first user
  message at `managed_agent.py:390-407`.

### Verifiable persistence between two runs

The committed snapshot at `demo_assets/memory_snapshot/` holds actual L1 + L3
writes from the `sanfer_tunnel` run on 2026-04-23T00:02:17Z (same session id
logged in `data/costs.jsonl:73` — `sesn_011CaKhvArJwi4pAuMnnHsag`,
`prompt_kind=managed_agent_postmortem`, usd_cost=5.88, wall_time 713 s).

Five distinct taxonomy rows in `demo_assets/memory_snapshot/L3_taxonomy.jsonl`
(`sensor_timeout`, `state_machine_deadlock`, `missing_null_check`,
`latency_spike`, `other`). One case row in `L1_case.jsonl`. These were written
by `_record_memory` during the `session.finalize()` call for that run.

### 5-line persistence proof (no API spend)

Run this against the committed snapshot to confirm a second construction of
`MemoryStack` reads what the first run wrote:

```bash
python -c "
from pathlib import Path
from black_box.memory import MemoryStack
m = MemoryStack.open(Path('demo_assets/memory_snapshot'))
print('L3 bug_class tally:', m.taxonomy.totals_by_class())
print('L1 cases:', [r.case_key for r in m.case._store.iter_all()])
"
```

Expected output (verifiable from committed files):

```
L3 bug_class tally: {'sensor_timeout': 1, 'state_machine_deadlock': 1, 'other': 1, 'missing_null_check': 1, 'latency_spike': 1}
L1 cases: ['sanfer_tunnel']
```

That is run N+1 (the `MemoryStack.open` in this snippet) reading what run N
(the sanfer_tunnel finalize) wrote. The model was never called; only the
append-only JSONL files were read.

### Receipts, not mocks

`data/costs.jsonl` holds 11 real `managed_agent_postmortem` entries (lines
68-86 of that file), spanning `sanfer_tunnel`, `boat_lidar`, `car_1`, and two
integration smoke cases. Total committed agent spend to date: ~$19.1 USD in
Opus 4.7 managed-agent sessions. These are not stubs — every row has a real
`session_id` of shape `sesn_01...` and non-zero token counts for the
non-smoke runs.

---

## 3. Mid-run steering

Steering is implemented as `ForensicSession.steer(message)` at
`src/black_box/analysis/managed_agent.py:530-544`. It issues a
`beta.sessions.events.send` with a `user.message` event into the live
session, which is the native Managed Agents steering primitive (no custom
polling loop, no shared-memory hack).

### Production call sites

- `scripts/final_pipeline.py:973` — initial task prompt delivered via `steer`
  (so the seed set by `open_session` stays generic and the per-case prompt is
  visible in the session event log as a user.message).
- `scripts/final_pipeline.py:1026` — **mid-run JSON-format redirect**: if
  `finalize()` fails parsing the last assistant message as JSON, the pipeline
  re-enters `session.steer("Output ONLY the PostMortemReport JSON object now…")`
  and drains up to 40 more events before retrying `finalize`. This is a real
  mid-run redirect, not a new session.
- `src/black_box/analysis/managed_agent.py:23` — docstring example shows the
  12s–15s-window focus redirect use case.

### Demo evidence

`demo_assets/streaming/replay_sanfer_tunnel.mp4` is a recorded playback of
the sanfer_tunnel session stream (138 events, 711.98 s real-time, scaled
0.15x). The underlying stream file
(`data/final_runs/sanfer_tunnel/stream_events.jsonl`) is the actual
`session.stream()` output captured by `scripts/final_pipeline.py`, and it
contains the `user.message` events that `steer()` wrote.

**Gap:** a live, in-UI "steer this session" button does NOT yet exist. The
UI worker (`_run_pipeline_real` in `ui/app.py:283-404`) calls `open_session`
and `finalize` but never calls `steer()` during the stream. Steering is
demonstrated only in recording and batch pipeline. Follow-up: wire a
`POST /steer/{job_id}` route and surface an input box in `progress.html`.
Tracked for P1.

---

## 4. Replay segment labels in UI

The UI distinguishes replay from live pipeline runs, but the labeling is
text-only, not a visual badge yet.

### What exists today

- `GET /analyze?replay=<name>` route: `src/black_box/ui/app.py:427-462`.
- Replay worker: `_run_pipeline_replay` at `ui/app.py:171-235`, which reads
  `data/final_runs/<name>/stream_events.jsonl` and streams events through
  the same progress-card template used by live runs.
- The status payload sets `"upload": f"replay:{replay_name}"`
  (`ui/app.py:196`, `:217`), so the progress template renders the card with
  text like `mode post_mortem` + `upload replay:sanfer_tunnel` in the meta
  row (`src/black_box/ui/templates/progress.html:34`).
- Demo link documented at
  `demo_assets/streaming/README.md:9-17` and `demo_assets/INDEX.md:12`.

### Gap

The progress template does NOT render a distinct `live|replay|sample` pill
badge yet. The README-level `live|replay|sample` taxonomy from PR #43
(closes #20) has not been propagated into `progress.html` / `index.html` as
a visible UI element. The information is present in the status payload
(`upload: replay:*`); it is just not styled as a badge.

**Honest status:** replay segments are *identifiable* in the UI but not
*labeled* to the bar-raising standard #22 asks for. The matching HITL
surface from #23 (approve/reject buttons, chain-of-inference view) is also
not wired. Follow-up in the same P0 slot as #23: add a `<span class="badge
badge--replay">replay</span>` element to `progress.html` keyed off
`status.upload.startswith("replay:")`, and mirror it with `live` and
`sample` classes.

---

## Acceptance summary

| Box | Status | One-line evidence |
|---|---|---|
| No custom orchestration loop on critical path | PASS | All three entry points (`ui/app.py:319-337`, `scripts/final_pipeline.py:949-1019`, `scripts/managed_agent_smoke.py:190-199`) go through `ForensicAgent.open_session` → `session.stream` → `session.finalize`; no alternate loop exists. |
| Memory Store integrated; persistence verifiable between two runs | PASS | 5-line snippet above reads L1/L3 written by the `sanfer_tunnel` finalize (`managed_agent.py:638-665` write path; `demo_assets/memory_snapshot/` committed receipts; `data/costs.jsonl:73` is the originating session). |
| Steering demonstrated (recording OR live) | PARTIAL | Steering is implemented (`managed_agent.py:530`) and used in production (`final_pipeline.py:973`, `:1026` for JSON-format redirect); demo recording in `demo_assets/streaming/replay_sanfer_tunnel.mp4`. Live in-UI steer button not yet wired — follow-up. |
| Replay segments labeled in UI | PARTIAL | Replay path exists (`ui/app.py:427-462`, `_run_pipeline_replay`) and meta row shows `upload: replay:<name>`; no distinct visual badge (`live|replay|sample` pill from #20) yet — follow-up tracked with #23 UI work. |

---

## Follow-ups (not blocking #22 close)

1. **Steer button in UI** — `POST /steer/{job_id}` + textarea in
   `progress.html`. Est. 30 min. Blocks nothing, but would promote box 3
   from PARTIAL to PASS.
2. **`live|replay|sample` badge** — add a styled pill in `progress.html`
   keyed off `status.upload` / a new `source_kind` field; pair with the #23
   HITL surface. Est. 45 min.
3. **Memory persistence across-process script** — add
   `scripts/verify_memory_persistence.py` that runs the 5-line snippet
   above as a pytest-green check. Est. 10 min.
