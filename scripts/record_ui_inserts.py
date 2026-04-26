# SPDX-License-Identifier: MIT
"""Record short UI feature inserts.

Inserts:
  1. memory          -> intake page memory card (/)
  2. steering        -> /analyze?replay=sanfer_tunnel + POST /steer + GET /steer history
  3. hitl_patch      -> /diff/f748de9e40ca with APPROVE/REJECT gate
  4. rollback        -> /checkpoints
  5. evidence_trace  -> /trace/f748de9e40ca

Outputs PNG frames + phase index json. Encoding handled by wrapper script.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path("video_assets/ui_feature_inserts/_frames")
INDEX_JSON = Path("video_assets/ui_feature_inserts/_phase_index.json")
BASE = "http://127.0.0.1:8765"
FPS = 30
WIDTH, HEIGHT = 1920, 1080
PATCH_JOB = "f748de9e40ca"

DARK_CSS = """
:root {
  --bg: #0e0f0a !important;
  --bg-2: #15170f !important;
  --surface: #1d1f17 !important;
  --ink: #e8e3d4 !important;
  --ink-2: #cec9b8 !important;
  --muted: #9a9786 !important;
  --line: #2a2c22 !important;
  --rule: #3a3c30 !important;
  --accent-soft: #1f2e22 !important;
  --console-bg: #0a0b07 !important;
  --console-bg-2: #131509 !important;
}
html, body { background: #0e0f0a !important; color: #e8e3d4 !important; }
input, select, textarea, button { background: #1d1f17 !important; color: #e8e3d4 !important; border-color: #3a3c30 !important; }
table, th, td { border-color: #2a2c22 !important; }
"""

DARK_INIT_JS = """
(() => {
  const css = %s;
  const apply = () => {
    if (document.getElementById('bb-dark-style')) return;
    const s = document.createElement('style');
    s.id = 'bb-dark-style';
    s.textContent = css;
    (document.head || document.documentElement).appendChild(s);
  };
  if (document.readyState !== 'loading') apply();
  else document.addEventListener('DOMContentLoaded', apply);
})();
""" % json.dumps(DARK_CSS)

PHASES = [
    ("memory",          7),
    ("steering",       11),
    ("hitl_patch",     10),
    ("rollback",        8),
    ("evidence_trace",  8),
]


def _shoot(page, idx: int) -> None:
    page.screenshot(path=str(OUT_DIR / f"f_{idx:05d}.png"),
                    full_page=False, type="png", animations="disabled")


def _phase(page, name: str, secs: int, start_idx: int, *, hooks=None) -> int:
    n = FPS * secs
    dt = 1.0 / FPS
    t0 = time.monotonic()
    for i in range(n):
        target = t0 + (i + 1) * dt
        if hooks:
            hooks(page, name, i)
        _shoot(page, start_idx + i)
        now = time.monotonic()
        if now < target:
            time.sleep(target - now)
    return start_idx + n


def _hooks(page, name: str, i: int) -> None:
    if name == "hitl_patch" and i == FPS * 4:
        page.evaluate("window.scrollTo({top: 600, behavior:'instant'})")
    if name == "evidence_trace" and i == FPS * 4:
        page.evaluate("window.scrollTo({top: 400, behavior:'instant'})")
    if name == "rollback" and i == FPS * 4:
        # Hover the rollback button to highlight the action.
        try:
            page.locator("button.gate-reject").first.hover()
        except Exception:
            pass


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p in OUT_DIR.glob("*.png"):
        p.unlink()

    phase_ranges: dict[str, tuple[int, int]] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": WIDTH, "height": HEIGHT},
                                  device_scale_factor=1)
        ctx.add_init_script(DARK_INIT_JS)
        page = ctx.new_page()
        idx = 0

        # 1. memory — intake page memory card
        page.goto(f"{BASE}/", wait_until="networkidle")
        time.sleep(0.6)
        # Scroll memory card into prominent view if present.
        page.evaluate(
            "const el=document.querySelector('.memory-card');"
            "if(el){el.scrollIntoView({behavior:'instant',block:'center'});}"
        )
        time.sleep(0.3)
        start = idx
        idx = _phase(page, "memory", PHASES[0][1], idx)
        phase_ranges["memory"] = (start, idx)

        # 2. steering — replay then post a steer; show audit history.
        page.goto(f"{BASE}/", wait_until="networkidle")
        page.evaluate(
            "htmx.ajax('GET', '/analyze?replay=sanfer_tunnel',"
            " {target:'#main-panel', swap:'outerHTML'})"
        )
        time.sleep(0.6)
        # Capture the live job_id from the swapped panel.
        replay_job = None
        for _ in range(40):
            html = page.content()
            m = re.search(r"/status/([a-f0-9]{8,})", html)
            if m:
                replay_job = m.group(1)
                break
            time.sleep(0.1)
        # Show the live panel briefly, then submit a steer message via JS
        # FormData POST and surface its rendered confirmation by navigating
        # to GET /steer/<job_id> (audit history list).
        steering_msg = (
            "Focus on whether the operator's tunnel hypothesis is "
            "supported by telemetry."
        )

        def steering_hooks(page, _name: str, i: int) -> None:
            if i == FPS * 4 and replay_job:
                page.evaluate(
                    """async (args) => {
                        const fd = new FormData();
                        fd.append('message', args.msg);
                        fd.append('operator', 'lucas');
                        await fetch('/steer/' + args.job, {method:'POST', body: fd});
                    }""",
                    {"msg": steering_msg, "job": replay_job},
                )
            if i == FPS * 7 and replay_job:
                # Navigate to the steer history route so the queued message
                # is visible on screen.
                page.goto(f"{BASE}/steer/{replay_job}", wait_until="networkidle")

        start = idx
        idx = _phase(page, "steering", PHASES[1][1], idx, hooks=steering_hooks)
        phase_ranges["steering"] = (start, idx)

        # 3. hitl_patch — /diff with APPROVE/REJECT gate
        page.goto(f"{BASE}/diff/{PATCH_JOB}", wait_until="networkidle")
        time.sleep(0.5)
        page.evaluate("window.scrollTo({top: 0})")
        start = idx
        idx = _phase(page, "hitl_patch", PHASES[2][1], idx, hooks=_hooks)
        phase_ranges["hitl_patch"] = (start, idx)

        # 4. rollback — /checkpoints timeline
        page.goto(f"{BASE}/checkpoints", wait_until="networkidle")
        time.sleep(0.4)
        start = idx
        idx = _phase(page, "rollback", PHASES[3][1], idx, hooks=_hooks)
        phase_ranges["rollback"] = (start, idx)

        # 5. evidence_trace — /trace/<job_id>
        page.goto(f"{BASE}/trace/{PATCH_JOB}", wait_until="networkidle")
        time.sleep(0.4)
        page.evaluate("window.scrollTo({top: 0})")
        start = idx
        idx = _phase(page, "evidence_trace", PHASES[4][1], idx, hooks=_hooks)
        phase_ranges["evidence_trace"] = (start, idx)

        browser.close()

    INDEX_JSON.parent.mkdir(parents=True, exist_ok=True)
    INDEX_JSON.write_text(json.dumps({
        "fps": FPS,
        "width": WIDTH,
        "height": HEIGHT,
        "phases": {k: {"start": s, "end": e, "secs": (e - s) / FPS}
                   for k, (s, e) in phase_ranges.items()},
        "total_frames": idx,
    }, indent=2))
    print(f"captured {idx} frames", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
