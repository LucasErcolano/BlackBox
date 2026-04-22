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

# ---- paths ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent.parent  # src/black_box/ui -> repo root
DATA_DIR = REPO_ROOT / "data"
JOBS_DIR = DATA_DIR / "jobs"
REPORTS_DIR = DATA_DIR / "reports"
UPLOADS_DIR = DATA_DIR / "uploads"
for d in (JOBS_DIR, REPORTS_DIR, UPLOADS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---- app --------------------------------------------------------------------
app = FastAPI(title="Black Box", description="Forensic copilot for robots")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

Mode = Literal["post_mortem", "scenario_mining", "synthetic_qa"]

STAGES = [
    ("ingesting", "Decoding bag and extracting frames"),
    ("analyzing", "Claude is reviewing evidence"),
    ("synthesizing", "Cross-checking hypotheses"),
    ("reporting", "Rendering PDF report"),
    ("done", "Complete"),
]


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


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
    """Fake pipeline: walks through stages with sleeps.

    TODO(pipeline): wire real ingestion -> claude -> reporting here.
    """
    try:
        for stage, label in STAGES:
            reasoning = f"[{mode}] {label} for {upload_path.name}..."
            _write_status(
                job_id,
                {
                    "job_id": job_id,
                    "stage": stage,
                    "label": label,
                    "progress": (STAGES.index((stage, label)) + 1) / len(STAGES),
                    "mode": mode,
                    "upload": str(upload_path.name),
                    "reasoning": reasoning,
                },
            )
            if stage != "done":
                time.sleep(2)
    except Exception as e:  # pragma: no cover - defensive
        _write_status(
            job_id,
            {
                "job_id": job_id,
                "stage": "failed",
                "label": "Pipeline error",
                "progress": 0.0,
                "mode": mode,
                "reasoning": f"ERROR: {e!r}",
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
            "reasoning": "Waiting for worker...",
        },
    )
    background.add_task(_run_pipeline_stub, job_id, upload_path, mode)  # type: ignore[arg-type]

    # Return the progress fragment so HTMX swaps it into #result
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
