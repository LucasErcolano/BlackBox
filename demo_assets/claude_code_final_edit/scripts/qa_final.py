"""QA the final cut: probe, sample frames, build contact sheets, write report."""
import json
import subprocess
from pathlib import Path
from PIL import Image

ROOT = Path("/home/hz/Desktop/BlackBox")
EDIT = ROOT / "demo_assets/claude_code_final_edit"
OUT = EDIT / "output"
WORK = EDIT / "_work"
WORK.mkdir(parents=True, exist_ok=True)

FINAL = OUT / "blackbox_demo_claude_edit_v1.mp4"
TL = json.loads((OUT / "timeline.json").read_text())


def ffprobe(p: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                        "-show_streams", "-show_format", str(p)],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def grab(p: Path, ts: float, dst: Path):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{ts}",
                    "-i", str(p), "-frames:v", "1",
                    "-vf", "scale=480:270", str(dst)], check=True)


def grid(images, cols, dst: Path, label_fn=None):
    cw, ch = 480, 270
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cw*cols, ch*rows), (11, 13, 17))
    for i, im in enumerate(images):
        img = Image.open(im).convert("RGB").resize((cw, ch))
        r, c = i // cols, i % cols
        sheet.paste(img, (c*cw, r*ch))
    sheet.save(dst, "PNG")


def main():
    p = ffprobe(FINAL)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    a = next((s for s in p["streams"] if s["codec_type"] == "audio"), None)
    fr = v["r_frame_rate"]; n, d = (int(x) for x in fr.split("/"))
    fps = n / d
    dur = float(p["format"]["duration"])

    checks = {
        "duration_s": dur,
        "duration_ok": 170.0 <= dur <= 180.0,
        "resolution": f"{v['width']}x{v['height']}",
        "resolution_ok": v["width"] == 1920 and v["height"] == 1080,
        "fps": fps,
        "fps_ok": abs(fps - 30) < 0.05,
        "codec": v["codec_name"],
        "codec_ok": v["codec_name"] == "h264",
        "pix_fmt": v["pix_fmt"],
        "pix_fmt_ok": v["pix_fmt"] == "yuv420p",
        "audio_present": a is not None,
        "size_bytes": int(p["format"]["size"]),
    }

    # 20 evenly spaced frames -> contact_sheet_final
    n_grid = 20
    grid_imgs = []
    for i in range(n_grid):
        ts = (i + 0.5) * dur / n_grid
        f = WORK / f"grid_{i:02d}.png"
        grab(FINAL, ts, f)
        grid_imgs.append(f)
    grid(grid_imgs, 5, OUT / "contact_sheet_final.png")

    # transition contact sheet: 0.4s before & 0.4s after every cut
    cuts = [seg["start_s"] for seg in TL["segments"][1:]]
    trans_imgs = []
    for i, t in enumerate(cuts):
        for off, tag in [(-0.4, "pre"), (0.4, "post")]:
            ts = max(0.05, min(dur - 0.05, t + off))
            f = WORK / f"tr_{i:02d}_{tag}.png"
            grab(FINAL, ts, f)
            trans_imgs.append(f)
    grid(trans_imgs, 4, OUT / "transition_contact_sheet.png")

    # Freeze detection: ffmpeg freezedetect filter
    fr_log = WORK / "freeze.log"
    subprocess.run(["ffmpeg", "-i", str(FINAL),
                    "-vf", "freezedetect=n=-60dB:d=1.5",
                    "-map", "0:v:0", "-f", "null", "-"],
                   stderr=open(fr_log, "w"))
    freeze_lines = [l for l in fr_log.read_text().splitlines() if "freeze" in l.lower()]
    checks["freeze_warnings"] = freeze_lines

    all_pass = all(v for k, v in checks.items() if k.endswith("_ok"))
    checks["overall"] = "PASS" if all_pass else "FAIL"

    (OUT / "qa_report.json").write_text(json.dumps(checks, indent=2))
    print(json.dumps(checks, indent=2))
    print("contact_sheet_final.png ok")
    print("transition_contact_sheet.png ok")


if __name__ == "__main__":
    main()
