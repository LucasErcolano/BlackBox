"""Black Box FastAPI + HTMX front-end.

Serves a sober, single-column upload UI for forensic analysis jobs.
The background task is currently a stub that walks through fake stages
and writes JSON status files to ``data/jobs/{job_id}.json``.

TODO(pipeline): replace ``_run_pipeline_stub`` with the real wiring:
    ingestion.extract(bag) -> claude_client.analyze(mode) -> reporting.render_pdf()
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
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
        "Writing NTSB-style PDF to data/reports/{job}.pdf.",
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
    background.add_task(_run_pipeline_stub, job_id, upload_path, mode)  # type: ignore[arg-type]

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
    pdf = REPORTS_DIR / f"{job_id}.pdf"
    if not pdf.exists():
        raise HTTPException(404, "report not ready")
    return FileResponse(str(pdf), media_type="application/pdf", filename=pdf.name)


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
