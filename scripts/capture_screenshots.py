"""Capture the three demo UI screenshots into ``docs/assets/ui_*.png``.

Boots the FastAPI app on a private port, seeds fixture job states to the
runtime ``data/jobs/`` dir so /status/{id} renders, drives a headless
Chromium through three states, writes PNGs at 1280x800, tears down the
server.

Usage
-----
    python scripts/capture_screenshots.py

Requirements: ``playwright`` (already installed in project venv) and the
Chromium browser (``playwright install chromium`` one-off).

Honesty note: this is the reproducible recipe for the README screenshots.
If the Chromium binary isn't present, the script prints an install hint
and exits non-zero rather than writing stub PNGs.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ASSETS = REPO_ROOT / "docs" / "assets"
JOBS_DIR = REPO_ROOT / "data" / "jobs"
PATCHES_DIR = REPO_ROOT / "data" / "patches"
REPORTS_DIR = REPO_ROOT / "data" / "reports"

VIEWPORT = {"width": 1280, "height": 800}

# Mid-stream reasoning buffer — mirrors the stub worker's analyzing stage
# chunks so the screenshot is an honest rendering of what a user sees.
PROGRESS_BUFFER = [
    "[ingesting] Opening recording and enumerating topics...",
    "[ingesting] Found /imu (100 Hz), /cam_{front,left,right,back,top} (10 Hz), /joint_states.",
    "[ingesting] Decoded 3.2 s of telemetry; sampling frames at 10 fps across 5 cameras.",
    "[analyzing] Pulled 5-camera composite at t=1.8s (telemetry delta flagged this window).",
    "[analyzing] Claude call 1: cross-view reasoning over 5 thumbnails + IMU window.",
    "[analyzing] IMU pitch slope = -0.42 rad/s; /joint/LHipPitch command at +2.5 while joint saturates.",
    "[analyzing] Working theory: PID integral wind-up on hip pitch during step initiation.",
]

DONE_BUFFER = PROGRESS_BUFFER + [
    "[synthesizing] Grounding gate: 3/3 hypotheses meet min_evidence=2 (telemetry + camera).",
    "[synthesizing] Cross-source corroboration: cameras {front, left} + /imu + pid_controller.cpp.",
    "[reporting] Rendering annotated frames with bbox overlays on hip joint...",
    "[reporting] Generating unified diff against pid_controller.cpp...",
    "[reporting] Writing NTSB-style Markdown to data/reports/{job}.md.",
    "[done] Done. Root cause: pid_saturation (confidence 0.82). Patch: clamp integral ±1.0.",
]

REPORT_MD = """# Incident Report — ui-demo

**Case:** ui-demo  **Mode:** post_mortem  **Duration:** 3.2s

## Executive summary

Root cause: PID integral wind-up on LHipPitch during step initiation.
Confidence 0.82. Proposed fix: clamp integral term to ±1.0 and add output
saturation.

## Evidence
- Telemetry: IMU pitch slope -0.42 rad/s at t=1.8s
- Camera: 5-view composite at t=1.8s shows hip joint saturating
- Source: pid_controller.cpp line 23 (no integral clamp)

