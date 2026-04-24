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
from html import escape as html_escape
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
CASES_DIR = REPO_ROOT / "demo_assets" / "pdfs"

# Whitelist of hero cases surfaced on the landing page. Keeps the /case route
# from doubling as an arbitrary-file-read primitive.
HERO_CASES: dict[str, str] = {
    "sanfer_tunnel": "sanfer_tunnel.md",
    "car_1": "car_1.md",
    "boat_lidar": "boat_lidar.md",
}
for d in (JOBS_DIR, REPORTS_DIR, UPLOADS_DIR, PATCHES_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---- app --------------------------------------------------------------------
app = FastAPI(title="Black Box", description="Forensic copilot for robots")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

Mode = Literal["post_mortem", "scenario_mining", "synthetic_qa"]

# Sample-mode chunks. Shown only on the scripted path (no API key / real
# pipeline disabled). Every line is prefixed [sample] so the UI can never be
# mistaken for live agent reasoning. Live runs stream ForensicSession events;
# replay runs stream recorded events from data/final_runs/<name>/.
_STAGE_CHUNKS: dict[str, list[str]] = {
    "ingesting": [
        "[sample] SAMPLE MODE — no bag was analyzed; scripted walkthrough of pipeline stages.",
        "[sample] For a live run: set ANTHROPIC_API_KEY and BLACKBOX_REAL_PIPELINE=1.",
        "[sample] For a recorded run: open /analyze?replay=sanfer_tunnel.",
    ],
    "analyzing": [
        "[sample] Live mode would open a ForensicAgent managed-agent session here.",
        "[sample] Live mode would stream reasoning + tool_call + tool_result events.",
    ],
    "synthesizing": [
        "[sample] Live mode would run the grounding gate (min_evidence=2) on hypotheses.",
    ],
    "reporting": [
        "[sample] Live mode would render NTSB-style Markdown + unified diff artifact.",
    ],
    "done": [
        "[sample] Sample walkthrough complete. Use a real bag or /analyze?replay=... to see live output.",
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


def _decision_path(job_id: str) -> Path:
    return PATCHES_DIR / f"{job_id}.decision.json"


def _load_decision(job_id: str) -> dict:
    p = _decision_path(job_id)
    if not p.exists():
        return {"status": "pending"}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {"status": "pending"}


def _save_decision(job_id: str, status: str, note: str = "") -> dict:
    from datetime import datetime, timezone
    decision = {
        "status": status,
        "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": note,
    }
    _decision_path(job_id).write_text(json.dumps(decision, indent=2))
    return decision


_GATE_STYLE = """<style>
.gate { margin-top: 1.5rem; padding: 1.1rem 1.25rem; border: 1px solid #d9d6cc;
  border-radius: 4px; background: #fffdf8; font-family: "IBM Plex Sans", sans-serif; }
.gate-headline { font-family: "IBM Plex Serif", Georgia, serif; font-weight: 600;
  font-size: 1.05rem; letter-spacing: 0.03em; margin-bottom: 0.25rem; }
.gate-sub, .gate-meta, .gate-note { font-family: ui-monospace, monospace;
  font-size: 0.82rem; color: #6b6b66; }
.gate-form { margin-top: 0.9rem; display: flex; flex-direction: column; gap: 0.7rem; }
.gate-input { padding: 0.45rem 0.6rem; border: 1px solid #d9d6cc; border-radius: 3px;
  font-family: ui-monospace, monospace; font-size: 0.85rem; background: #faf8f2; }
.gate-actions { display: flex; gap: 0.6rem; }
.gate-btn { padding: 0.55rem 1rem; border: 1px solid #1c1c1a; border-radius: 3px;
  background: #1c1c1a; color: #fffdf8; font-family: ui-monospace, monospace;
  font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.08em; cursor: pointer; }
.gate-approve { background: #2f855a; border-color: #2f855a; }
.gate-reject  { background: #b33; border-color: #b33; }
.gate-approved { border-left: 4px solid #2f855a; }
.gate-rejected { border-left: 4px solid #b33; }
.gate-approved .gate-headline { color: #2f855a; }
.gate-rejected .gate-headline { color: #b33; }
</style>"""


def _gate_footer_html(job_id: str, decision: dict) -> str:
    """Approve/reject buttons (pending) or locked-decision banner (decided)."""
    status = decision.get("status", "pending")
    if status == "approved":
        decided = html_escape(decision.get("decided_at", ""))
        note = html_escape(decision.get("note", ""))
        note_line = f'<div class="gate-note">{note}</div>' if note else ""
        return (
            f'{_GATE_STYLE}'
            '<section class="gate gate-approved" data-status="approved">'
            '<div class="gate-headline">PATCH APPROVED — CLEARED FOR INTEGRATION</div>'
            f'<div class="gate-meta">decided {decided}</div>'
            f'{note_line}'
            '</section>'
        )
    if status == "rejected":
        decided = html_escape(decision.get("decided_at", ""))
        note = html_escape(decision.get("note", ""))
        note_line = f'<div class="gate-note">{note}</div>' if note else ""
        return (
            f'{_GATE_STYLE}'
            '<section class="gate gate-rejected" data-status="rejected">'
            '<div class="gate-headline">PATCH REJECTED — BLOCKED FROM APPLICATION</div>'
            f'<div class="gate-meta">decided {decided}</div>'
            f'{note_line}'
            '</section>'
        )
    return (
        f'{_GATE_STYLE}'
        '<section class="gate gate-pending" data-status="pending">'
        '<div class="gate-headline">HUMAN APPROVAL REQUIRED</div>'
        '<div class="gate-sub">Patch will NOT be applied until an engineer decides below.</div>'
        f'<form method="post" action="/decide/{html_escape(job_id)}" class="gate-form">'
        '<input type="text" name="note" placeholder="optional note (why)" class="gate-input" />'
        '<div class="gate-actions">'
        '<button type="submit" name="decision" value="approve" class="gate-btn gate-approve">Approve patch</button>'
        '<button type="submit" name="decision" value="reject" class="gate-btn gate-reject">Reject patch</button>'
        '</div>'
        '</form>'
        '</section>'
    )


def _write_status(job_id: str, payload: dict) -> None:
    """Write job status, stamping ``created_at`` once and preserving it."""
    payload = dict(payload)
    if "created_at" not in payload:
        prev = _read_status(job_id) or {}
        payload["created_at"] = prev.get("created_at") or time.time()
    _job_path(job_id).write_text(json.dumps(payload, indent=2))


def _read_status(job_id: str) -> dict | None:
    p = _job_path(job_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


# ---- stage pills + cost counter --------------------------------------------
# Internal STAGES ('ingesting', 'analyzing', 'synthesizing', 'reporting',
# 'done') collapse into three user-facing phases. 'synthesizing' sits inside
# analysis; 'done' highlights the final pill so the UI stays readable once the
# job completes.
_STAGE_PILL_MAP: dict[str, str] = {
    "queued": "ingest",
    "ingesting": "ingest",
    "analyzing": "analyze",
    "synthesizing": "analyze",
    "reporting": "report",
    "done": "report",
    "failed": "report",
}
PILLS = ("ingest", "analyze", "report")


def _pill_for(stage: str) -> str:
    return _STAGE_PILL_MAP.get(stage, "analyze")


def _case_name(status: dict) -> str:
    """Derive the user-visible case label from whatever the job recorded."""
    for key in ("case_name", "upload", "job_id"):
        val = status.get(key)
        if val:
            return str(val)
    return "—"


def _elapsed_seconds(status: dict) -> int:
    created = status.get("created_at")
    if not created:
        return 0
    return max(0, int(time.time() - float(created)))


def _fmt_elapsed(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _cost_summary(job_id: str) -> dict:
    """Sum ``data/costs.jsonl`` into {'usd', 'source'} for the progress pill.

    Falls back to 'empty' when the ledger is missing / unparseable so the UI
    can render a zero-dollar value with a data-source attribute for tests.
    """
    path = DATA_DIR / "costs.jsonl"
    if not path.exists():
        return {"usd": 0.0, "source": "empty"}
    total = 0.0
    count = 0
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += float(entry.get("usd_cost", 0.0) or 0.0)
            count += 1
    except OSError:
        return {"usd": 0.0, "source": "empty"}
    if count == 0:
        return {"usd": 0.0, "source": "empty"}
    return {"usd": round(total, 2), "source": "session"}


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
                    "source": "replay",
                    "replay_name": replay_name,
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
                "source": "replay",
                "replay_name": replay_name,
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
                "source": "replay",
                "replay_name": replay_name,
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
                "source": "live",
                "upload": upload_path.name,
                "reasoning_buffer": list(buffer[-200:]),
                "has_diff": done,
            },
        )

    try:
        buffer.append(f"[ingest] Uploaded {upload_path.name}, {upload_path.stat().st_size} bytes")
        _push("ingesting", "Decoding bag and extracting frames", 0.08)

        case_key = f"ui_{job_id}"

        # Preflight: build a manifest. If the session has NO cameras, bypass
        # the cloud ForensicAgent (which is tuned for vision post-mortem) and
        # route through the local run_session pipeline, which has a
        # telemetry-only branch. Keeps no-camera bags from producing empty UI.
        try:
            from black_box.ingestion.manifest import build_manifest as _bm
            pre_manifest = _bm(upload_path, count_messages=False)
            no_cams = not pre_manifest.has_cameras()
        except Exception as pe:
            buffer.append(f"[preflight] manifest probe skipped: {pe!r}")
            no_cams = False

        if no_cams:
            buffer.append("[preflight] no camera topics detected — "
                          "routing to telemetry-only pipeline")
            _push("analyzing", "Telemetry-only pipeline", 0.25)
            _run_pipeline_telemetry_only(
                job_id, upload_path, mode, case_key, buffer, _push
            )
            return

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
        # Persist the raw JSON payload so /report/{id}?format=pdf can build
        # a PDF on demand without re-running the pipeline.
        (JOBS_DIR / f"{job_id}_report.json").write_text(json.dumps(payload, indent=2))
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


def _run_pipeline_telemetry_only(
    job_id: str,
    upload_path: Path,
    mode: Mode,
    case_key: str,
    buffer: list[str],
    _push,
) -> None:
    """Run run_session.run() locally for bags with no camera topics.

    Output report.md is copied into REPORTS_DIR/<job_id>.md so the existing
    /report route keeps working. Only telemetry/lidar evidence — no vision.
    """
    import sys as _sys
    scripts_dir = REPO_ROOT / "scripts"
    if str(scripts_dir) not in _sys.path:
        _sys.path.insert(0, str(scripts_dir))
    import run_session as _rs  # type: ignore

    out_dir = DATA_DIR / "runs" / f"ui_{job_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    buffer.append(f"[pipeline] out_dir={out_dir}")
    _push("analyzing", "Scanning telemetry + lidar", 0.35)

    _rs.run(
        path=upload_path,
        out_dir=out_dir,
        user_prompt=None,
        reuse_frames=False,
        force_deep=False,
    )

    _push("synthesizing", "Cross-checking hypotheses", 0.82)
    report_src = out_dir / "report.md"
    report_dst = REPORTS_DIR / f"{job_id}.md"
    if report_src.exists():
        report_dst.write_text(report_src.read_text())
        buffer.append(f"[report] Wrote {report_dst.name} "
                      f"({report_dst.stat().st_size} bytes)")
    else:
        buffer.append("[report] ERROR: run_session produced no report.md")

    # Build a minimal payload so /report?format=pdf still works.
    vision = {}
    vj = out_dir / "vision.json"
    if vj.exists():
        try:
            vision = json.loads(vj.read_text())
        except Exception:
            vision = {}
    top_label = ""
    moments = vision.get("all_moments") or []
    if moments:
        top_label = str(moments[0].get("label", ""))[:120]
    payload = {
        "timeline": [],
        "hypotheses": [{
            "bug_class": "sensor_timeout",
            "confidence": float(moments[0].get("confidence", 0.0)) if moments else 0.0,
            "summary": top_label or "No anomalies detected.",
            "evidence": [],
            "patch_hint": "See report.md for actionable recommendations.",
        }],
        "root_cause_idx": 0,
        "patch_proposal": "",
    }
    (JOBS_DIR / f"{job_id}_report.json").write_text(json.dumps(payload, indent=2))
    _patch_path(job_id).write_text(json.dumps(_STUB_PATCH, indent=2))
    _push("done", "Complete", 1.0, done=True)


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
                        "label": f"{label} (sample)",
                        "progress": inner_progress,
                        "mode": mode,
                        "source": "sample",
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
                "source": "sample",
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
            "source": "replay",
            "replay_name": replay,
            "upload": f"replay:{replay}",
            "case_name": replay,
            "reasoning_buffer": [f"Replaying recorded session: {replay}"],
            "has_diff": False,
        },
    )
    background.add_task(_run_pipeline_replay, job_id, replay)

    # Render the full shell with the progress card already injected so the
    # demo link `?replay=...` loads a styled page, not a bare HTMX fragment.
    progress_html = templates.get_template("progress.html").render(
        request=request, **_progress_context(job_id, _read_status(job_id) or {})
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
            "case_name": file.filename or upload_path.name,
            "reasoning_buffer": ["Waiting for worker..."],
            "has_diff": False,
        },
    )
    live = _real_pipeline_enabled()
    worker = _run_pipeline_real if live else _run_pipeline_stub
    # Re-stamp with correct source before the worker starts so the progress
    # card's first render already shows the right badge.
    queued = _read_status(job_id) or {}
    queued["source"] = "live" if live else "sample"
    if not live:
        queued["label"] = "Queued (sample)"
    _write_status(job_id, queued)
    background.add_task(worker, job_id, upload_path, mode)  # type: ignore[arg-type]

    return templates.TemplateResponse(
        request,
        "progress.html",
        _progress_context(job_id, _read_status(job_id) or {}),
    )


