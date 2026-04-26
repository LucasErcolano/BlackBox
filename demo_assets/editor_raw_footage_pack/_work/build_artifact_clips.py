"""Build clips 09–20 from real artifacts (PDFs, markdown, charts, frames)."""
import os
import shutil
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
import markdown

ROOT = Path("/home/hz/Desktop/BlackBox")
PACK = ROOT / "demo_assets/editor_raw_footage_pack"
WORK = PACK / "_work"
WEBM = WORK / "raw_webm"
WEBM.mkdir(parents=True, exist_ok=True)
CLIPS = PACK / "clips"
TMP = WORK / "tmp_html"
TMP.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080

CSS = """
<style>
:root{color-scheme:dark;}
body{background:#0b0d11;color:#dfe5ec;font-family:-apple-system,Inter,Segoe UI,Roboto,sans-serif;
     max-width:1180px;margin:0 auto;padding:48px 56px;font-size:18px;line-height:1.6;}
h1{font-size:38px;color:#fff;border-bottom:1px solid #2a3340;padding-bottom:12px;}
h2{font-size:28px;color:#9bd1ff;margin-top:36px;}
h3{font-size:22px;color:#cbd5e1;}
code{background:#161b22;color:#ffd28a;padding:2px 6px;border-radius:4px;font-size:0.9em;}
pre{background:#0f1419;border:1px solid #1f2937;padding:16px;border-radius:8px;overflow:auto;
    font-size:14px;line-height:1.5;}
blockquote{border-left:4px solid #ffb86b;padding:6px 16px;margin:18px 0;background:#1a1410;color:#ffd9aa;}
table{border-collapse:collapse;width:100%;margin:16px 0;}
th,td{border:1px solid #2a3340;padding:8px 12px;text-align:left;}
th{background:#171c25;}
strong{color:#fff;}
a{color:#9bd1ff;}
ul,ol{padding-left:28px;}
</style>
"""


def render_md_to_html(md_path: Path, out_html: Path, title: str):
    text = md_path.read_text()
    html = markdown.markdown(text, extensions=["fenced_code", "tables"])
    out_html.write_text(f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>{CSS}</head><body>{html}</body></html>")


def smooth_scroll(page, total, step=22, delay=0.045):
    done = 0
    sgn = 1 if total > 0 else -1
    total = abs(total)
    while done < total:
        d = min(step, total - done)
        page.mouse.wheel(0, sgn * d)
        time.sleep(delay)
        done += d


def record_url(name: str, url: str, driver, duration: float):
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            device_scale_factor=1,
            record_video_dir=str(WEBM / name),
            record_video_size={"width": W, "height": H},
        )
        page = ctx.new_page()
        start = time.time()
        try:
            page.goto(url, wait_until="domcontentloaded")
            time.sleep(1.5)
            driver(page)
        except Exception as e:
            print(f"  ! {name}: {e}", flush=True)
        elapsed = time.time() - start
        if elapsed < duration:
            time.sleep(duration - elapsed)
        page.close()
        ctx.close()
        browser.close()
    webms = list((WEBM / name).rglob("*.webm"))
    if webms:
        target = WEBM / f"{name}.webm"
        webms[0].rename(target)
        print(f"  -> {target.name} ({target.stat().st_size//1024} KB)")


def webm_to_mp4(name: str, scale_filter: str = "scale=1920:1080:flags=lanczos"):
    src = WEBM / f"{name}.webm"
    if not src.exists():
        print(f"  ! missing {src}")
        return
    dst = CLIPS / f"{name}.mp4"
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vf", f"{scale_filter},fps=30,format=yuv420p",
        "-c:v", "libx264", "-profile:v", "high", "-crf", "18", "-pix_fmt", "yuv420p", "-an", str(dst),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"  mp4 {dst}")


def slideshow_kenburns(name: str, images: list[Path], per_image: float = 3.0):
    """Build slideshow MP4 with subtle Ken Burns from a list of real images."""
    if not images:
        print(f"  ! no images for {name}")
        return
    inputs = []
    filters = []
    n = len(images)
    fps = 30
    frames_per = int(per_image * fps)
    # zoompan needs explicit input frame counts
    for i, img in enumerate(images):
        inputs += ["-loop", "1", "-t", f"{per_image}", "-i", str(img)]
        # gentle zoom 1.0 -> 1.07 with slow pan
        zoom = (
            f"[{i}:v]scale=2400:-1:flags=lanczos,"
            f"zoompan=z='min(zoom+0.0009,1.07)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames_per}:s=1920x1080:fps={fps},setsar=1[v{i}]"
        )
        filters.append(zoom)
    concat = "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,format=yuv420p[outv]"
    filter_complex = ";".join(filters) + ";" + concat
    dst = CLIPS / f"{name}.mp4"
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex,
           "-map", "[outv]", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(dst)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print(f"  ! ffmpeg slideshow {name}: {r.stderr.decode()[-500:]}")
    else:
        print(f"  mp4 {dst}")


