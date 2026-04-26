"""Rebuild slideshows efficiently + render PDF via pdftoppm."""
import subprocess
from pathlib import Path

ROOT = Path("/home/hz/Desktop/BlackBox")
PACK = ROOT / "demo_assets/editor_raw_footage_pack"
CLIPS = PACK / "clips"
WORK = PACK / "_work"
PDF_FRAMES = WORK / "pdf_frames"
PDF_FRAMES.mkdir(parents=True, exist_ok=True)


def slideshow(name, images, per=3.0):
    if not images:
        print(f"  skip {name}: no images")
        return
    inputs = []
    filters = []
    n = len(images)
    fps = 30
    for i, img in enumerate(images):
        inputs += ["-loop", "1", "-t", f"{per}", "-i", str(img)]
        filters.append(
            f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0b0d11,"
            f"zoompan=z='min(1.0+0.0008*on,1.05)':d=1:s=1920x1080:fps={fps},"
            f"trim=duration={per},setsar=1[v{i}]"
        )
    concat = "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,format=yuv420p[outv]"
    fc = ";".join(filters) + ";" + concat
    dst = CLIPS / f"{name}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc,
           "-map", "[outv]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", str(dst)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode == 0:
        print(f"  OK {dst.name} ({dst.stat().st_size//1024} KB)")
    else:
        print(f"  FAIL {name}: {r.stderr.decode()[-400:]}")


def grid_video(name, images, cols=3, rows=2, duration=10.0):
    cell_w, cell_h = 1920 // cols, 1080 // rows
    n = cols * rows
    images = (list(images) + list(images) * n)[:n]
    inputs, pads = [], []
    for i, img in enumerate(images):
        inputs += ["-loop", "1", "-t", f"{duration}", "-i", str(img)]
        pads.append(f"[{i}:v]scale={cell_w}:{cell_h}:force_original_aspect_ratio=decrease,"
                    f"pad={cell_w}:{cell_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[c{i}]")
    rows_f = []
    for r_i in range(rows):
        row_in = "".join(f"[c{r_i*cols+c}]" for c in range(cols))
        rows_f.append(f"{row_in}hstack=inputs={cols}[r{r_i}]")
    rows_in = "".join(f"[r{r_i}]" for r_i in range(rows))
    fc = (";".join(pads + rows_f) + ";" + rows_in
          + f"vstack=inputs={rows},format=yuv420p,fps=30[outv]")
    dst = CLIPS / f"{name}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc,
           "-map", "[outv]", "-t", f"{duration}",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(dst)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode == 0:
        print(f"  OK {dst.name} ({dst.stat().st_size//1024} KB)")
    else:
        print(f"  FAIL {name}: {r.stderr.decode()[-400:]}")


def main():
    charts = ROOT / "demo_assets/final_demo_pack/charts"

    # 10 RTK charts
    rtk = [charts / n for n in
           ["moving_base_vs_rover_2x.png", "rtk_carrier_contrast.png",
            "rel_pos_valid.png", "rtk_numsv.png"]]
    rtk = [p for p in rtk if p.exists()]
    print(f"[10] rtk_root_cause_charts ({len(rtk)})")
    slideshow("10_rtk_root_cause_charts", rtk, per=4.0)

    # 13 sanfer camera frames
    fr_dir = ROOT / "data/final_runs/sanfer_tunnel/bundle/frames"
    all_frames = sorted(fr_dir.glob("*.jpg"))
    pick = all_frames[::max(1, len(all_frames)//6)][:6]
    print(f"[13] sanfer_real_camera_broll ({len(pick)})")
    slideshow("13_sanfer_real_camera_broll", pick, per=2.2)

    # 14 multicam grid
    print(f"[14] multicam_composite_real ({len(pick)})")
    grid_video("14_multicam_composite_real", pick, cols=3, rows=2, duration=10.0)

    # 19 opus47 panel
    panel = ROOT / "demo_assets/final_demo_pack/panels/opus47_delta_panel.png"
    if panel.exists():
        print("[19] opus47_delta_panel_real_capture")
        slideshow("19_opus47_delta_panel_real_capture", [panel], per=8.0)

    # 20 vision A/B
    vis = [charts / "visual_mining_v2_grid.png", charts / "d1_vision_plot.png"]
    vis = [p for p in vis if p.exists()]
    print(f"[20] vision_ab_artifact ({len(vis)})")
    slideshow("20_vision_ab_artifact", vis, per=5.0)

    # 11 PDF — render pages with pdftoppm, slideshow them
    pdf = ROOT / "data/final_runs/sanfer_tunnel/report.pdf"
    if pdf.exists():
        print("[11] sanfer_pdf_scroll (rendering pages)")
        for f in PDF_FRAMES.glob("*.png"):
            f.unlink()
        subprocess.run(["pdftoppm", "-png", "-r", "144", "-aa", "yes",
                        str(pdf), str(PDF_FRAMES / "page")], check=True)
        pages = sorted(PDF_FRAMES.glob("*.png"))
        print(f"  {len(pages)} pages")
        slideshow("11_sanfer_pdf_scroll", pages, per=2.5)


if __name__ == "__main__":
    main()