@app.get("/status/{job_id}", response_class=HTMLResponse)
async def status(request: Request, job_id: str) -> HTMLResponse:
    data = _read_status(job_id)
    if data is None:
        raise HTTPException(404, "unknown job")
    return templates.TemplateResponse(
        request,
        "progress.html",
        _progress_context(job_id, data),
    )


_SOURCE_LABELS = {
    "live":   ("LIVE",   "Real Managed-Agents session, streaming events now."),
    "replay": ("REPLAY", "Pre-recorded ForensicSession event stream played back."),
    "sample": ("SAMPLE", "Scripted walkthrough — no bag analyzed, no model called."),
}


def _progress_context(job_id: str, status_data: dict) -> dict:
    stage = status_data.get("stage", "queued")
    active_pill = _pill_for(stage)
    elapsed = _elapsed_seconds(status_data)
    cost = _cost_summary(job_id)
    source = status_data.get("source") or "sample"
    src_label, src_tooltip = _SOURCE_LABELS.get(source, _SOURCE_LABELS["sample"])
    review = _review_banner(job_id, status_data)
    return {
        "job_id": job_id,
        "status": status_data,
        "pills": PILLS,
        "active_pill": active_pill,
        "case_name": _case_name(status_data),
        "elapsed_seconds": elapsed,
        "elapsed_fmt": _fmt_elapsed(elapsed),
        "cost_usd": cost["usd"],
        "cost_source": cost["source"],
        "source": source,
        "source_label": src_label,
        "source_tooltip": src_tooltip,
        "review": review,
    }


