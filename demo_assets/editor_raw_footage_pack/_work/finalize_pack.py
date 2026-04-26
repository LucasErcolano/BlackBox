"""Stills, contact sheets, manifest, docs."""
import json
import shutil
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path("/home/hz/Desktop/BlackBox")
PACK = ROOT / "demo_assets/editor_raw_footage_pack"
CLIPS = PACK / "clips"
STILLS = PACK / "stills"
SHEETS = PACK / "contact_sheets"
DOCS = PACK / "docs"
for p in (STILLS, SHEETS, DOCS):
    p.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
BASE = "http://127.0.0.1:8765"


# --- Stills via playwright + ffmpeg ---

def shoot(name, url=None, src_mp4=None, ts=None, scroll_y=0):
    out = STILLS / name
    if url:
        with sync_playwright() as p:
            br = p.chromium.launch(args=["--no-sandbox"])
            ctx = br.new_context(viewport={"width": W, "height": H}, device_scale_factor=1)
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(2)
            if scroll_y:
                page.evaluate(f"window.scrollTo(0,{scroll_y})")
                time.sleep(1.0)
            page.screenshot(path=str(out), full_page=False)
            br.close()
        print(f"  still {out.name}")
    elif src_mp4 and ts is not None:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(ts),
                        "-i", str(src_mp4), "-frames:v", "1", "-q:v", "2", str(out)], check=True)
        print(f"  still {out.name} (from {src_mp4.name}@{ts}s)")


def stills():
    # Hero — sanfer report
    shoot("hero_report_top.png", url=f"{BASE}/report?case=case_2026_04_18_sanfer", scroll_y=0)
    shoot("operator_refutation.png", src_mp4=CLIPS/"09_operator_refutation_report.mp4", ts=6.0)
    shoot("rtk_root_cause_chart.png", src_mp4=CLIPS/"10_rtk_root_cause_charts.mp4", ts=2.0)
    shoot("patch_diff.png", url=f"{BASE}/report?case=case_2026_04_18_sanfer", scroll_y=2200)
    # use existing real panel png
    shutil.copy(ROOT/"demo_assets/final_demo_pack/panels/opus47_delta_panel.png",
                STILLS/"opus47_delta_panel.png")
    shoot("breadth_cases_archive.png", url=f"{BASE}/cases", scroll_y=120)
    shoot("grounding_gate.png", src_mp4=CLIPS/"08_grounding_gate_ui.mp4", ts=8.0)
    shoot("managed_agent_memory_trace.png", src_mp4=CLIPS/"03_managed_agent_stream_ui.mp4", ts=8.0)


# --- Contact sheets ---

