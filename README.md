# Black Box

Forensic copilot for robots. Feed it a ROS bag, get back a root-cause hypothesis, cross-camera evidence, and a scoped code patch.

> **Pitch placeholder.** When a robot crashes, the flight data recorder tells you *what* happened. Black Box tells you *why* — and hands you the diff.

Built with **Claude Opus 4.7** (vision) + **Managed Agents** (long-horizon bag replay).

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
- **Forensic post-mortem** — crash bag in, root cause + patch out.
- **Scenario mining** — clean bag in, 3–5 moments of interest out.
- **Synthetic QA** — injected-bug bag in, hypothesis + self-eval vs ground truth out.

## Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
export ANTHROPIC_API_KEY=...    # or put in .env
python -m black_box.eval.runner --case data/synthetic/pid_saturation
```

## System overview

End-to-end flow from uploaded bag to NTSB-style report + unified diff.

```mermaid
flowchart LR
    U[Operator] -->|upload .bag| UI[FastAPI + HTMX]
    UI --> ING[ingestion<br/>rosbags parser]
    ING --> SYNC[frame sync<br/>+ plot render]
    SYNC --> MA[ForensicAgent<br/>Managed Agents SDK]
    MA --> CL[Claude Opus 4.7<br/>vision + reasoning]
    CL --> MA
    MA --> MEM[(4-layer memory<br/>L1..L4 JSONL)]
    MA --> REP[reporting<br/>PDF + side-by-side diff]
    REP --> OUT[case report + patch]
    SYN[synthesis<br/>injected bugs] -.-> ING
    BENCH[(black-box-bench<br/>ground truth)] -.-> EVAL[eval runner]
    EVAL --> MA
```

## Analysis pipeline

The three tiers share one agent loop; the prompt template and the grounding gate change per tier.

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

    UI->>Ing: parse_bag(path)
    Ing-->>UI: telemetry + plots + frame index
    UI->>Ag: start_session(case_key, tier)
    Ag->>Cl: system + taxonomy (cached) + tier-1 prompt
    Cl-->>Ag: hypotheses (pydantic)
    Ag->>Gr: validate against telemetry windows
    Gr-->>Ag: kept vs rejected + evidence refs
    Ag->>Cl: densify suspicious windows (5 cams/prompt)
    Cl-->>Ag: root cause + scoped patch
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
        +parse_bag(path) Telemetry
        +sync_frames(topics) FrameIndex
        +render_plots(series) PNG
    }
    class analysis {
        +ClaudeClient
        +ForensicAgent
        +prompts (tier1/tier2/tier3)
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
        +nao6.NAO6Adapter
        +nao6.NAO6_TAXONOMY
    }
    class synthesis {
        +inject_bug(kind) Bag
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
        +TierRunner (1/2/3)
        +self_eval vs ground truth
    }

    ui --> ingestion
    ui --> analysis
    analysis --> memory
    analysis --> platforms
    analysis --> reporting
    eval --> analysis
    eval --> synthesis
    synthesis ..> ingestion : replays as bag
```

## Memory stack (L1–L4)

Append-only JSONL, flat code, no vector DB. Each layer has a single narrow responsibility.

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
    L2 -.priors.-> FA
    L3 -.global freq.-> FA
```

## Bug taxonomy (closed set)

```mermaid
classDiagram
    class BugClass {
        <<enumeration>>
        pid_saturation
        sensor_timeout
        state_machine_deadlock
        bad_gain_tuning
        missing_null_check
        calibration_drift
        latency_spike
    }
    class Patch {
        <<policy>>
        clamp
        timeout
        null_check
        gain_adjust
    }
    class Hypothesis {
        +bug_class: BugClass
        +summary: str
        +evidence_refs: list
        +confidence: 0..1
    }
    Hypothesis --> BugClass
    BugClass ..> Patch : scoped fix shape
```

Closed set (7): `pid_saturation`, `sensor_timeout`, `state_machine_deadlock`, `bad_gain_tuning`, `missing_null_check` (path planning), `calibration_drift` (cameras), `latency_spike` / sync issue.

## Token discipline

```mermaid
flowchart LR
    SP[system + taxonomy + few-shot] -->|cache_control| CACHE[(Anthropic prompt cache)]
    CACHE --> CALL[Opus 4.7 call]
    TEL[telemetry timeline] -->|pick windows| WIN[suspicious windows]
    WIN -->|densify frames| FR[5 cams · 800x600 thumbs]
    FR --> CALL
    CALL --> LOG[data/costs.jsonl<br/>cached_in · uncached_in · out · USD]
```

Escalate to 3.75 MP only on explicit request from the analysis step. Never 5 separate calls for 5 cameras — one cross-view prompt.

## Architecture (modules)
- `ingestion/` — `rosbags`-based ROS1+ROS2 parser, frame sync, matplotlib plots.
- `analysis/` — Claude client with aggressive prompt caching, 3 prompt templates, pydantic schemas, `ForensicAgent` over Managed Agents SDK.
- `memory/` — 4-layer append-only JSONL stack (case / platform / taxonomy / eval).
- `platforms/` — robot-specific adapters + taxonomies (NAO6 today).
- `synthesis/` — injects known bugs, emits ground truth + text video prompts (run Wan 2.2 / Nano Banana Pro yourself).
- `reporting/` — reportlab PDF (NTSB-style), unified diff + HTML side-by-side.
- `ui/` — FastAPI + HTMX progress polling.
- `eval/` — 3-tier runner.

## License
MIT.
