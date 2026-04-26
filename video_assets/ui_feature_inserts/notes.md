# ui_feature_inserts — production notes

## What this is
Short reusable UI inserts for advanced BlackBox features. Drops into the
final 3-minute cut alongside Batch A (Sanfer evidence) and Batch B
(Opus 4.7 credibility pack), which are already approved. Not a full cut.

## Recorded inserts
| insert | duration | mode | route | priority |
|--------|----------|------|-------|----------|
| memory_insert.mp4         | 7s  | live   | `/`                                 | **A** — strongest, ship in main cut |
| steering_insert.mp4       | 11s | replay+live | `/analyze?replay=sanfer_tunnel` then POST `/steer/{job}` then GET `/steer/{job}` | B — ship as side-card / overlay |
| hitl_patch_insert.mp4     | 10s | live   | `/diff/f748de9e40ca`                | **A** — already in main cut, also useful as standalone |
| rollback_insert.mp4       | 8s  | live   | `/checkpoints`                      | C — bare fragment, narrate over |
| evidence_trace_insert.mp4 | 8s  | live   | `/trace/f748de9e40ca`               | **A** — strongest "glass-box" argument |

## Skipped — none
All five features are implemented and visually presentable. None skipped.

## Mode column key
- **live**: route hits real handlers and reads real artifacts at capture
  time (no scripted mocks).
- **replay**: page is driven by `data/final_runs/sanfer_tunnel/stream_events.jsonl`
  (a real prior run, not synthetic events).
- **replay+live**: replay drives the live panel; the steer endpoint
  itself is live (real POST, real audit JSONL append).

## Per-insert provenance and caveats

### 1. memory_insert.mp4 — `GET /`
- The "NATIVE CLAUDE MEMORY MOUNTED" card and right-rail MEMORY MOUNTS
  panel are rendered from `_native_memory_status()` in `src/black_box/ui/app.py`.
- Real config strings (mount names, modes, gate). No fake panels.

### 2. steering_insert.mp4
- Replay starts via `htmx.ajax('GET','/analyze?replay=sanfer_tunnel', …)`.
- A real `POST /steer/{job_id}` is fired from the headless browser with
  the message: "Focus on whether the operator's tunnel hypothesis is
  supported by telemetry." (operator=lucas)
- The capture then navigates to `GET /steer/{job_id}` so the durable
  audit list is on screen — that is the real artifact written to
  `data/jobs/{job_id}.steer.jsonl`.
- **Honesty caveat**: `_run_pipeline_replay` does not call
  `session.steer()` because there is no live session — it just plays
  a prior event log. The audit append + history view is real; the
  "agent reacts mid-stream" payoff requires the live pipeline path
  (`_run_pipeline_real` in app.py at `_drain_steers`), which uses an
  Anthropic key. Narration should not over-claim.

### 3. hitl_patch_insert.mp4 — `GET /diff/f748de9e40ca`
- Reads `data/patches/f748de9e40ca.json` (real patch artifact emitted
  by the replay pipeline). APPROVE/REJECT POST to `/decide/{job_id}` is
  wired but not pressed in capture (we do not want the artifact
  decided before the demo run).

### 4. rollback_insert.mp4 — `GET /checkpoints`
- Two checkpoints seeded by `scripts/seed_ui_inserts.py`:
  - `pre-ingest` (kind=ingestion, provenance=replay)
  - `post-grounding-gate` (kind=analysis_turn, provenance=replay)
- Snapshots are real copies of the active L1/L2 JSONL files written by
  `black_box.memory.checkpoint.checkpoint(...)`.
- ROLLBACK button on each row POSTs to `/checkpoints/{id}/rollback`.
  Not clicked in capture (would mutate `data/memory/`).
- The rendered fragment is bare (no `_base.html` wrapper) because the
  route returns an HTMX-friendly fragment. Editor: low chrome — best as
  picture-in-picture or overlay, not full-frame.

### 5. evidence_trace_insert.mp4 — `GET /trace/f748de9e40ca`
- Trace assembled by `black_box.reporting.trace.trace_from_artifacts`
  from `data/reports/f748de9e40ca/trace_manifest.json` (seeded). The
  manifest content reflects the real Sanfer findings:
  - operator's tunnel hypothesis discarded (RTK was already broken
    pre-tunnel)
  - GPS multipath discarded (front-cam shows open sky)
  - grounding gate PASS with min_evidence=2
  - confidence 0.91 with raises/lowers
- Cost-step section is empty because `data/costs.jsonl` does not tag
  rows with this `job_id`. Acceptable — the manifest-backed sections
  are the load-bearing ones for this insert.

## Footage NOT to use
- No browser tabs, no devtools, no secrets. Single Playwright context.
- Frame-edge transitions during htmx swap on the steering insert
  (~`f_00100..f_00110`): mid-swap blank panel possible. Editor:
  prefer cutting on the audit-history frames (`f_00150+`).

## Reproducibility
```bash
# 0. Seed prerequisites (idempotent)
PYTHONPATH=src python3 scripts/seed_ui_inserts.py

# 1. Server
PYTHONPATH=src python3 -m uvicorn black_box.ui.app:app \
  --host 127.0.0.1 --port 8765 --log-level warning &

# 2. Capture
PYTHONPATH=src python3 scripts/record_ui_inserts.py

# 3. Encode subclips
FF=/home/hz/.local/bin/ffmpeg
mk_sub() {  # name start_frame end_frame
  $FF -y -framerate 10 -start_number $2 \
    -i video_assets/ui_feature_inserts/_frames/f_%05d.png -frames:v $(( $3 - $2 )) \
    -c:v libx264 -pix_fmt yuv420p -crf 20 -preset medium -movflags +faststart \
    video_assets/ui_feature_inserts/$1
}
mk_sub memory_insert.mp4         0   70
mk_sub steering_insert.mp4       70  180
mk_sub hitl_patch_insert.mp4     180 280
mk_sub rollback_insert.mp4       280 360
mk_sub evidence_trace_insert.mp4 360 440
```

## Recommended final-video priority
1. **memory_insert** + **evidence_trace_insert** + **hitl_patch_insert**
   — strongest "glass-box / human-in-the-loop / native memory" trio.
2. **steering_insert** as side-card or B-roll under operator narration.
3. **rollback_insert** only if there is room; otherwise hold for the
   technical deep-dive cut.
