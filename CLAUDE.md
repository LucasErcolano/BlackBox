# Black Box — Forensic copilot for robots

Hackathon project (Built with Opus 4.7). Deadline 2026-04-26 20:00 EST. Solo builder. API budget tight ($500 total).

## Response style
- Terse. No preamble. No re-explaining what you just did.
- Prefer targeted edits over file rewrites.
- Fragments OK in comments/commits. Code itself: normal style.
- Never add code comments unless the WHY is non-obvious.

## Project shape
- `src/black_box/ingestion/` — rosbag parser (ROS1+ROS2 via `rosbags` lib, Python pure), frame sync, plot rendering.
- `src/black_box/analysis/` — Claude client (caching, token log), prompts (3 templates), pydantic schemas, managed agent skeleton.
- `src/black_box/synthesis/` — synthetic failure injection (telemetry + buggy controllers + video-prompt text for manual Wan/Nano Banana runs).
- `src/black_box/reporting/` — PDF (reportlab, NTSB-style), unified diff + HTML side-by-side.
- `src/black_box/ui/` — FastAPI + HTMX upload/progress/report.
- `src/black_box/eval/` — 3-tier runner, public data downloader.
- `black-box-bench/` — separate MIT repo for the benchmark dataset + cases.
- `data/{bags,synthetic,reports}/` — runtime artifacts, gitignored.

## Token discipline (critical — $500 cap)
- `cache_control` on system prompt + bug taxonomy + few-shot examples. Always.
- Default image resolution: 800×600 thumbnails. Escalate to 3.75 MP only when explicitly requested by the analysis step.
- Two-step frame sampling: telemetry timeline → pick suspicious windows → densify frames there only.
  Implemented by `black_box.analysis.windows.from_timeline` + `black_box.ingestion.frame_sampler.sample_frames` (one AnyReader pass for baseline + windowed dense extraction). Uniform-stride sampling is a bug; never use it for hero runs.
- 5 cameras in ONE prompt (cross-view reasoning). Never 5 separate calls.
- Every Claude call logs: cached_input_tokens, uncached_input_tokens, output_tokens, USD cost. Append to `data/costs.jsonl`.

## Session discovery
- Input is a *folder*, not a single bag. Use `black_box.ingestion.session.discover_session_assets(root)` — it groups sibling `.bag` files by numeric prefix (`2_*.bag`), matches peripheral assets (audio, chrony NTP logs) by mtime window, and excludes historical clutter (old `.webm`, archived `ros_logs/<uuid>/` launch dirs filtered by UUIDv1 timestamp).
- Never hardcode bag paths in new extractors. Operators hand over whole directories.

## Bug taxonomy (closed set)
1. PID saturation / wind-up
2. Sensor timeout / stale data
3. State machine deadlock
4. Bad gain tuning
5. Missing null check in path planning
6. Calibration drift between cameras
7. Latency spike / sync issue

## Modes
- Tier 1 — Forensic post-mortem: known-crash bag → root cause + patch.
- Tier 2 — Scenario mining: clean bag → 3–5 moments of interest. Conservative: say "nothing anomalous detected" if nothing is found. Do not invent.
- Tier 3 — Synthetic QA: injected-bug bag → hypothesis + self-eval vs ground truth.

## Hard rules
- Never install ROS 2 runtime. `rosbags` lib only.
- Never install ComfyUI / Wan 2.2 / Nano Banana. Synthesis generates TEXT prompts only; user runs video tools manually on their GPU.
- No LangChain / AutoGen / LlamaIndex / vector DBs / RAG. Flat code.
- No training. Inference-only over Opus 4.7 (`claude-opus-4-7`).
- Patches are SCOPED: clamps, timeouts, null checks, gain adjustments. No architectural rewrites.
- Never touch the user's real bags (not present here).

## Model
Always `claude-opus-4-7` for vision/analysis. Never downgrade silently.