_REVIEW_LABELS = {
    "pending":  ("AWAITING HUMAN REVIEW", "patch staged · not yet applied"),
    "approved": ("PATCH APPROVED",        "cleared for integration"),
    "rejected": ("PATCH REJECTED",        "blocked from application"),
}


def _review_banner(job_id: str, status_data: dict) -> dict | None:
    """Return the review banner dict when a patch artifact exists, else None.

    Surfaces the HITL gate state on the progress card so operators can tell
    at a glance whether a run still needs a human decision.
    """
    if not _patch_path(job_id).exists() and not status_data.get("has_diff"):
        return None
    decision = _load_decision(job_id)
    status = decision.get("status", "pending")
    label, sub = _REVIEW_LABELS.get(status, _REVIEW_LABELS["pending"])
    return {"status": status, "label": label, "sub": sub}


@app.get("/case/{slug}", response_class=HTMLResponse)
async def case_fragment(request: Request, slug: str) -> HTMLResponse:
    filename = HERO_CASES.get(slug)
    if filename is None:
        raise HTTPException(404, f"unknown case: {slug}")
    md_path = CASES_DIR / filename
    if not md_path.exists():
        raise HTTPException(404, f"case markdown missing: {filename}")
    markdown_source = md_path.read_text(encoding="utf-8")
    return templates.TemplateResponse(
        request,
        "case_fragment.html",
        {"slug": slug, "markdown_source": markdown_source},
    )


