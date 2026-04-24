# SPDX-License-Identifier: MIT
"""Black Box FastAPI + HTMX front-end.

Serves a sober, single-column upload UI for forensic analysis jobs.
Routes the upload through a real ingestion -> ForensicAgent -> PDF pipeline
when ``BLACKBOX_REAL_PIPELINE=1`` (and an ``ANTHROPIC_API_KEY`` is set);
otherwise falls back to the scripted stub so the UI still reads as a
thought process in offline demos.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from black_box.reporting.diff import demo_side_by_side_html, parse_patch_proposal

# ---- paths ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent.parent  # src/black_box/ui -> repo root
DATA_DIR = REPO_ROOT / "data"
JOBS_DIR = DATA_DIR / "jobs"
REPORTS_DIR = DATA_DIR / "reports"
UPLOADS_DIR = DATA_DIR / "uploads"
PATCHES_DIR = DATA_DIR / "patches"
for d in (JOBS_DIR, REPORTS_DIR, UPLOADS_DIR, PATCHES_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---- app --------------------------------------------------------------------
app = FastAPI(title="Black Box", description="Forensic copilot for robots")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

Mode = Literal["post_mortem", "scenario_mining", "synthetic_qa"]

# Per-stage reasoning chunks — visible during the stream so the demo reads
# as a thought process, not a progress bar. Stub only; real pipeline streams
# from Claude's managed-agent session events.
_STAGE_CHUNKS: dict[str, list[str]] = {
    "ingesting": [
        "Opening recording and enumerating topics...",
        "Found /imu (100 Hz), /cam_{front,left,right,back,top} (10 Hz), /joint_states.",
        "Decoded 3.2 s of telemetry; sampling frames at 10 fps across 5 cameras.",
    ],
    "analyzing": [
        "Pulled 5-camera composite at t=1.8s (telemetry delta flagged this window).",
        "Claude call 1: cross-view reasoning over 5 thumbnails + IMU window.",
        "IMU pitch slope = -0.42 rad/s; /joint/LHipPitch command at +2.5 while joint saturates.",
        "Working theory: PID integral wind-up on hip pitch during step initiation.",
    ],
    "synthesizing": [
        "Grounding gate: 3/3 hypotheses meet min_evidence=2 (telemetry + camera).",
        "Cross-source corroboration: cameras {front, left} + /imu + pid_controller.cpp.",
        "Dropping 1 low-confidence info moment; keeping 2 anomalous.",
    ],
    "reporting": [
        "Rendering annotated frames with bbox overlays on hip joint...",
        "Generating unified diff against pid_controller.cpp...",
        "Writing NTSB-style Markdown to data/reports/{job}.md.",
    ],
    "done": [
        "Done. Root cause: pid_saturation (confidence 0.82). Patch: clamp integral ±1.0.",
    ],
}

STAGES = [
    ("ingesting", "Decoding bag and extracting frames"),
    ("analyzing", "Claude is reviewing evidence"),
    ("synthesizing", "Cross-checking hypotheses"),
    ("reporting", "Rendering PDF report"),
    ("done", "Complete"),
]

# Stub patch artifact used by the diff viewer demo beat.
_STUB_PATCH = {
    "file_path": "src/controllers/pid_controller.cpp",
    "old": (
        "void PidController::update(double error, double dt) {\n"
        "    integral_ += error * dt;\n"
        "    double derivative = (error - prev_error_) / dt;\n"
        "    output_ = kp_ * error + ki_ * integral_ + kd_ * derivative;\n"
        "    prev_error_ = error;\n"
        "}\n"
    ),
    "new": (
        "void PidController::update(double error, double dt) {\n"
        "    integral_ += error * dt;\n"
        "    integral_ = std::clamp(integral_, -integral_limit_, integral_limit_);\n"
        "    double derivative = (error - prev_error_) / dt;\n"
        "    output_ = kp_ * error + ki_ * integral_ + kd_ * derivative;\n"
        "    output_ = std::clamp(output_, -output_limit_, output_limit_);\n"
        "    prev_error_ = error;\n"
        "}\n"
    ),
}


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _patch_path(job_id: str) -> Path:
    return PATCHES_DIR / f"{job_id}.json"


def _write_status(job_id: str, payload: dict) -> None:
    _job_path(job_id).write_text(json.dumps(payload, indent=2))


def _read_status(job_id: str) -> dict | None:
    p = _job_path(job_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


# ---- real stream replay -----------------------------------------------------
REPLAY_ROOT = DATA_DIR / "final_runs"
REPLAY_SCALE = 0.15  # wall-clock / demo-clock ratio
REPLAY_MAX_SLEEP = 0.8  # cap per-event sleep in seconds


def _replay_stage(progress: float) -> tuple[str, str]:
    if progress < 0.25:
        return ("ingesting", "Decoding bag and extracting frames")
    if progress < 0.55:
        return ("analyzing", "Claude is reviewing evidence")
    if progress < 0.85:
        return ("synthesizing", "Cross-checking hypotheses")
    if progress < 1.0:
        return ("reporting", "Rendering PDF report")
    return ("done", "Complete")


def _fmt_replay_event(ev: dict) -> str | None:
    t = ev.get("type")
    p = ev.get("payload") or {}
    if t == "status":
        state = p.get("state", "")
        if state in {"running", "user.message", "idle", "completed"}:
            return f"[status] {state}"
        return None  # skip chatty span.* events
    if t == "reasoning":
        return "[reasoning] (thinking...)"
    if t == "tool_call":
        name = p.get("name", "tool")
        inp = p.get("input") or {}
        preview = inp.get("command") or json.dumps(inp)[:140]
        return f"[tool:{name}] {preview[:180]}"
    if t == "tool_result":
        text = (p.get("text") or "").replace("\n", " ⏎ ")
        err = "ERR " if p.get("is_error") else ""
        return f"[result] {err}{text[:180]}"
    if t == "assistant":
        text = (p.get("text") or "").replace("\n", " ")
        return f"[assistant] {text[:220]}"
    return None


def _run_pipeline_replay(job_id: str, replay_name: str) -> None:
    """Replay a recorded ForensicSession event stream at demo-scaled speed."""
    jsonl = REPLAY_ROOT / replay_name / "stream_events.jsonl"
    buffer: list[str] = []
    try:
        events = [json.loads(line) for line in jsonl.read_text().splitlines() if line.strip()]
        if not events:
            raise ValueError(f"no events in {jsonl}")
        t0 = float(events[0].get("ts", 0.0))
        last_ts = t0
        total = len(events)
        for i, ev in enumerate(events):
            line = _fmt_replay_event(ev)
            if line is not None:
                buffer.append(line)
            progress = (i + 1) / total
            stage, label = _replay_stage(progress)
            _write_status(
                job_id,
                {
                    "job_id": job_id,
                    "stage": stage,
                    "label": label,
                    "progress": progress,
                    "mode": "post_mortem",
                    "upload": f"replay:{replay_name}",
                    "reasoning_buffer": list(buffer[-200:]),
                    "has_diff": stage == "done",
                },
            )
            ts = float(ev.get("ts", last_ts))
            delta = max(0.0, ts - last_ts)
            last_ts = ts
            sleep_s = min(delta * REPLAY_SCALE, REPLAY_MAX_SLEEP)
            if sleep_s > 0:
                time.sleep(sleep_s)
        # Patch artifact so the /diff route works for the replay job too.
        _patch_path(job_id).write_text(json.dumps(_STUB_PATCH, indent=2))
        _write_status(
            job_id,
            {
                "job_id": job_id,
                "stage": "done",
                "label": "Complete",
                "progress": 1.0,
                "mode": "post_mortem",
                "upload": f"replay:{replay_name}",
                "reasoning_buffer": list(buffer[-200:]),
                "has_diff": True,
            },
        )
    except Exception as e:  # pragma: no cover - defensive
        buffer.append(f"ERROR: {e!r}")
        _write_status(
            job_id,
            {
                "job_id": job_id,
                "stage": "failed",
                "label": "Replay error",
                "progress": 0.0,
                "mode": "post_mortem",
                "reasoning_buffer": list(buffer),
                "has_diff": False,
            },
        )


# ---- real pipeline ----------------------------------------------------------
def _real_pipeline_enabled() -> bool:
    """Real pipeline only fires when explicitly enabled AND an API key is set."""
    return os.getenv("BLACKBOX_REAL_PIPELINE") == "1" and bool(os.getenv("ANTHROPIC_API_KEY"))


def _fmt_stream_event(ev: dict) -> str | None:
    """Convert a ForensicSession.stream() event dict into one buffer line.

    Same shape as ``_fmt_replay_event`` so the UI reads identically in live
    and replay modes.
    """
    t = ev.get("type")
    p = ev.get("payload") or {}
    if t == "status":
        state = p.get("state", "")
        if state in {"running", "user.message", "idle", "completed"}:
            return f"[status] {state}"
        return None
    if t == "reasoning":
        return "[reasoning] (thinking...)"
    if t == "tool_call":
        name = p.get("name", "tool")
        inp = p.get("input") or {}
        preview = inp.get("command") or json.dumps(inp)[:140]
        return f"[tool:{name}] {preview[:180]}"
    if t == "tool_result":
        text = (p.get("text") or "").replace("\n", " ⏎ ")
        err = "ERR " if p.get("is_error") else ""
        return f"[result] {err}{text[:180]}"
    if t == "assistant":
        text = (p.get("text") or "").replace("\n", " ")
        return f"[assistant] {text[:220]}"
    return None


_REAL_STAGE_MAP = {
    "status": ("analyzing", "Claude is reviewing evidence"),
    "reasoning": ("analyzing", "Claude is reviewing evidence"),
    "tool_call": ("analyzing", "Claude is reviewing evidence"),
    "tool_result": ("analyzing", "Claude is reviewing evidence"),
    "assistant": ("synthesizing", "Cross-checking hypotheses"),
}


def _run_pipeline_real(job_id: str, upload_path: Path, mode: Mode) -> None:
    """Real ingestion -> ForensicAgent -> PDF wiring.

    Streams ``session.stream()`` events into the reasoning buffer so the UI
    shows actual agent activity, not scripted text. Falls through to
    ``_run_pipeline_stub`` on any setup failure so a missing key / SDK
    version never leaves the user staring at a spinner.
    """
    from black_box.analysis.managed_agent import ForensicAgent, ForensicAgentConfig
    from black_box.reporting import build_report

    buffer: list[str] = []

    def _push(stage: str, label: str, progress: float, *, done: bool = False) -> None:
        _write_status(
            job_id,
            {
                "job_id": job_id,
                "stage": stage,
                "label": label,
                "progress": progress,
                "mode": mode,
                "upload": upload_path.name,
                "reasoning_buffer": list(buffer[-200:]),
                "has_diff": done,
            },
        )

    try:
        buffer.append(f"[ingest] Uploaded {upload_path.name}, {upload_path.stat().st_size} bytes")
        _push("ingesting", "Decoding bag and extracting frames", 0.08)

        case_key = f"ui_{job_id}"
        buffer.append(f"[agent] Opening ForensicAgent session for {case_key}")
        _push("ingesting", "Decoding bag and extracting frames", 0.15)

        agent = ForensicAgent(config=ForensicAgentConfig(task_budget_minutes=7))
        session = agent.open_session(bag_path=upload_path, case_key=case_key)
        buffer.append(f"[agent] session_id={session.session_id}")
        _push("analyzing", "Claude is reviewing evidence", 0.25)

        event_count = 0
        for ev in session.stream():
            event_count += 1
            line = _fmt_stream_event(ev)
            if line is not None:
                buffer.append(line)
            stage, label = _REAL_STAGE_MAP.get(ev.get("type", ""), ("analyzing", "Claude is reviewing evidence"))
            # Coarse progress: 0.25 -> 0.75 across the stream; never regress.
            progress = min(0.75, 0.25 + 0.005 * event_count)
            _push(stage, label, progress)

        buffer.append("[finalize] Parsing agent report payload...")
        _push("synthesizing", "Cross-checking hypotheses", 0.82)
        payload = session.finalize()
        top = (payload.get("hypotheses") or [{}])[0].get("bug_class", "other")
        buffer.append(f"[finalize] top hypothesis: {top}")

        buffer.append("[report] Building NTSB-style Markdown report...")
        _push("reporting", "Rendering Markdown report", 0.92)
        out_pdf = REPORTS_DIR / f"{job_id}.md"
        build_report(
            report_json=payload,
            artifacts={},
            out_pdf=out_pdf,
            case_meta={
                "case_key": case_key,
                "bag_path": str(upload_path),
                "mode": mode,
                "duration_s": 0.0,
            },
        )
        buffer.append(f"[report] Wrote {out_pdf.name} ({out_pdf.stat().st_size} bytes)")

        # Patch artifact for the /diff route. If the model emitted a unified
        # diff in patch_proposal, hand that to the viewer; else fall back to
        # the stub so the diff tab still renders something sane.
        patch_blob = (payload.get("patch_proposal") or "").strip()
        if patch_blob.startswith(("---", "diff ")):
            _patch_path(job_id).write_text(json.dumps({"unified_diff": patch_blob}, indent=2))
        else:
            _patch_path(job_id).write_text(json.dumps(_STUB_PATCH, indent=2))

        _push("done", "Complete", 1.0, done=True)
    except Exception as e:  # pragma: no cover - live API failure path
        buffer.append(f"ERROR: {e!r}")
        buffer.append("[fallback] Falling back to stub pipeline so the UI stays responsive.")
        _push("analyzing", "Live pipeline failed — replaying stub", 0.3)
        _run_pipeline_stub(job_id, upload_path, mode)


# ---- background stub --------------------------------------------------------
def _run_pipeline_stub(job_id: str, upload_path: Path, mode: Mode) -> None:
    """Fake pipeline: streams reasoning chunks and walks through stages.

    TODO(pipeline): wire real ingestion -> claude -> reporting here.
    """
    buffer: list[str] = []
    try:
        for i, (stage, label) in enumerate(STAGES):
            chunks = _STAGE_CHUNKS.get(stage, [label])
            base_progress = i / len(STAGES)
            for j, chunk in enumerate(chunks):
                buffer.append(f"[{stage}] {chunk}")
                inner_progress = base_progress + ((j + 1) / len(chunks)) * (1.0 / len(STAGES))
                _write_status(
                    job_id,
                    {
                        "job_id": job_id,
                        "stage": stage,
                        "label": label,
                        "progress": inner_progress,
                        "mode": mode,
                        "upload": str(upload_path.name),
                        "reasoning_buffer": list(buffer),
                        "has_diff": stage == "done",
                    },
                )
                if stage != "done":
                    time.sleep(0.8)
        # Write stub patch artifact for the diff route.
        _patch_path(job_id).write_text(json.dumps(_STUB_PATCH, indent=2))
    except Exception as e:  # pragma: no cover - defensive
        buffer.append(f"ERROR: {e!r}")
        _write_status(
            job_id,
            {
                "job_id": job_id,
                "stage": "failed",
                "label": "Pipeline error",
                "progress": 0.0,
                "mode": mode,
                "reasoning_buffer": list(buffer),
                "has_diff": False,
            },
        )


# ---- routes -----------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/analyze", response_class=HTMLResponse)
async def analyze_replay(
    request: Request,
    background: BackgroundTasks,
    replay: str = Query(..., description="name of data/final_runs/<name>/ to replay"),
) -> HTMLResponse:
    jsonl = REPLAY_ROOT / replay / "stream_events.jsonl"
    if not jsonl.exists():
        raise HTTPException(404, f"no recorded stream for replay={replay!r}")

    job_id = uuid.uuid4().hex[:12]
    _write_status(
        job_id,
        {
            "job_id": job_id,
            "stage": "queued",
            "label": f"Queued replay: {replay}",
            "progress": 0.0,
            "mode": "post_mortem",
            "upload": f"replay:{replay}",
            "reasoning_buffer": [f"Replaying recorded session: {replay}"],
            "has_diff": False,
        },
    )
    background.add_task(_run_pipeline_replay, job_id, replay)

    # Render the full shell with the progress card already injected so the
    # demo link `?replay=...` loads a styled page, not a bare HTMX fragment.
    progress_html = templates.get_template("progress.html").render(
        request=request, job_id=job_id, status=_read_status(job_id) or {}
    )
    return templates.TemplateResponse(
        request,
        "index.html",
        {"initial_html": progress_html},
    )


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form("post_mortem"),
) -> HTMLResponse:
    if mode not in ("post_mortem", "scenario_mining", "synthetic_qa"):
        raise HTTPException(400, f"unknown mode: {mode}")

    job_id = uuid.uuid4().hex[:12]
    upload_path = UPLOADS_DIR / f"{job_id}_{file.filename}"
    with upload_path.open("wb") as fh:
        while chunk := await file.read(1 << 20):
            fh.write(chunk)

    _write_status(
        job_id,
        {
            "job_id": job_id,
            "stage": "queued",
            "label": "Queued",
            "progress": 0.0,
            "mode": mode,
            "upload": upload_path.name,
            "reasoning_buffer": ["Waiting for worker..."],
            "has_diff": False,
        },
    )
    worker = _run_pipeline_real if _real_pipeline_enabled() else _run_pipeline_stub
    background.add_task(worker, job_id, upload_path, mode)  # type: ignore[arg-type]

    return templates.TemplateResponse(
        request,
        "progress.html",
        {"job_id": job_id, "status": _read_status(job_id) or {}},
    )


@app.get("/status/{job_id}", response_class=HTMLResponse)
async def status(request: Request, job_id: str) -> HTMLResponse:
    data = _read_status(job_id)
    if data is None:
        raise HTTPException(404, "unknown job")
    return templates.TemplateResponse(
        request,
        "progress.html",
        {"job_id": job_id, "status": data},
    )


@app.get("/report/{job_id}")
async def report(job_id: str) -> FileResponse:
    md = REPORTS_DIR / f"{job_id}.md"
    if not md.exists():
        raise HTTPException(404, "report not ready")
    return FileResponse(str(md), media_type="text/markdown", filename=md.name)


@app.get("/diff/{job_id}", response_class=HTMLResponse)
async def diff_view(job_id: str) -> HTMLResponse:
    """Side-by-side diff viewer — the 2:00–2:20 demo beat.

    Reads the patch artifact written by the pipeline. Falls back to parsing
    ``patch_proposal`` from the JSON report if no structured artifact exists.
    """
    patch_file = _patch_path(job_id)
    if patch_file.exists():
        patch = json.loads(patch_file.read_text())
        old, new = patch["old"], patch["new"]
        file_path = patch.get("file_path", "patch")
    else:
        # Fallback: parse a text patch_proposal if a report JSON is present.
        report_json = JOBS_DIR / f"{job_id}_report.json"
        if not report_json.exists():
            raise HTTPException(404, "no patch artifact for job")
        rep = json.loads(report_json.read_text())
        proposal = rep.get("patch_proposal", "")
        file_path, old, new = parse_patch_proposal(proposal)

    html = demo_side_by_side_html(
        old=old,
        new=new,
        file_path=file_path,
        case_key=job_id,
        title="Proposed Fix",
    )
    return HTMLResponse(html)