def grid_video(name: str, images: list[Path], cols=3, rows=2, duration=10.0):
    """2D contact-sheet video from real frames, gentle zoom on whole grid."""
    if not images:
        print(f"  ! no images for {name}")
        return
    cell_w = W // cols
    cell_h = H // rows
    n = cols * rows
    images = (images + images * n)[:n]
    inputs = []
    pads = []
    for i, img in enumerate(images):
        inputs += ["-loop", "1", "-t", f"{duration}", "-i", str(img)]
        pads.append(f"[{i}:v]scale={cell_w}:{cell_h}:force_original_aspect_ratio=decrease,"
                    f"pad={cell_w}:{cell_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[c{i}]")
    rows_filters = []
    for r_i in range(rows):
        row_in = "".join(f"[c{r_i*cols+c}]" for c in range(cols))
        rows_filters.append(f"{row_in}hstack=inputs={cols}[r{r_i}]")
    rows_in = "".join(f"[r{r_i}]" for r_i in range(rows))
    final = (";".join(pads + rows_filters) + ";" + rows_in
             + f"vstack=inputs={rows},format=yuv420p,fps=30[outv]")
    dst = CLIPS / f"{name}.mp4"
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", final,
           "-map", "[outv]", "-t", f"{duration}",
           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(dst)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print(f"  ! ffmpeg grid {name}: {r.stderr.decode()[-500:]}")
    else:
        print(f"  mp4 {dst}")


# --- Drivers ---

def drv_scroll_long(page):
    # scroll all the way down then back partway
    smooth_scroll(page, 2200, step=22, delay=0.05)
    time.sleep(1.0)


def drv_scroll_short(page):
    smooth_scroll(page, 900, step=20, delay=0.05)
    time.sleep(1.0)


def drv_pdf(page):
    # Chromium PDF viewer: PageDown
    for _ in range(8):
        time.sleep(1.4)
        page.keyboard.press("PageDown")
    time.sleep(2.0)


def drv_idle(page):
    time.sleep(8)


