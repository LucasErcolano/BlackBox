# Black Box

Forensic copilot for robots. Feed it a robot recording, get back a root-cause hypothesis, cross-modal evidence, and a scoped code patch.

> **Pitch placeholder.** When a robot crashes, the flight data recorder tells you *what* happened. Black Box tells you *why* — and hands you the diff.

Built with **Claude Opus 4.7** (vision + reasoning) + **Managed Agents** (long-horizon session replay).

## Docs
- [Build journal & strategy](https://gist.github.com/LucasErcolano/851c5e976c6aa364f69c9e6875544061) — narrative, novelty positioning, findings.
- [Team onboarding](docs/ONBOARDING.md) — scope, cadence, conventions.
- [Pitch](docs/PITCH.md) — one-liner, elevator, positioning one-liners.
- [Demo script](docs/DEMO_SCRIPT.md) — 3-min video beat sheet.
- [Risks](docs/RISKS.md) — risk register + stop-loss triggers.
- [Submission](docs/SUBMISSION.md) — deliverables checklist.
- [Testimonial](docs/TESTIMONIAL.md) — quote capture plan.
- [Flag-plant](docs/FLAG_PLANT.md) — X/LinkedIn thread copy.
- [Rehearsal](docs/REHEARSAL.md) — pitch timing, breath points, Q&A prep.

## Modes
- **Forensic post-mortem** — known-crash recording in, root cause + patch out.
- **Scenario mining** — clean recording in, 3–5 moments of interest out. Conservative: if nothing is found, the answer is "nothing anomalous detected."
- **Synthetic QA** — injected-bug recording in, hypothesis + self-eval vs ground truth out.

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
export ANTHROPIC_API_KEY=...    # or put in .env
python -m black_box.eval.runner --case-dir black-box-bench/cases
```

## System overview

Platform-agnostic by design: the analysis layer sees a normalized session (telemetry series, multi-view frames, source snapshots) regardless of the source robot or recording format.

```mermaid
flowchart LR
    U[Operator] -->|upload recording| UI[FastAPI + HTMX]
    UI --> ING[ingestion<br/>platform adapters]
    ING --> NORM[normalized session<br/>telemetry · frames · source]
    NORM --> MA[ForensicAgent<br/>Managed Agents SDK]
    MA --> CL[Claude Opus 4.7<br/>vision + reasoning]
    CL --> MA
    MA --> GG{grounding gate<br/>min_evidence · telemetry check}
    GG -->|kept| REP[reporting<br/>PDF + side-by-side diff]
    GG -->|dropped| REP
    MA --> MEM[(4-layer memory<br/>L1..L4 JSONL)]
    REP --> OUT[case report + patch]
    SYN[synthesis<br/>injected bugs] -.-> ING
    BENCH[(bench cases)] -.-> EVAL[eval runner]
    EVAL --> MA
```

## Analysis pipeline

The three modes share one agent loop. The prompt template and the grounding gate change per mode; the memory writes are uniform.

```mermaid
sequenceDiagram
    autonumber
    participant UI as FastAPI/UI
    participant Ing as Ingestion
    participant Ag as ForensicAgent
    participant Cl as Claude Opus 4.7
    participant Gr as Grounding Gate
    participant Mem as MemoryStack
    participant Rep as Reporting

    UI->>Ing: ingest(recording)
    Ing-->>UI: telemetry + frames + source index
    UI->>Ag: start_session(case_key, mode)
    Ag->>Cl: system + taxonomy (cached) + mode prompt
    Cl-->>Ag: hypotheses (pydantic)
    Ag->>Gr: validate against telemetry windows
    alt evidence meets threshold
        Gr-->>Ag: kept + evidence refs
        Ag->>Cl: densify suspicious windows (cross-view)
        Cl-->>Ag: root cause + scoped patch
    else clean recording
        Gr-->>Ag: "nothing anomalous detected"
    end
    Ag->>Mem: log L1 case + L3 taxonomy counts
    Ag->>Rep: build PDF + HTML diff
    Rep-->>UI: artifacts ready
```

## Grounding gate (two exits)

Every hypothesis Claude emits runs through a deterministic post-filter before it reaches the PDF. The gate has two visible exits — refuse the operator narrative, or ship silence — and both are in-tree as demo assets.

```mermaid
flowchart LR
    CL[Claude hypotheses] --> G{Grounding gate}
    G -->|conf &ge; 0.4<br/>&ge;2 evidence rows<br/>&ge;2 distinct sources| KEEP[ship report]
    G -->|all hypotheses fail| NONE[ship<br/>&quot;nothing anomalous detected&quot;]
    G -->|telemetry refutes operator| REF[ship refutation<br/>as ranked hypothesis]
```

- **Refutation exit** — [`demo_assets/grounding_gate/README.md`](demo_assets/grounding_gate/README.md) — sanfer_tunnel: operator said "tunnel caused the anomaly," telemetry said RTK was already degraded 43 min pre-tunnel. The gate promoted the refutation to a ranked hypothesis with its own confidence and patch_hint.
- **Silence exit** — [`demo_assets/grounding_gate/clean_recording/README.md`](demo_assets/grounding_gate/clean_recording/README.md) — clean recording fed in, model produced four plausible-but-under-evidenced hypotheses, gate dropped all four (one per rule) and shipped `"No anomaly detected with sufficient evidence to support a scoped fix."`

Rules live in `src/black_box/analysis/grounding.py :: GroundingThresholds`. Regenerate the silence-exit fixture with `python scripts/build_grounding_gate_demo.py`.

## Package layout

```mermaid
classDiagram
    class ingestion {
        +ingest(recording) Session
        +sync_frames(streams) FrameIndex
        +render_plots(series) PNG
    }
    class analysis {
        +ClaudeClient
        +ForensicAgent
        +prompts (post_mortem/mining/synthetic_qa)
        +schemas (pydantic)
    }
    class memory {
        +MemoryStack
        +CaseMemory (L1)
        +PlatformMemory (L2)
        +TaxonomyMemory (L3)
        +EvalMemory (L4)
    }
    class platforms {
        +Adapter (abstract)
        +nao6.NAO6Adapter
        +nao6.NAO6_TAXONOMY
    }
    class synthesis {
        +inject_bug(kind) Recording
        +emit_video_prompt() str
    }
    class reporting {
        +build_pdf(case) PDF
        +side_by_side_html(diff) HTML
        +parse_patch_proposal() Tuple
    }
    class ui {
        +FastAPI app
        +HTMX progress poll
    }
    class eval {
        +run_tier3() Summary
        +self_eval vs ground truth
    }

    ui --> ingestion
    ui --> analysis
    analysis --> memory
    analysis --> platforms
    analysis --> reporting
    eval --> analysis
    eval --> synthesis
    synthesis ..> ingestion : replays as recording
```

## Bug taxonomy — closed-set benchmark, open-world product

The benchmark scorer requires an **exact-match label** from a closed set of seven common failure modes. That closed set exists for *measurement*, not for *expression* — the product surface accepts any label the model produces and routes unknown labels to a neutral `other` bucket that still carries evidence and a scoped patch.

```mermaid
classDiagram
    class BugClass {
        <<closed benchmark set>>
        pid_saturation
        sensor_timeout
        state_machine_deadlock
        bad_gain_tuning
        missing_null_check
        calibration_drift
        latency_spike
        other
    }
    class Patch {
        <<scoped fix shape>>
        clamp
        timeout
        null_check
        gain_adjust
    }
    class Hypothesis {
        +bug_class: BugClass or str
        +summary: str
        +evidence_refs: list
        +confidence: 0..1
    }
    Hypothesis --> BugClass
    BugClass ..> Patch : shapes the patch kind
```

- **For the benchmark:** closed 7-class set. A hypothesis scores iff `predicted == ground_truth`.
- **For production traffic:** open-world labels allowed. `other` is a first-class bucket — the model still has to justify the claim with telemetry + frames, and the patch shape still has to be one of the scoped primitives (clamp / timeout / null check / gain adjust). New failure modes that recur get promoted into the taxonomy via the memory stack, not by changing the prompt.

## Memory stack — substrate today, self-improving loop on the roadmap

Black Box writes an append-only 4-layer JSONL store every run (no vector DB, no RAG). This is the **substrate** for self-improvement. The visible policy loop that consumes L2 priors + L3 frequencies + L4 accuracy to steer the agent between runs is not yet convincingly surfaced in the demo — it's the next piece.

```mermaid
flowchart TB
    subgraph L1[L1 · Case]
        C1[hypothesis<br/>evidence<br/>steering]
    end
    subgraph L2[L2 · Platform]
        P1[priors per robot<br/>signature -> bug_class<br/>confidence, hits]
    end
    subgraph L3[L3 · Taxonomy]
        T1[rolling bug-class<br/>+ signature counts]
    end
    subgraph L4[L4 · Eval]
        E1[predicted vs ground truth<br/>accuracy by case/class]
    end

    FA[ForensicAgent.finalize] --> L1
    FA --> L3
    BENCH[eval runner] --> L4

    L2 -. roadmap: prime prompt .-> FA
    L3 -. roadmap: tie-break .-> FA
    L4 -. roadmap: regression alarm .-> FA
```

**Shipped:** stack wiring, pydantic records, four independent stores, `MemoryStack.open()`, accuracy roll-ups by case and bug class, taxonomy counts on every finalize.

**Not yet shipped (roadmap):** the policy loop that reads L2 priors to bias the system prompt, uses L3 frequency as a tie-breaker on low-confidence hypotheses, and raises a regression alarm when L4 accuracy on a previously-solved case class drops below a threshold. Calling that "self-improving" would be overclaim until the loop is visible between runs.

## Grounding gate

The gate is the credibility floor: every hypothesis must anchor to at least two sources (telemetry window + frame evidence, or telemetry + source snippet). A clean recording returns `"nothing anomalous detected"` by construction — the gate is why Black Box doesn't hallucinate on calm bags.

```mermaid
flowchart LR
    H[candidate hypothesis] --> G{min_evidence >= 2?}
    G -->|telemetry + frames| K[KEEP]
    G -->|telemetry + source| K
    G -->|only 1 source| D[DROP]
    G -->|zero evidence| N["nothing anomalous detected"]
```

## Adaptive resolution budgeter

Image resolution is not a fixed dial — it's a budget. The frame sampler chooses resolution per window based on:

- **Saliency** — is this a flagged telemetry spike or a quiet stretch?
- **Ambiguity** — did the last Claude call return low confidence or conflicting hypotheses?
- **Cost budget** — remaining per-case token budget against a $500 hackathon cap.

```mermaid
flowchart LR
    SP[system + taxonomy + few-shot] -->|cache_control| CACHE[(Anthropic prompt cache)]
    CACHE --> CALL[Opus 4.7 call]
    TEL[telemetry timeline] -->|pick windows| WIN[suspicious windows]
    WIN --> BUD{adaptive resolution<br/>saliency · ambiguity · $ budget}
    BUD -->|low signal| THUMB[thumbnail grid]
    BUD -->|high signal| FULL[full-res crops]
    THUMB --> CALL
    FULL --> CALL
    CALL --> LOG[data/costs.jsonl<br/>cached_in · uncached_in · out · USD]
```

Default tier is a thumbnail grid across the selected views in one cross-view prompt — **never** one call per camera. The budgeter escalates to full-resolution crops only when the analysis step explicitly asks.

## Benchmark status

The benchmark lives in a sibling repo (`black-box-bench/`). Seven cases are present. Scoring requires exact match on `bug_class`.

| Path | Cases | Offline stub | Real Opus 4.7 | Notes |
|---|---|---|---|---|
| `run_tier3(use_claude=False)` | 7 | runs | — | deterministic plumbing check; does not call the model |
| `run_tier3(use_claude=True)` | 7 | — | one case confirmed (`pid_saturation_01` via smoke script) | others pending a budgeted bench pass |
| Tier-1 forensic batch runner | — | skeleton | skeleton | single-case path works end-to-end; batch CLI not yet wired |
| Tier-2 scenario-mining batch runner | — | skeleton | skeleton | agent loop exists; bench integration pending |
| Public-data path (`eval.public_data`) | — | stub | — | downloader + adapter mapping stubbed |

The published sample run in `black-box-bench/runs/sample/` is a hand-written reference, not model output.

## UI

Three states of the FastAPI + HTMX front-end running against synthetic fixtures. NTSB aesthetic — no gradients, monospace reasoning stream, explicit job IDs.

<p>
  <img src="docs/assets/ui_upload.png" alt="Upload panel" width="800" /><br />
  <em>Upload — pick a recording, pick a mode, hand off to the worker.</em>
</p>

<p>
  <img src="docs/assets/ui_progress.png" alt="Progress panel" width="800" /><br />
  <em>Progress — staged reasoning stream (ingesting / analyzing / synthesizing / reporting), HTMX polls <code>/status/{job_id}</code> once per second.</em>
</p>

<p>
  <img src="docs/assets/ui_report.png" alt="Report panel" width="800" /><br />
  <em>Report — complete state with root cause, download link, and the "View proposed fix" side-by-side diff.</em>
</p>

Reproduce: `python scripts/capture_screenshots.py` (requires `playwright` + `playwright install chromium`).

## UI status

`src/black_box/ui/` ships the upload → streaming-reasoning → side-by-side-diff UX. Behind the UI, the pipeline worker is currently the streaming **stub** (`_run_pipeline_stub` in `ui/app.py`) that walks through realistic stage chunks and emits a canned patch artifact for the diff viewer. The demo video uses this path.

The real worker (ingestion → `ForensicAgent` session → PDF render) runs today via `scripts/managed_agent_smoke.py`; wiring that into the UI background task is the next worker-level change.

## Implementation notes (current adapters)

- **Ingestion** — `rosbags` for ROS1+ROS2 bag files (pure Python, no ROS runtime). Other adapters plug in under `platforms/`.
- **First platform** — NAO6 (SoftBank Aldebaran) humanoid. `platforms/nao6/` includes an adapter, a synthetic fall fixture, and a platform-specific taxonomy that maps to the global bug-class set.
- **Synthesis** — emits telemetry + buggy controllers + text video prompts. Video generation (Wan 2.2 / Nano Banana Pro) is operator-driven on your own GPU; nothing is auto-installed.

## Architecture (modules)
- `ingestion/` — recording parser, frame sync, plot rendering.
- `analysis/` — Claude client with aggressive prompt caching, three prompt templates, pydantic schemas, `ForensicAgent` over Managed Agents SDK.
- `memory/` — 4-layer append-only JSONL stack (case / platform / taxonomy / eval).
- `platforms/` — robot-specific adapters + taxonomies.
- `synthesis/` — injected-bug recordings + text video prompts.
- `reporting/` — reportlab PDF (NTSB-style), unified diff + HTML side-by-side.
- `ui/` — FastAPI + HTMX progress polling (stub worker today; real wiring in progress).
- `eval/` — tier-3 runner + offline stub path; tier-1/tier-2 batch runners pending.

## License
MIT.
