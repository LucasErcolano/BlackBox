"""Capture real UI screen recordings via Playwright."""
import time
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765"
OUT = Path("demo_assets/editor_raw_footage_pack/_work/raw_webm")
OUT.mkdir(parents=True, exist_ok=True)
STILLS = Path("demo_assets/editor_raw_footage_pack/stills")
STILLS.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080


def smooth_scroll(page, total, step=40, delay=0.04):
    done = 0
    while done < total:
        d = min(step, total - done)
        page.mouse.wheel(0, d)
        time.sleep(delay)
        done += d


def record(name, fn, duration_min=6.0):
    """Record one clip. fn(page) drives the interaction."""
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            device_scale_factor=1,
            record_video_dir=str(OUT / name),
            record_video_size={"width": W, "height": H},
        )
        page = ctx.new_page()
        start = time.time()
        try:
            fn(page)
        except Exception as e:
            print(f"  ! {name}: {e}", flush=True)
        elapsed = time.time() - start
        if elapsed < duration_min:
            time.sleep(duration_min - elapsed)
        page.close()
        ctx.close()
        browser.close()
    # find the recorded webm
    webms = list((OUT / name).rglob("*.webm"))
    if webms:
        target = OUT / f"{name}.webm"
        webms[0].rename(target)
        print(f"  -> {target} ({target.stat().st_size//1024} KB)")
    return name


# --- Clip drivers ---

def c01_intake(page):
    page.goto(BASE + "/", wait_until="networkidle")
    time.sleep(2)
    # hover mode cards
    for sel in ["text=Forensic post-mortem", "text=Scenario mining", "text=Synthetic QA"]:
        try:
            page.locator(sel).first.hover(timeout=2000)
            time.sleep(1.0)
        except Exception:
            pass
    # scroll a tiny bit
    smooth_scroll(page, 200)
    time.sleep(1.5)
    smooth_scroll(page, -200, step=-40, delay=0.04)
    time.sleep(1.0)
    page.screenshot(path=str(STILLS / "intake_capture.png"), full_page=False)


def c02_live(page):
    # trigger replay
    page.goto(BASE + "/analyze?replay=sanfer_tunnel", wait_until="domcontentloaded")
    time.sleep(2)
    # let live panel fetch / poll
    for _ in range(18):
        time.sleep(1)
        try:
            smooth_scroll(page, 30)
        except Exception:
            pass


def c03_managed_agent(page):
    # /trace/{job_id} — need a job. Use replay first.
    page.goto(BASE + "/analyze?replay=sanfer_tunnel", wait_until="domcontentloaded")
    time.sleep(3)
    # try to extract job_id from URL or DOM
    job_id = None
    try:
        html = page.content()
        import re
        m = re.search(r"/status/([a-f0-9]{12})", html) or re.search(r"job[_-]?id[\"'>: ]+([a-f0-9]{12})", html)
        if m:
            job_id = m.group(1)
    except Exception:
        pass
    if job_id:
        page.goto(f"{BASE}/trace/{job_id}", wait_until="domcontentloaded")
    else:
        page.goto(f"{BASE}/checkpoints", wait_until="domcontentloaded")
    time.sleep(3)
    smooth_scroll(page, 600)
    time.sleep(2)
    smooth_scroll(page, -300, step=-40)
    time.sleep(1)


def c04_report_overview(page):
    page.goto(BASE + "/report?case=case_2026_04_18_sanfer", wait_until="networkidle")
    time.sleep(2.5)
    smooth_scroll(page, 600, step=20, delay=0.05)
    time.sleep(2)


def c05_report_exhibits(page):
    page.goto(BASE + "/report?case=case_2026_04_18_sanfer", wait_until="networkidle")
    time.sleep(2)
    smooth_scroll(page, 1200, step=20, delay=0.04)
    time.sleep(2)
    # try clicking exhibit tabs if present
    for sel in ["text=Telemetry", "text=Cameras", "text=Patch", "text=Evidence"]:
        try:
            page.locator(sel).first.click(timeout=1500)
            time.sleep(1.5)
        except Exception:
            pass
    smooth_scroll(page, 600)
    time.sleep(1.5)


def c06_patch_diff(page):
    page.goto(BASE + "/report?case=case_2026_04_18_sanfer", wait_until="networkidle")
    time.sleep(2)
    # scroll deep to patch section
    smooth_scroll(page, 2200, step=25, delay=0.04)
    time.sleep(2)
    try:
        page.locator("text=Patch").first.scroll_into_view_if_needed(timeout=1500)
    except Exception:
        pass
    time.sleep(2)
    smooth_scroll(page, 400)
    time.sleep(1.5)


def c07_cases(page):
    page.goto(BASE + "/cases", wait_until="networkidle")
    time.sleep(2)
    smooth_scroll(page, 400)
    time.sleep(1.5)
    smooth_scroll(page, -400, step=-30)
    time.sleep(1.0)
    # hover first row
    try:
        page.locator("a[href*='/report?case=']").first.hover(timeout=1500)
        time.sleep(1.0)
    except Exception:
        pass


def c08_grounding(page):
    # Inconclusive case — grounding/abstention beat
    page.goto(BASE + "/report?case=case_2026_04_12_yard9", wait_until="networkidle")
    time.sleep(2)
    # scroll to refutation block
    smooth_scroll(page, 1400, step=22, delay=0.05)
    time.sleep(2)
    smooth_scroll(page, 400)
    time.sleep(1.5)


CLIPS = [
    ("01_intake_upload_ui", c01_intake, 10),
    ("02_live_analysis_ui", c02_live, 22),
    ("03_managed_agent_stream_ui", c03_managed_agent, 14),
    ("04_report_overview_ui", c04_report_overview, 16),
    ("05_report_exhibits_ui", c05_report_exhibits, 20),
    ("06_patch_diff_ui", c06_patch_diff, 14),
    ("07_cases_archive_ui", c07_cases, 14),
    ("08_grounding_gate_ui", c08_grounding, 12),
]


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for name, fn, dur in CLIPS:
        if only and only not in name:
            continue
        print(f"[capture] {name} (target {dur}s)", flush=True)
        record(name, fn, duration_min=dur)


if __name__ == "__main__":
    main()