def main():
    # 09 operator_refutation_report — render sanfer_tunnel.md from demo_assets/pdfs
    md = ROOT / "demo_assets/final_demo_pack/pdfs/sanfer_tunnel.md"
    if md.exists():
        out = TMP / "09.html"
        render_md_to_html(md, out, "Operator vs BlackBox — sanfer_tunnel")
        print("[09] operator_refutation_report")
        record_url("09_operator_refutation_report", f"file://{out}", drv_scroll_long, 12)
        webm_to_mp4("09_operator_refutation_report")

    # 11 sanfer_pdf_scroll — actual report PDF
    pdf = ROOT / "data/final_runs/sanfer_tunnel/report.pdf"
    if pdf.exists():
        print("[11] sanfer_pdf_scroll")
        record_url("11_sanfer_pdf_scroll", f"file://{pdf}#zoom=125", drv_pdf, 22)
        webm_to_mp4("11_sanfer_pdf_scroll")

    # 17 opus47_delta_doc_scroll
    md47 = ROOT / "docs/OPUS47_DELTA.md"
    if md47.exists():
        out = TMP / "17.html"
        render_md_to_html(md47, out, "Opus 4.7 vs 4.6 — Delta")
        print("[17] opus47_delta_doc_scroll")
        record_url("17_opus47_delta_doc_scroll", f"file://{out}", drv_scroll_long, 22)
        webm_to_mp4("17_opus47_delta_doc_scroll")

    # 15 boat_report_broll
    boat_md = ROOT / "data/final_runs/boat_lidar/report.md"
    if boat_md.exists():
        out = TMP / "15.html"
        render_md_to_html(boat_md, out, "Boat lidar — report")
        print("[15] boat_report_broll")
        record_url("15_boat_report_broll", f"file://{out}", drv_scroll_short, 12)
        webm_to_mp4("15_boat_report_broll")

    # 16 other_car_run_broll — render car_1 report
    car_md = ROOT / "data/final_runs/car_1/report.md"
    if car_md.exists():
        out = TMP / "16.html"
        render_md_to_html(car_md, out, "car_1 — report")
        print("[16] other_car_run_broll (report scroll)")
        record_url("16_other_car_run_broll", f"file://{out}", drv_scroll_short, 12)
        webm_to_mp4("16_other_car_run_broll")

    # 12 telemetry_files_broll — file index via local http.server
    # Start a temp server on root; use Playwright file://-style index
    # Simpler: enable Chromium "view directory" by pointing to a generated index html
    files_dir = ROOT / "data/final_runs/sanfer_tunnel"
    rows = []
    for entry in sorted(files_dir.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            for sub in sorted(entry.iterdir())[:30]:
                size = sub.stat().st_size if sub.is_file() else "—"
                rows.append((f"{entry.name}/{sub.name}", size))
        else:
            rows.append((entry.name, entry.stat().st_size))
    rows_html = "\n".join(
        f"<tr><td><code>{n}</code></td><td>{(f'{s/1024:.1f} KB' if isinstance(s,int) else s)}</td></tr>"
        for n, s in rows
    )
    listing_html = f"""<!doctype html><html><head><meta charset="utf-8">{CSS}</head><body>
    <h1>data/final_runs/sanfer_tunnel/</h1>
    <p>Real telemetry artifacts written by the BlackBox pipeline.</p>
    <table><thead><tr><th>path</th><th>size</th></tr></thead><tbody>
    {rows_html}
    </tbody></table></body></html>"""
    listing = TMP / "12.html"
    listing.write_text(listing_html)
    print("[12] telemetry_files_broll")
    record_url("12_telemetry_files_broll", f"file://{listing}", drv_scroll_short, 9)
    webm_to_mp4("12_telemetry_files_broll")

    # 18 opus47_delta_artifacts_folder — listing of data/bench_runs
    bench = ROOT / "data/bench_runs"
    rows = []
    for entry in sorted(bench.iterdir()):
        if entry.name.startswith("."):
            continue
        size = entry.stat().st_size if entry.is_file() else "—"
        rows.append((entry.name, size))
    rows_html = "\n".join(
        f"<tr><td><code>{n}</code></td><td>{(f'{s/1024:.1f} KB' if isinstance(s,int) else s)}</td></tr>"
        for n, s in rows
    )
    bench_html = f"""<!doctype html><html><head><meta charset="utf-8">{CSS}</head><body>
    <h1>data/bench_runs/ — Opus 4.7 vs 4.6 outputs</h1>
    <p>Each <code>opus46_vs_opus47_*.json</code> is a head-to-head bench run.</p>
    <table><thead><tr><th>file</th><th>size</th></tr></thead><tbody>{rows_html}</tbody></table>
    </body></html>"""
    bench_path = TMP / "18.html"
    bench_path.write_text(bench_html)
    print("[18] opus47_delta_artifacts_folder")
    record_url("18_opus47_delta_artifacts_folder", f"file://{bench_path}", drv_scroll_short, 11)
    webm_to_mp4("18_opus47_delta_artifacts_folder")

    # 10 rtk_root_cause_charts — slideshow of real chart PNGs
    charts_dir = ROOT / "demo_assets/final_demo_pack/charts"
    chart_files = [
        charts_dir / "moving_base_vs_rover_2x.png",
        charts_dir / "rtk_carrier_contrast.png",
        charts_dir / "rel_pos_valid.png",
        charts_dir / "rtk_numsv.png",
    ]
    chart_files = [c for c in chart_files if c.exists()]
    print("[10] rtk_root_cause_charts (slideshow)")
    slideshow_kenburns("10_rtk_root_cause_charts", chart_files, per_image=4.0)

    # 13 sanfer_real_camera_broll — frames slideshow
    frames_dir = ROOT / "data/final_runs/sanfer_tunnel/bundle/frames"
    all_frames = sorted(frames_dir.glob("*.jpg"))
    pick = all_frames[::max(1, len(all_frames)//6)][:6]
    print(f"[13] sanfer_real_camera_broll ({len(pick)} frames)")
    slideshow_kenburns("13_sanfer_real_camera_broll", pick, per_image=2.2)

    # 14 multicam_composite_real — 3x2 grid from real frames
    pick14 = all_frames[::max(1, len(all_frames)//6)][:6]
    print(f"[14] multicam_composite_real ({len(pick14)} cells)")
    grid_video("14_multicam_composite_real", pick14, cols=3, rows=2, duration=10.0)

    # 19 opus47_delta_panel_real_capture — ken-burns over existing panel PNG
    panel = ROOT / "demo_assets/final_demo_pack/panels/opus47_delta_panel.png"
    if panel.exists():
        print("[19] opus47_delta_panel_real_capture")
        slideshow_kenburns("19_opus47_delta_panel_real_capture", [panel], per_image=8.0)

    # 20 vision_ab_artifact — visual_mining_v2_grid + d1_vision_plot
    vis = [
        charts_dir / "visual_mining_v2_grid.png",
        charts_dir / "d1_vision_plot.png",
    ]
    vis = [v for v in vis if v.exists()]
    print(f"[20] vision_ab_artifact ({len(vis)} images)")
    slideshow_kenburns("20_vision_ab_artifact", vis, per_image=5.0)


if __name__ == "__main__":
    main()
