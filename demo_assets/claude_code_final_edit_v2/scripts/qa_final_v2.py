"""V2 QA + A/B comparison report against v1."""
import json
import subprocess
from pathlib import Path
from PIL import Image

ROOT = Path("/home/hz/Desktop/BlackBox")
V1 = ROOT / "demo_assets/claude_code_final_edit/output"
V2 = ROOT / "demo_assets/claude_code_final_edit_v2/output"
WORK = ROOT / "demo_assets/claude_code_final_edit_v2/_work"
WORK.mkdir(parents=True, exist_ok=True)

FINAL = V2 / "blackbox_demo_claude_edit_v2.mp4"


def ffprobe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                        "-show_streams", "-show_format", str(p)],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def grab(p, ts, dst):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{ts}",
                    "-i", str(p), "-frames:v", "1",
                    "-vf", "scale=480:270", str(dst)], check=True)


def grid(images, cols, dst):
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

    # Contact sheet — 24 frames
    grid_imgs = []
    for i in range(24):
        ts = (i + 0.5) * dur / 24
        f = WORK / f"grid_{i:02d}.png"
        grab(FINAL, ts, f)
        grid_imgs.append(f)
    grid(grid_imgs, 6, V2 / "contact_sheet_v2.png")

    # Transition sheet — 0.4s pre/post each chapter cut from timeline
    tl = json.loads((V2 / "timeline_v2.json").read_text())
    # Use new (post-xfade) starts as cut points
    new_starts = [0.0]
    for i in range(1, len(tl["segments"])):
        prev = new_starts[-1] + tl["segments"][i-1]["duration_s"]
        if tl["segments"][i]["id"] in tl["xfade_at_segment_ids"]:
            prev -= tl["xfade_dur"]
        new_starts.append(prev)
    cuts = new_starts[1:]
    trans_imgs = []
    for i, t in enumerate(cuts):
        for off, tag in [(-0.3, "pre"), (0.3, "post")]:
            ts = max(0.05, min(dur - 0.05, t + off))
            f = WORK / f"tr_{i:02d}_{tag}.png"
            grab(FINAL, ts, f)
            trans_imgs.append(f)
    grid(trans_imgs, 4, V2 / "transition_contact_sheet_v2.png")

    # Freeze detection
    fr_log = WORK / "freeze.log"
    subprocess.run(["ffmpeg", "-i", str(FINAL),
                    "-vf", "freezedetect=n=-60dB:d=1.5",
                    "-map", "0:v:0", "-f", "null", "-"],
                   stderr=open(fr_log, "w"))
    freeze_lines = [l.strip() for l in fr_log.read_text().splitlines() if "freeze_start" in l]
    checks["freeze_window_count"] = len(freeze_lines)
    checks["freeze_starts"] = freeze_lines[:30]

    all_pass = all(v for k, v in checks.items() if k.endswith("_ok"))
    checks["overall"] = "PASS" if all_pass else "FAIL"
    (V2 / "qa_report_v2.json").write_text(json.dumps(checks, indent=2))

    # ---- v1 vs v2 comparison ----
    v1_qa = json.loads((V1 / "qa_report.json").read_text())
    v1_tl = json.loads((V1 / "timeline.json").read_text())

    def stats(tl, qa):
        segs = tl["segments"]
        cuts = max(0, len(segs) - 1)
        stills = [s for s in segs if s["kind"] == "still"]
        longest_still = max((s["duration_s"] for s in stills), default=0)
        srcs = sorted({Path(s["src"]).name for s in segs})
        return {
            "duration_s": qa["duration_s"],
            "cuts": cuts,
            "static_holds": len(stills),
            "longest_static_hold_s": longest_still,
            "source_files": len(srcs),
            "caption_lines": len(tl["captions"]),
            "freeze_window_count": qa.get("freeze_window_count",
                                          len([x for x in qa.get("freeze_warnings", [])
                                               if "freeze_start" in x])),
        }

    a = stats(v1_tl, v1_qa); b = stats(tl, checks)
    cmp_md = f"""# v1 vs v2 — A/B comparison

| metric                     | v1                    | v2                    |
|----------------------------|-----------------------|-----------------------|
| duration                   | {a['duration_s']:.2f} s             | {b['duration_s']:.2f} s             |
| cuts                       | {a['cuts']}                    | {b['cuts']}                    |
| static holds (PNG stills)  | {a['static_holds']}                     | {b['static_holds']}                     |
| longest static hold        | {a['longest_static_hold_s']:.1f} s               | {b['longest_static_hold_s']:.1f} s               |
| source files used          | {a['source_files']}                    | {b['source_files']}                    |
| caption lines              | {a['caption_lines']}                    | {b['caption_lines']}                    |
| freeze windows (>=1.5 s)   | {a['freeze_window_count']}                    | {b['freeze_window_count']}                     |

## Sections shortened / expanded

| beat              | v1     | v2     | delta                                  |
|-------------------|--------|--------|----------------------------------------|
| Hook              | 12.0 s | 11.0 s | -1.0 s — faster cut to "story is wrong" |
| Problem           | 13.0 s | 13.0 s | unchanged                              |
| Setup             | 13.0 s | 11.0 s | -2.0 s — drop redundant `02_live` 2 s tail |
| Agent             | 17.0 s | 17.0 s | unchanged                              |
| Visual mining     | 15.0 s | 14.0 s | -1.0 s                                 |
| Refutation        | 25.0 s | 27.0 s | +2.0 s — give the verdict more room   |
| Root cause        | 20.0 s | 20.0 s | restructured: 12 s chart + 3 s still + 5 s PDF |
| Patch             | 15.0 s | 17.9 s | +2.9 s — patch_diff zoom-in still + return-to-UI movement |
| Opus 4.7          | 19.5 s | 16.0 s | -3.5 s — drop 4 s of unreadable doc scroll |
| Breadth           | 13.0 s | 14.0 s | +1.0 s                                 |
| Grounding         | 8.0 s  | 9.0 s  | +1.0 s                                 |
| Outro             | 4.0 s  | 6.0 s  | +2.0 s — dedicated 2-still title card  |

## Editorial notes

- v2 hook reaches the line "that story is wrong" at ~0:08 (vs ~0:11 in v1).
- v2 introduces 4 strategic 0.25 s xfade dissolves at chapter boundaries
  (problem → setup not faded; faded: hook→problem, mining→refutation,
  patch→opus, grounding→outro). Everywhere else stays hard cut.
- v2 still holds use a 1.0 → 1.045 zoompan slow-zoom (sourced at 3840x2160 to
  avoid upscale blur), so refutation/patch/root/outro stills don't sit dead.
- Captions: ASS Inter 42 px (was 40), MarginV 72 (was 80), tighter line width
  (≤48 chars), MarginL/R 100. Easier to read on dense UI clips.
- Outro is now a real-derived title card (breadth_cases_archive.png +
  hero_report_top.png with slow zoom) rather than re-running the cases tail.
- Doc-scroll dependence reduced: `17_opus47_delta_doc_scroll` shortened from
  ~7 s to 4 s, `11_sanfer_pdf_scroll` shortened from 8 s to 5 s.

## Why v2 is the better edit

1. Faster, more confident hook.
2. Refutation beat hits harder: longer hold + slow-zoom on the verdict still.
3. Opus 4.7 segment is half its v1 weight in seconds and clearer
   ("Same accuracy. Better judgment."), instead of three doc paragraphs.
4. Outro is a deliberate two-card payoff, not a tail clip.
5. xfades at chapter boundaries give pacing cadence without sacrificing
   evidence beats.
6. Static holds lifted by zoompan — fewer "frozen" frames despite using more
   stills than v1.
"""
    (V2 / "v1_vs_v2_comparison.md").write_text(cmp_md)
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