## Proposed patch
See `patches/ui-demo.json` (clamp integral + clamp output).
"""


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_up(base: str, timeout: float = 15.0) -> None:
    import urllib.request
    import urllib.error
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(base + "/", timeout=1.0) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.2)
    raise TimeoutError(f"uvicorn did not come up at {base}")


def _seed_progress_job(job_id: str) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    (JOBS_DIR / f"{job_id}.json").write_text(json.dumps({
        "job_id": job_id,
        "stage": "analyzing",
        "label": "Claude is reviewing evidence",
        "progress": 0.42,
        "mode": "post_mortem",
        "upload": "demo_session.bag",
        "reasoning_buffer": PROGRESS_BUFFER,
        "has_diff": False,
    }))


def _seed_done_job(job_id: str) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    PATCHES_DIR.mkdir(parents=True, exist_ok=True)
    (JOBS_DIR / f"{job_id}.json").write_text(json.dumps({
        "job_id": job_id,
        "stage": "done",
        "label": "Complete",
        "progress": 1.0,
        "mode": "post_mortem",
        "upload": "demo_session.bag",
        "reasoning_buffer": DONE_BUFFER,
        "has_diff": True,
    }))
    (REPORTS_DIR / f"{job_id}.md").write_text(REPORT_MD)
    (PATCHES_DIR / f"{job_id}.json").write_text(json.dumps({
        "file_path": "src/controllers/pid_controller.cpp",
        "old": "integral_ += error * dt;\n",
        "new": "integral_ += error * dt;\nintegral_ = std::clamp(integral_, -1.0, 1.0);\n",
    }, indent=2))


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed. `pip install playwright && playwright install chromium`", file=sys.stderr)
        return 2

    DOCS_ASSETS.mkdir(parents=True, exist_ok=True)
    port = _free_port()
    base = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (os.pathsep + env.get("PYTHONPATH", "") if env.get("PYTHONPATH") else "")
    # Make sure we never accidentally trigger the live Anthropic pipeline
    # while capturing demo frames.
    env.pop("BLACKBOX_REAL_PIPELINE", None)

    cmd = [
        sys.executable, "-m", "uvicorn",
        "black_box.ui.app:app",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--log-level", "warning",
    ]
    proc = subprocess.Popen(cmd, env=env, cwd=str(REPO_ROOT))
    try:
        _wait_up(base)

        progress_id = "ui" + uuid.uuid4().hex[:8]
        done_id = "ui" + uuid.uuid4().hex[:8]
        _seed_progress_job(progress_id)
        _seed_done_job(done_id)

        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True)
            except Exception as e:
                print(f"ERROR: could not launch chromium ({e}). Run `playwright install chromium`.", file=sys.stderr)
                return 3
            ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
            page = ctx.new_page()

            targets = [
                ("ui_upload.png", f"{base}/"),
                ("ui_progress.png", f"{base}/status/{progress_id}"),
                ("ui_report.png", f"{base}/status/{done_id}"),
            ]
            for name, url in targets:
                page.goto(url, wait_until="networkidle")
                # Stop HTMX polling so we don't race a 1s refresh during capture.
                page.evaluate("() => { if (window.htmx) { window.htmx.config.defaultFocusScroll = false; } }")
                # For progress/report pages, the progress card is a raw
                # fragment — wrap it in the same main column so the shot
                # reads like a real page, not a bare <div>.
                if "/status/" in url:
                    page.evaluate(
                        """() => {
                          if (document.querySelector('main')) return;
                          const body = document.body;
                          const card = body.firstElementChild;
                          const shell = document.createElement('main');
                          const header = document.createElement('header');
                          header.innerHTML = '<h1>Black Box</h1><p class=\"sub\">A forensic copilot for robots.</p>';
                          shell.appendChild(header);
                          shell.appendChild(card);
                          body.innerHTML = '';
                          body.appendChild(shell);
                          const link = document.createElement('link');
                          link.rel = 'stylesheet';
                          link.href = '/static/style.css';
                          document.head.appendChild(link);
                        }"""
                    )
                    page.wait_for_load_state("networkidle")
                # Disable live polling/cursor animation to get a stable frame.
                page.evaluate("() => document.querySelectorAll('[hx-get]').forEach(el => el.removeAttribute('hx-get'))")
                # For the "report" (done) state, scroll the reasoning pre to
                # the bottom so the money-shot "Root cause" line is visible.
                if name == "ui_report.png":
                    page.evaluate(
                        """() => {
                          const pre = document.getElementById('reasoning-pre');
                          if (pre) { pre.scrollTop = pre.scrollHeight; }
                        }"""
                    )
                page.wait_for_timeout(400)
                out = DOCS_ASSETS / name
                page.screenshot(path=str(out), full_page=False)
                size = out.stat().st_size
                print(f"wrote {out.relative_to(REPO_ROOT)} ({size} bytes)")

            ctx.close()
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