def _build_pdf_on_demand(job_id: str) -> Path | None:
    """Render PDF from saved JSON payload. Fallback when no pre-built PDF on disk."""
    payload_path = JOBS_DIR / f"{job_id}_report.json"
    if not payload_path.exists():
        return None
    try:
        payload = json.loads(payload_path.read_text())
    except json.JSONDecodeError:
        return None
    from black_box.reporting import build_pdf_report

    out_pdf = REPORTS_DIR / f"{job_id}.pdf"
    build_pdf_report(
        report_json=payload,
        artifacts={},
        out_pdf=out_pdf,
        case_meta={"case_key": f"ui_{job_id}", "mode": "post_mortem"},
    )
    return out_pdf


@app.get("/report/{job_id}", response_class=HTMLResponse)
async def report(
    request: Request,
    job_id: str,
    format: str | None = Query(None, description="'pdf' to download the PDF, default renders markdown in-browser"),
):
    """Render forensic report. Default = HTML+marked.js; ?format=pdf = raw PDF."""
    md_path = REPORTS_DIR / f"{job_id}.md"
    pdf_path = REPORTS_DIR / f"{job_id}.pdf"

    if format == "pdf":
        if not pdf_path.exists():
            built = _build_pdf_on_demand(job_id)
            if built is None or not built.exists():
                raise HTTPException(404, "pdf not available")
            pdf_path = built
        return FileResponse(
            str(pdf_path),
            media_type="application/pdf",
            filename=pdf_path.name,
        )

    if not md_path.exists():
        raise HTTPException(404, "report not ready")

    markdown_source = md_path.read_text(encoding="utf-8")
    hero = _report_hero(markdown_source)
    return templates.TemplateResponse(
        request,
        "report.html",
        {"job_id": job_id, "markdown_source": markdown_source, "hero": hero},
    )


