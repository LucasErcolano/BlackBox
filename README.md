# Black Box

Forensic copilot for robots. Feed it a ROS bag, get back a root-cause hypothesis, cross-camera evidence, and a scoped code patch.

> **Pitch placeholder.** When a robot crashes, the flight data recorder tells you *what* happened. Black Box tells you *why* — and hands you the diff.

Built with **Claude Opus 4.7** (vision) + **Managed Agents** (long-horizon bag replay).

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

## Architecture
- `ingestion/` — `rosbags`-based ROS1+ROS2 parser, frame sync, matplotlib plots.
- `analysis/` — Claude client with aggressive prompt caching, 3 prompt templates, pydantic schemas.
- `synthesis/` — injects known bugs, emits ground truth + text video prompts (run Wan 2.2 / Nano Banana Pro yourself).
- `reporting/` — reportlab PDF (NTSB-style), unified diff + HTML side-by-side.
- `ui/` — FastAPI + HTMX.
- `eval/` — 3-tier runner.

## License
MIT.
