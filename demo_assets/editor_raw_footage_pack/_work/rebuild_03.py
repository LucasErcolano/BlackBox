"""Rebuild 03 — render real stream_events.jsonl as a managed-agent feed and scroll."""
import json
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path("/home/hz/Desktop/BlackBox")
PACK = ROOT / "demo_assets/editor_raw_footage_pack"
WORK = PACK / "_work"
WEBM = WORK / "raw_webm"
TMP = WORK / "tmp_html"
CLIPS = PACK / "clips"

src = ROOT / "data/final_runs/sanfer_tunnel/stream_events.jsonl"
events = [json.loads(l) for l in src.read_text().splitlines() if l.strip()]

CSS = """<style>
:root{color-scheme:dark;}
body{background:#0b0d11;color:#dfe5ec;font-family:-apple-system,Inter,Segoe UI,Roboto,sans-serif;
     margin:0;padding:32px 56px;font-size:16px;line-height:1.5;}
h1{font-size:30px;color:#fff;margin:0 0 8px;}
.sub{color:#94a3b8;margin-bottom:28px;}
.row{border-left:3px solid #2a3340;padding:10px 14px;margin:8px 0;background:#10141b;
     border-radius:0 6px 6px 0;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
     font-size:14px;}
.row.tool{border-color:#9bd1ff;}
.row.text{border-color:#ffb86b;}
.row.usage{border-color:#a3e635;}
.row.status{border-color:#64748b;}
.kind{display:inline-block;padding:1px 8px;border-radius:10px;background:#1f2937;color:#cbd5e1;
      font-size:11px;letter-spacing:.04em;text-transform:uppercase;margin-right:8px;}
.ts{color:#64748b;font-size:11px;margin-right:10px;}
pre{margin:6px 0 0;color:#dfe5ec;white-space:pre-wrap;word-break:break-word;font-size:13px;
    max-height:120px;overflow:hidden;}
</style>"""

rows = []
for ev in events[:90]:
    t = ev.get("type", "?")
    p = ev.get("payload", {})
    cls = "status"
    if t == "tool_use" or "tool" in str(p)[:50]:
        cls = "tool"
    elif t == "text":
        cls = "text"
    elif t == "usage":
        cls = "usage"
    snippet = json.dumps(p)[:280].replace("<","&lt;")
    rows.append(
        f'<div class="row {cls}"><span class="kind">{t}</span>'
        f'<span class="ts">t={ev.get("ts",0):.3f}</span>'
        f'<pre>{snippet}</pre></div>'
    )

html = f"""<!doctype html><html><head><meta charset="utf-8">{CSS}</head><body>
<h1>Managed agent — session trace</h1>
<div class="sub">case_2026_04_18_sanfer · stream_events.jsonl · {len(events)} events</div>
{''.join(rows)}
</body></html>"""
out = TMP / "03b.html"
out.write_text(html)

W, H = 1920, 1080
name = "03_managed_agent_stream_ui"
(WEBM / name).mkdir(parents=True, exist_ok=True)
for f in (WEBM / name).glob("*"):
    if f.is_file():
        f.unlink()

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox"])
    ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1,
                              record_video_dir=str(WEBM / name),
                              record_video_size={"width": W, "height": H})
    page = ctx.new_page()
    page.goto(f"file://{out}", wait_until="domcontentloaded")
    time.sleep(1.5)
    # smooth long scroll over ~14s
    total = 5500
    step = 18
    delay = 0.05
    done = 0
    while done < total:
        d = min(step, total - done)
        page.mouse.wheel(0, d)
        time.sleep(delay)
        done += d
    time.sleep(1.0)
    page.close(); ctx.close(); browser.close()

webms = list((WEBM/name).rglob("*.webm"))
target = WEBM / f"{name}.webm"
webms[0].rename(target)

dst = CLIPS / f"{name}.mp4"
subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(target),
                "-vf","scale=1920:1080:flags=lanczos,fps=30,format=yuv420p",
                "-c:v","libx264","-crf","18","-pix_fmt","yuv420p","-an",str(dst)], check=True)
print(f"OK {dst} ({dst.stat().st_size//1024} KB)")
