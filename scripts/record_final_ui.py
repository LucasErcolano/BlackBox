# SPDX-License-Identifier: MIT
"""Record polished UI sequence for final demo.

Phases (frame index ranges captured for clean subclip slicing):
  1. intake          -> /
  2. analysis_start  -> htmx.ajax /analyze?replay=sanfer_tunnel into #main-panel
  3. agent_stream    -> same page, watch live panel update
  4. report          -> /report?case=sanfer_tunnel
  5. patch_review    -> /diff/<job_id>

Outputs PNG frames + phase index json. Encoding to mp4 is done by the wrapper
shell script.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path("video_assets/final_ui_capture/_frames")
INDEX_JSON = Path("video_assets/final_ui_capture/_phase_index.json")
BASE = "http://127.0.0.1:8765"
FPS = 10
WIDTH, HEIGHT = 1920, 1080

# Phase durations in seconds. Sum ~= 65s for the main clip.
PHASES = [
    ("intake",          10),
    ("analysis_start",   6),
    ("agent_stream",    22),
    ("report",          15),
    ("patch_review",    12),
]


def _shoot(page, idx: int) -> None:
    page.screenshot(path=str(OUT_DIR / f"f_{idx:05d}.png"),
                    full_page=False, type="png", animations="disabled")


def _phase(page, name: str, secs: int, start_idx: int) -> int:
    n = FPS * secs
    dt = 1.0 / FPS
    t0 = time.monotonic()
    for i in range(n):
        target = t0 + (i + 1) * dt
        _shoot(page, start_idx + i)
        if name == "report" and i == int(FPS * 4):
            # Mid-phase: scroll to evidence cards.
            page.evaluate("window.scrollTo({top: 600, behavior:'instant'})")
        if name == "report" and i == int(FPS * 9):
            page.evaluate("window.scrollTo({top: 1500, behavior:'instant'})")
        if name == "patch_review" and i == int(FPS * 6):
            page.evaluate("window.scrollTo({top: 800, behavior:'instant'})")
        now = time.monotonic()
        if now < target:
            time.sleep(target - now)
    return start_idx + n


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p in OUT_DIR.glob("*.png"):
        p.unlink()

    phase_ranges: dict[str, tuple[int, int]] = {}
    job_id: str | None = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": WIDTH, "height": HEIGHT},
                                  device_scale_factor=1)
        page = ctx.new_page()

        # 1. Intake screen
        page.goto(f"{BASE}/", wait_until="networkidle")
        time.sleep(0.6)
        idx = 0
        start = idx
        idx = _phase(page, "intake", PHASES[0][1], idx)
        phase_ranges["intake"] = (start, idx)

        # 2. Analysis start: trigger replay via htmx so we keep the app shell.
        page.evaluate(
            "htmx.ajax('GET', '/analyze?replay=sanfer_tunnel',"
            " {target:'#main-panel', swap:'outerHTML'})"
        )
        # Give htmx 1 tick to swap so the panel is visible immediately.
        time.sleep(0.4)
        # Pull job_id out of the swapped panel for later /diff route. The
        # panel's hx-get attr names the status route — search the live DOM
        # over a few polls because htmx may still be swapping.
        for _ in range(30):
            try:
                html = page.content()
                m = re.search(r"/status/([a-f0-9]{8,})", html)
                if m:
                    job_id = m.group(1)
                    break
            except Exception:
                pass
            time.sleep(0.1)
        start = idx
        idx = _phase(page, "analysis_start", PHASES[1][1], idx)
        phase_ranges["analysis_start"] = (start, idx)

        # 3. Agent stream — keep watching same page, htmx polls /status.
        start = idx
        idx = _phase(page, "agent_stream", PHASES[2][1], idx)
        phase_ranges["agent_stream"] = (start, idx)

        # Recheck job_id in case htmx reswapped to a different node.
        if job_id is None:
            try:
                html = page.content()
                m = re.search(r"/status/([a-f0-9]+)", html)
                if m:
                    job_id = m.group(1)
            except Exception:
                pass

        # 4. Report
        page.goto(f"{BASE}/report?case=sanfer_tunnel", wait_until="networkidle")
        time.sleep(0.6)
        page.evaluate("window.scrollTo({top:0})")
        start = idx
        idx = _phase(page, "report", PHASES[3][1], idx)
        phase_ranges["report"] = (start, idx)

        # 5. Patch review (diff). If we never caught a job_id from the live
        # panel, fall back to the most recently produced patch artifact.
        if job_id is None:
            patches = sorted(Path("data/patches").glob("*.json"),
                             key=lambda p: p.stat().st_mtime, reverse=True)
            if patches:
                job_id = patches[0].stem
        if job_id:
            page.goto(f"{BASE}/diff/{job_id}", wait_until="networkidle")
        else:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.6)
        start = idx
        idx = _phase(page, "patch_review", PHASES[4][1], idx)
        phase_ranges["patch_review"] = (start, idx)

        browser.close()

    INDEX_JSON.parent.mkdir(parents=True, exist_ok=True)
    INDEX_JSON.write_text(json.dumps({
        "fps": FPS,
        "width": WIDTH,
        "height": HEIGHT,
        "job_id": job_id,
        "phases": {k: {"start": s, "end": e, "secs": (e - s) / FPS}
                   for k, (s, e) in phase_ranges.items()},
        "total_frames": idx,
    }, indent=2))
    print(f"captured {idx} frames; job_id={job_id}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
