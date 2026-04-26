"""Build timeline.json mapping each second of the demo to source footage + captions."""
import json
from pathlib import Path

ROOT = Path("/home/hz/Desktop/BlackBox")
PACK = ROOT / "demo_assets/editor_raw_footage_pack"
OUT_DIR = ROOT / "demo_assets/claude_code_final_edit/output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CLIPS = PACK / "clips"
STILLS = PACK / "stills"

# Each segment: clip path, in_s, out_s. Stills are passed as PNG with `still_dur`.
# Captions per segment (start_offset_s, text). offset relative to segment start.
TIMELINE = [
    # 1. HOOK (0-12)
    {"id": "h1", "src": CLIPS / "13_sanfer_real_camera_broll.mp4", "in": 0.0, "out": 7.0,
     "captions": [(0.0, "The operator told me the GPS failed under a tunnel.")]},
    {"id": "h2", "src": CLIPS / "09_operator_refutation_report.mp4", "in": 0.0, "out": 5.0,
     "captions": [(0.0, "Black Box checked the recording and said: that story is wrong.")]},

    # 2. PROBLEM (12-25)
    {"id": "p1", "src": CLIPS / "12_telemetry_files_broll.mp4", "in": 0.0, "out": 7.0,
     "captions": [(0.0, "Robotics teams collect hours of video, lidar, telemetry,"),
                  (3.5, "and controller logs.")]},
    {"id": "p2", "src": CLIPS / "14_multicam_composite_real.mp4", "in": 0.0, "out": 6.0,
     "captions": [(0.0, "The evidence exists, but forensic review is still manual.")]},

    # 3. SETUP (25-38)
    {"id": "s1", "src": CLIPS / "01_intake_upload_ui.mp4", "in": 0.0, "out": 11.0,
     "captions": [(0.0, "One real driving session. No labels."),
                  (5.5, "Just the operator's note: check the tunnel.")]},
    {"id": "s2", "src": CLIPS / "02_live_analysis_ui.mp4", "in": 0.0, "out": 2.0,
     "captions": [(0.0, "Black Box opens it as a forensic case.")]},

    # 4. MANAGED AGENT (38-55)
    {"id": "a1", "src": CLIPS / "03_managed_agent_stream_ui.mp4", "in": 0.0, "out": 10.0,
     "captions": [(0.0, "Not a one-shot summary."),
                  (3.0, "Opus 4.7 runs as a managed forensic agent —"),
                  (6.0, "reading files, calling tools, streaming events.")]},
    {"id": "a2", "src": CLIPS / "02_live_analysis_ui.mp4", "in": 5.0, "out": 12.0,
     "captions": [(0.0, "Memory carries forward across runs.")]},

    # 5. VISUAL MINING (55-70)
    {"id": "v1", "src": CLIPS / "14_multicam_composite_real.mp4", "in": 0.0, "out": 8.0,
     "captions": [(0.0, "It doesn't send every frame."),
                  (3.0, "Telemetry selects suspicious windows.")]},
    {"id": "v2", "src": CLIPS / "05_report_exhibits_ui.mp4", "in": 0.0, "out": 7.0,
     "captions": [(0.0, "High-resolution visual mining checks the relevant cameras.")]},

    # 6. REFUTATION (70-95) — 25s
    {"id": "r1", "src": CLIPS / "09_operator_refutation_report.mp4", "in": 0.0, "out": 11.0,
     "captions": [(0.0, "The tunnel did mildly degrade GNSS."),
                  (4.0, "But the RTK heading failure was already present"),
                  (7.5, "43 minutes earlier.")]},
    {"id": "r2", "src": CLIPS / "04_report_overview_ui.mp4", "in": 0.0, "out": 10.0,
     "captions": [(0.0, "Drive-by-wire was never engaged."),
                  (4.0, "The tunnel could not have caused this.")]},
    {"id": "r3", "src": STILLS / "operator_refutation.png", "still_dur": 4.0,
     "captions": [(0.0, "Operator hypothesis: refuted.")]},

    # 7. ROOT CAUSE (95-115) — 20s
    {"id": "rc1", "src": CLIPS / "10_rtk_root_cause_charts.mp4", "in": 0.0, "out": 12.0,
     "captions": [(0.0, "The real failure is lower level."),
                  (3.5, "Moving-base antenna: healthy."),
                  (7.0, "Rover: never receives valid RTK heading.")]},
    {"id": "rc2", "src": CLIPS / "11_sanfer_pdf_scroll.mp4", "in": 0.0, "out": 8.0,
     "captions": [(0.0, "The correction path was broken before the car left the lot.")]},

    # 8. PATCH (115-130) — 15s
    {"id": "px1", "src": CLIPS / "06_patch_diff_ui.mp4", "in": 0.0, "out": 12.0,
     "captions": [(0.0, "The output isn't just a report."),
                  (3.0, "Scoped patch: RTCM IDs, UART link check,"),
                  (6.5, "and a human-review gate.")]},
    {"id": "px2", "src": STILLS / "patch_diff.png", "still_dur": 3.0,
     "captions": [(0.0, "Black Box proposes. Engineer approves.")]},

    # 9. OPUS 4.7 vs 4.6 (130-150) — 20s
    {"id": "o1", "src": CLIPS / "19_opus47_delta_panel_real_capture.mp4", "in": 0.0, "out": 6.5,
     "captions": [(0.0, "Same benchmark slice. Opus 4.6 vs 4.7."),
                  (3.5, "Same cases, same prompts, same budget.")]},
    {"id": "o2", "src": CLIPS / "17_opus47_delta_doc_scroll.mp4", "in": 5.0, "out": 12.0,
     "captions": [(0.0, "On simple post-mortems they tie."),
                  (3.5, "But robot forensics punishes confident wrong answers.")]},
    {"id": "o3", "src": CLIPS / "20_vision_ab_artifact.mp4", "in": 0.0, "out": 6.5,
     "captions": [(0.0, "4.6 committed on every under-specified case."),
                  (3.5, "4.7 abstained every time.")]},

    # 10. BREADTH (150-163) — 13s
    {"id": "b1", "src": CLIPS / "07_cases_archive_ui.mp4", "in": 0.0, "out": 5.0,
     "captions": [(0.0, "Not a single-car demo.")]},
    {"id": "b2", "src": CLIPS / "15_boat_report_broll.mp4", "in": 0.0, "out": 4.0,
     "captions": [(0.0, "More car sessions. A robotic boat case.")]},
    {"id": "b3", "src": CLIPS / "16_other_car_run_broll.mp4", "in": 0.0, "out": 4.0,
     "captions": [(0.0, "Clean recordings and injected benchmark failures.")]},

    # 11. GROUNDING (163-171) — 8s
    {"id": "g1", "src": CLIPS / "08_grounding_gate_ui.mp4", "in": 0.0, "out": 8.0,
     "captions": [(0.0, "When evidence is weak, it refuses to invent a bug."),
                  (4.0, "No evidence. No claim.")]},

    # 12. OUTRO (171-175) — 4s
    {"id": "out1", "src": CLIPS / "07_cases_archive_ui.mp4", "in": 8.0, "out": 12.0,
     "captions": [(0.0, "Open benchmark. Reproducible runs."),
                  (2.0, "Robot forensics in minutes, for cents.")]},
]