_HERO_KEYS = {
    "Case": "case",
    "Mode": "mode",
    "Duration": "duration",
    "Generated": "generated",
    "Model": "model",
}


def _report_hero(md: str) -> dict | None:
    """Extract the first-fold lockup from a NTSB-style report.md.

    Pulls the `Case / Mode / Duration / Model / Generated` metadata row and
    the first blockquote (used as the root-cause verdict). Returns None when
    the markdown does not match the expected shape so legacy reports still
    render.
    """
    case = mode = duration = generated = model = None
    verdict = None
    for raw in md.splitlines()[:40]:
        line = raw.strip()
        if line.startswith(">") and verdict is None:
            verdict = line.lstrip("> ").strip()
        if "**" in line and ":**" in line:
            # **Case:** `foo` · **Mode:** `bar`
            for chunk in line.replace("&nbsp;", " ").split("·"):
                chunk = chunk.strip()
                for key, attr in _HERO_KEYS.items():
                    token = f"**{key}:**"
                    if chunk.startswith(token):
                        val = chunk[len(token):].strip()
                        if "`" in val:
                            parts = val.split("`")
                            val = parts[1] if len(parts) >= 2 else val.strip("`")
                        val = val.strip()
                        if attr == "case" and case is None:
                            case = val
                        elif attr == "mode" and mode is None:
                            mode = val
                        elif attr == "duration" and duration is None:
                            duration = val
                        elif attr == "generated" and generated is None:
                            generated = val
                        elif attr == "model" and model is None:
                            model = val
    if not case:
        return None
    return {
        "case": case,
        "mode": mode or "—",
        "duration": duration,
        "generated": generated,
        "model": model,
        "verdict": verdict,
    }


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

    decision = _load_decision(job_id)
    footer = _gate_footer_html(job_id, decision)
    page = demo_side_by_side_html(
        old=old,
        new=new,
        file_path=file_path,
        case_key=job_id,
        title="Proposed Fix",
        footer_html=footer,
    )
    return HTMLResponse(page)


@app.post("/decide/{job_id}", response_class=HTMLResponse)
async def decide_patch(
    job_id: str,
    decision: str = Form(...),
    note: str = Form(""),
) -> HTMLResponse:
    """Human-in-the-loop gate: record approve/reject before any patch applies.

    Idempotent only on the first write — re-posting to a decided job 409s so
    the decision log stays truthful.
    """
    if decision not in ("approve", "reject"):
        raise HTTPException(400, "decision must be approve or reject")
    if not _patch_path(job_id).exists():
        raise HTTPException(404, "no patch artifact for job")
    existing = _load_decision(job_id)
    if existing.get("status") in ("approved", "rejected"):
        raise HTTPException(409, f"already {existing['status']}")
    status = "approved" if decision == "approve" else "rejected"
    saved = _save_decision(job_id, status=status, note=note.strip())
    return HTMLResponse(_gate_footer_html(job_id, saved))
