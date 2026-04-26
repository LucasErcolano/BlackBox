# final_ui_capture — production notes

## What this is
Polished UI flow for the Black Box 3-minute demo. Captures only the
UI-dependent footage; Batch A (Sanfer evidence story) and Batch B (Opus 4.7
delta + generalization + grounding credibility pack) are already recorded
and approved — not regenerated here.

## Mode
- **Replay**, not live. Drives the production UI against a previously-
  recorded forensic run on the Sanfer tunnel session.
- Honesty: every frame after the intake is replay (`?replay=sanfer_tunnel`).
  Mark accordingly in the cut.

## Exact commands

```bash
# 1. Start the production FastAPI/HTMX UI (uvicorn) in the background
PYTHONPATH=src python3 -m uvicorn black_box.ui.app:app \
  --host 127.0.0.1 --port 8765 --log-level warning > /tmp/bb_uvicorn.log 2>&1 &

# 2. Run the Playwright capture (writes 650 PNG frames + phase index)
PYTHONPATH=src python3 scripts/record_final_ui.py

# 3. Encode the main 65s clip
/home/hz/.local/bin/ffmpeg -y -framerate 10 \
  -i video_assets/final_ui_capture/_frames/f_%05d.png \
  -c:v libx264 -pix_fmt yuv420p -crf 20 -preset medium -movflags +faststart \
  video_assets/final_ui_capture/clip.mp4

# 4. Subclips (per-phase, frame-range slice)
mk_sub() {  # name start_frame end_frame
  /home/hz/.local/bin/ffmpeg -y -framerate 10 -start_number $2 \
    -i video_assets/final_ui_capture/_frames/f_%05d.png -frames:v $(( $3 - $2 )) \
    -c:v libx264 -pix_fmt yuv420p -crf 20 -preset medium -movflags +faststart \
    video_assets/final_ui_capture/$1
}
mk_sub intake_ui.mp4               0   100
mk_sub managed_agent_stream_ui.mp4 100 300
mk_sub report_overview_ui.mp4      380 530
mk_sub patch_human_review_ui.mp4   530 650
```

## Routes recorded
- `http://127.0.0.1:8765/`                                  — intake / landing
- `http://127.0.0.1:8765/analyze?replay=sanfer_tunnel`      — replay launch (htmx-injected into `#main-panel` so the `_base.html` shell is preserved)
- `http://127.0.0.1:8765/report?case=sanfer_tunnel`         — report overview
- `http://127.0.0.1:8765/diff/f748de9e40ca`                 — proposed-fix diff with HUMAN APPROVAL gate (job_id pulled from the live panel during this take)

## Live vs replay vs static
| segment              | source   | notes |
|----------------------|----------|-------|
| intake_ui            | live UI  | Real `/` page, server running locally. No network calls beyond localhost. |
| analysis_start       | replay   | `replay=sanfer_tunnel` triggered via htmx. Real job_id allocated. |
| managed_agent_stream | replay   | Stream events sourced from `data/final_runs/sanfer_tunnel/stream_events.jsonl` (real prior run, not synthetic). Stages, tool calls, memory mounts, ledger all rendered by the production templates. |
| report_overview      | live UI  | `/report?case=sanfer_tunnel` reads `demo_data.case_by_id("sanfer_tunnel")`. Causal chain + exhibits are the real Sanfer findings. |
| patch_human_review   | live UI  | `/diff/<job_id>` reads `data/patches/f748de9e40ca.json` (real artifact emitted by the replay pipeline). Approve/Reject buttons functional but not pressed in capture. |

## Source artifacts shown on screen
- `data/final_runs/sanfer_tunnel/stream_events.jsonl` (87 KB, real recorded reasoning)
- `data/final_runs/sanfer_tunnel/report.md` / `report.pdf`
- `data/final_runs/sanfer_tunnel/cost.json`
- `data/patches/f748de9e40ca.json` (proposed `pid_controller.cpp` clamp patch)
- `data/jobs/f748de9e40ca.json` (run metadata for this take)

Cost-ledger panel is visible inside the live stream UI (`tool-call ledger` row
with token in/out + USD); a dedicated cost-only view was not added to the cut
to keep the main clip under 80s.

## Footage NOT to use in the final cut
- None of the captured frames contain secrets, API keys, file paths outside
  `data/`, or unrelated browser tabs (headless single-context Playwright run).
- Phase boundary frames around `f_00100..f_00105` show the htmx swap mid-
  transition. Editor: prefer cutting at `f_00110+` for the analysis_start
  → agent_stream segue.
- The "RECENT" sidebar lists synthetic-looking demo cases
  (`palette-thermal-04-22`, `pier-handover-04-15`, etc.). These are
  `demo_data.recent_cases()` placeholders, not real prior runs. If the cut
  lingers on the right rail, narration should not imply these are real
  customer engagements.

## Reproducibility
- Capture is deterministic given the same `data/final_runs/sanfer_tunnel/`
  bundle and HTMX swap timing (~200 frames variance possible in the live
  panel due to async event flush). Re-run to regenerate; nothing else
  required beyond the uvicorn server.
- Total wall-clock recording time: ~75s.