def main():
    cur = 0.0
    timeline = []
    captions = []
    for seg in TIMELINE:
        if "still_dur" in seg:
            dur = seg["still_dur"]
            entry = {"id": seg["id"], "kind": "still", "src": str(seg["src"]),
                     "duration_s": dur, "start_s": cur, "end_s": cur + dur}
        else:
            dur = seg["out"] - seg["in"]
            entry = {"id": seg["id"], "kind": "video", "src": str(seg["src"]),
                     "in_s": seg["in"], "out_s": seg["out"],
                     "duration_s": dur, "start_s": cur, "end_s": cur + dur}
        timeline.append(entry)
        for off, text in seg.get("captions", []):
            captions.append({"start_s": cur + off, "text": text, "seg_id": seg["id"]})
        cur += dur
    # set caption end times: until next caption start, capped to seg end
    for i, c in enumerate(captions):
        seg = next(s for s in timeline if s["id"] == c["seg_id"])
        next_start = captions[i + 1]["start_s"] if i + 1 < len(captions) else cur
        c["end_s"] = min(next_start - 0.05, seg["end_s"] - 0.05)
        if c["end_s"] <= c["start_s"]:
            c["end_s"] = c["start_s"] + 1.0

    out = {"total_duration_s": cur, "segments": timeline, "captions": captions,
           "target_fps": 30, "target_w": 1920, "target_h": 1080}
    p = OUT_DIR / "timeline.json"
    p.write_text(json.dumps(out, indent=2))
    print(f"wrote {p} total={cur:.2f}s segments={len(timeline)} captions={len(captions)}")


if __name__ == "__main__":
    main()