def contact_all_clips():
    clips = sorted(CLIPS.glob("*.mp4"))
    # 1 frame per clip at 50% point, tile 5x4
    tmp = PACK / "_work" / "thumbs"
    tmp.mkdir(parents=True, exist_ok=True)
    thumbs = []
    for c in clips:
        # midpoint
        dur = float(subprocess.check_output(
            ["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(c)]
        ).decode().strip())
        out = tmp / f"{c.stem}.jpg"
        subprocess.run(["ffmpeg","-y","-loglevel","error","-ss",f"{dur/2:.2f}",
                        "-i",str(c),"-frames:v","1","-vf","scale=480:270",str(out)], check=True)
        thumbs.append(out)
    # 5 cols, 4 rows
    cols, rows = 5, 4
    cell_w, cell_h = 480, 270
    sheet_w = cols*cell_w
    # build with montage via ffmpeg xstack
    # simpler: PIL
    from PIL import Image, ImageDraw, ImageFont
    sheet = Image.new("RGB", (sheet_w, rows*cell_h+rows*32), (11,13,17))
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except Exception:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(thumbs):
        r, c = divmod(i, cols)
        x = c*cell_w
        y = r*(cell_h+32)
        im = Image.open(t).resize((cell_w, cell_h))
        sheet.paste(im, (x, y))
        d.rectangle([x,y+cell_h,x+cell_w,y+cell_h+32], fill=(20,25,35))
        d.text((x+8, y+cell_h+6), t.stem, font=font, fill=(220,229,238))
    sheet.save(SHEETS/"editor_contact_sheet_all_clips.png")
    print("  sheet all_clips")
    # key frames sheet — 8 marquee clips
    key = ["01_intake_upload_ui","04_report_overview_ui","06_patch_diff_ui",
           "07_cases_archive_ui","09_operator_refutation_report","10_rtk_root_cause_charts",
           "13_sanfer_real_camera_broll","17_opus47_delta_doc_scroll"]
    cw, ch = 960, 540
    sheet2 = Image.new("RGB", (cw*4, ch*2+2*40), (11,13,17))
    d2 = ImageDraw.Draw(sheet2)
    for i, stem in enumerate(key):
        c = CLIPS / f"{stem}.mp4"
        dur = float(subprocess.check_output(
            ["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(c)]
        ).decode().strip())
        out = tmp / f"key_{stem}.jpg"
        subprocess.run(["ffmpeg","-y","-loglevel","error","-ss",f"{dur/2:.2f}",
                        "-i",str(c),"-frames:v","1","-vf","scale=960:540",str(out)], check=True)
        r, cc = divmod(i, 4)
        x = cc*cw
        y = r*(ch+40)
        sheet2.paste(Image.open(out), (x, y))
        d2.rectangle([x,y+ch,x+cw,y+ch+40], fill=(20,25,35))
        try:
            font2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        except Exception:
            font2 = font
        d2.text((x+12, y+ch+8), stem, font=font2, fill=(255,255,255))
    sheet2.save(SHEETS/"editor_contact_sheet_key_frames.png")
    print("  sheet key_frames")


# --- Manifest ---

CLIP_META = [
    ("01_intake_upload_ui.mp4", "Real intake page (/) — mode cards, drop zone, hero copy.",
     "live BlackBox UI route /", "Setup beat: 'this is the operator-facing intake'.",
     "real UI", None),
    ("02_live_analysis_ui.mp4", "Live job panel after replay-trigger — pipeline stages, polling.",
     "GET /analyze?replay=sanfer_tunnel", "Analysis-running beat.",
     "real UI", None),
    ("03_managed_agent_stream_ui.mp4", "Trace/checkpoints view — managed agent events.",
     "GET /trace/{job_id} or /checkpoints", "Managed agent / not-one-shot beat.",
     "real UI", "Job ID hand-off may default to /checkpoints if trace ID not parseable."),
    ("04_report_overview_ui.mp4", "Report top — verdict banner, summary scroll.",
     "GET /report?case=case_2026_04_18_sanfer", "Verdict reveal.",
     "real UI", None),
    ("05_report_exhibits_ui.mp4", "Report exhibits — telemetry, evidence sections.",
     "GET /report?case=...", "Evidence montage.",
     "real UI", None),
    ("06_patch_diff_ui.mp4", "Scoped patch / diff section, deep scroll.",
     "GET /report?case=... (deep scroll)", "Patch / human-review beat.",
     "real UI", None),
    ("07_cases_archive_ui.mp4", "Cases archive list — multiple cases.",
     "GET /cases", "Breadth: 'not a one-off car demo'.",
     "real UI", None),
    ("08_grounding_gate_ui.mp4", "Inconclusive case report (yard9) — abstention beat.",
     "GET /report?case=case_2026_04_12_yard9", "Grounding gate / 'refuses to invent a bug'.",
     "real UI", "demo_data falls back to SANFER content for unknown case ids — UI is real."),
    ("09_operator_refutation_report.mp4", "sanfer_tunnel.md rendered & scrolled.",
     "demo_assets/final_demo_pack/pdfs/sanfer_tunnel.md", "Operator vs BlackBox refutation beat.",
     "real artifact (markdown→html in browser)", None),
    ("10_rtk_root_cause_charts.mp4", "RTK chart slideshow: moving_base_vs_rover, carrier, rel_pos_valid, num_sv.",
     "demo_assets/final_demo_pack/charts/*.png", "Root-cause evidence beat.",
     "real artifact (chart slideshow)", None),
    ("11_sanfer_pdf_scroll.mp4", "Real BlackBox sanfer report PDF, page-by-page.",
     "data/final_runs/sanfer_tunnel/report.pdf (pdftoppm)", "Forensic report B-roll.",
     "real artifact (PDF render)", None),
    ("12_telemetry_files_broll.mp4", "File listing of data/final_runs/sanfer_tunnel/ (real entries).",
     "filesystem listing", "Telemetry/file-system B-roll.",
     "real artifact (file listing)", "Rendered as HTML table, not OS file explorer."),
    ("13_sanfer_real_camera_broll.mp4", "Real extracted camera frames from sanfer_tunnel bag.",
     "data/final_runs/sanfer_tunnel/bundle/frames/*.jpg", "'Real robot footage' beat.",
     "real robot footage (extracted frames)", None),
    ("14_multicam_composite_real.mp4", "3x2 grid of real frames.",
     "same frames", "Multi-camera reasoning B-roll.",
     "real robot footage (grid)", "Same camera, sampled at different times — labels minimal."),
    ("15_boat_report_broll.mp4", "boat_lidar report markdown rendered & scrolled.",
     "data/final_runs/boat_lidar/report.md", "Breadth — robotic boat case.",
     "real artifact (no camera frames available)",
     "No camera frames in boat_lidar/ — report scroll only. Renamed from boat_real_broll."),
    ("16_other_car_run_broll.mp4", "car_1 report markdown rendered & scrolled.",
     "data/final_runs/car_1/report.md", "Breadth — second car run.",
     "real artifact", None),
    ("17_opus47_delta_doc_scroll.mp4", "docs/OPUS47_DELTA.md rendered & scrolled.",
     "docs/OPUS47_DELTA.md", "Model-delta beat.",
     "real artifact", None),
    ("18_opus47_delta_artifacts_folder.mp4", "Listing of data/bench_runs/ — real bench JSONs.",
     "data/bench_runs/", "Model-delta artifact B-roll.",
     "real artifact (listing)", None),
    ("19_opus47_delta_panel_real_capture.mp4", "Static delta panel PNG with subtle pan.",
     "demo_assets/final_demo_pack/panels/opus47_delta_panel.png", "Delta beat B-roll.",
     "real artifact (panel image)", None),
    ("20_vision_ab_artifact.mp4", "Visual mining grid + d1_vision_plot.",
     "demo_assets/final_demo_pack/charts/visual_mining_v2_grid.png, d1_vision_plot.png",
     "4.6 vs 4.7 vision detail beat.", "real artifact", None),
]


def manifest():
    items = []
    for fn, desc, source, beat, kind, caveat in CLIP_META:
        f = CLIPS / fn
        if not f.exists():
            continue
        meta = json.loads(subprocess.check_output(
            ["ffprobe","-v","error","-show_entries",
             "stream=width,height,r_frame_rate,codec_name,pix_fmt:format=duration",
             "-of","json","-select_streams","v:0",str(f)]
        ).decode())
        s = meta["streams"][0]
        items.append({
            "filename": fn,
            "duration_s": round(float(meta["format"]["duration"]), 2),
            "width": s["width"], "height": s["height"],
            "fps": int(eval(s["r_frame_rate"])),
            "codec": s["codec_name"], "pix_fmt": s["pix_fmt"],
            "source": source, "description": desc,
            "suggested_beat": beat, "kind": kind, "caveat": caveat,
        })
    (PACK/"manifest.json").write_text(json.dumps({"clips": items}, indent=2))
    print(f"  manifest {len(items)} clips")


def write_docs():
    idx = ["# Editor clip index", ""]
    for fn, desc, source, beat, kind, caveat in CLIP_META:
        idx += [f"## {fn}",
                f"- **shows**: {desc}",
                f"- **source**: {source}",
                f"- **beat**: {beat}",
                f"- **kind**: {kind}",
                f"- **caveat**: {caveat or '—'}",
                ""]
    (DOCS/"editor_clip_index.md").write_text("\n".join(idx))

    (DOCS/"capture_notes.md").write_text("""# Capture notes

- App: `uvicorn black_box.ui.app:app --host 127.0.0.1 --port 8765`
- UI clips (01–08): Playwright Chromium, 1920x1080, device_scale_factor=1, headless. Driver: `_work/capture_ui.py`.
- Artifact clips (09, 12, 15–18): markdown→HTML wrapper rendered in same Playwright session, scrolled with `mouse.wheel`.
- PDF clip (11): `pdftoppm -r 144` → PNG pages → ffmpeg slideshow with subtle zoom.
- Slideshows (10, 13, 14, 19, 20): ffmpeg `-loop 1` + `zoompan` + `concat`. CRF 20, preset veryfast.
- All clips re-encoded to H.264 / yuv420p / 30fps via ffmpeg.
- No Remotion. No AI-generated terminal. No synthetic UI. All footage either is the live FastAPI/HTMX UI or a static asset already shipped in the repo.

## Reproduce
```
PYTHONPATH=src nohup python3 -m uvicorn black_box.ui.app:app --host 127.0.0.1 --port 8765 &
python3 demo_assets/editor_raw_footage_pack/_work/capture_ui.py
python3 demo_assets/editor_raw_footage_pack/_work/build_artifact_clips.py     # clips 09, 11, 12, 15-18
python3 demo_assets/editor_raw_footage_pack/_work/build_remaining.py          # clips 10, 13, 14, 19, 20
python3 demo_assets/editor_raw_footage_pack/_work/finalize_pack.py            # stills + sheets + manifest
```
""")

    (DOCS/"missing_assets.md").write_text("""# Missing real assets

- **Real boat camera footage** — `data/final_runs/boat_lidar/bundle/` has lidar + summary only, no `.jpg`/`.mp4`. Substituted with `15_boat_report_broll.mp4` (real `report.md`). Not a fabricated robot view.
- **Real `vision_ab` side-by-side** — no shipped 4.6-vs-4.7 vision pair PNG. Used `visual_mining_v2_grid.png` + `d1_vision_plot.png` (real shipped vision charts) as the closest available proxy. Editor may want to recreate a tighter A/B card by hand.
- **Audio** — no clips include audio. Editor to add v/o + score.
- **Live websocket trace** — `/trace/{job_id}` rendered, but no real-time event flood; demo replay drives a fast pipeline. If editor wants more visible motion, re-record `02_live_analysis_ui.mp4` with longer dwell.
""")

    (DOCS/"usage_rights_and_caveats.md").write_text("""# Usage rights & caveats

- All footage is from the BlackBox project repo (Lucas Ercolano + Aayush). Internal hackathon use.
- Camera frames in `13_*.mp4` and `14_*.mp4` are extracted from project bag(s) the team owns.
- Demo case data shown in `02`, `08`, etc. is the team's `data/final_runs/` recorded output.
- No third-party footage. No AI-generated content. No Remotion-generated scenes.
- Stills in `stills/` are real screenshots.
- yuv420p, H.264 baseline-compatible, 30 fps, 1920x1080.
""")
    print("  docs written")


if __name__ == "__main__":
    stills()
    contact_all_clips()
    manifest()
    write_docs()
