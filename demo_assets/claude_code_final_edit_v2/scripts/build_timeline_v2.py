"""V2 timeline: tighter pacing, slow-zoom stills, dedicated outro card."""
import json
from pathlib import Path

ROOT = Path("/home/hz/Desktop/BlackBox")
PACK = ROOT / "demo_assets/editor_raw_footage_pack"
EDIT = ROOT / "demo_assets/claude_code_final_edit_v2"
OUT_DIR = EDIT / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CL = PACK / "clips"
ST = PACK / "stills"

# Each segment: video has {src,in,out,zoom?}, still has {src,still_dur,zoom?}.
# zoom=True applies subtle 1.0->1.04 zoompan to break dead frame on stills/charts.
TIMELINE = [
    # 1. HOOK (0-11) — 11s, fast
    {"id": "h1", "src": CL/"13_sanfer_real_camera_broll.mp4", "in": 0.0, "out": 6.0,
     "captions": [(0.2, "Operator: \"GPS failed under the tunnel.\"")]},
    {"id": "h2", "src": CL/"09_operator_refutation_report.mp4", "in": 0.0, "out": 5.0,
     "captions": [(0.0, "Black Box checked the recording."),
                  (2.4, "That story is wrong.")]},

    # 2. PROBLEM (11-24) — 13s
    {"id": "p1", "src": CL/"12_telemetry_files_broll.mp4", "in": 0.0, "out": 6.0,
     "captions": [(0.0, "Hours of video, lidar, telemetry, controller logs.")]},
    {"id": "p2", "src": CL/"14_multicam_composite_real.mp4", "in": 0.0, "out": 7.0,
     "captions": [(0.0, "Evidence exists. Forensic review is still manual.")]},

    # 3. SETUP (24-35) — 11s
    {"id": "s1", "src": CL/"01_intake_upload_ui.mp4", "in": 0.0, "out": 11.0,
     "captions": [(0.0, "One real driving session. No labels."),
                  (5.0, "Operator's note: check the tunnel.")]},

    # 4. AGENT (35-52) — 17s
    {"id": "a1", "src": CL/"03_managed_agent_stream_ui.mp4", "in": 0.0, "out": 9.0,
     "captions": [(0.0, "Not a one-shot summary."),
                  (3.0, "Opus 4.7 runs as a managed forensic agent."),
                  (6.0, "Tools, memory, streaming events.")]},
    {"id": "a2", "src": CL/"02_live_analysis_ui.mp4", "in": 4.0, "out": 12.0,
     "captions": [(0.0, "Project memory carries forward across runs.")]},

    # 5. VISUAL MINING (52-66) — 14s
    {"id": "v1", "src": CL/"14_multicam_composite_real.mp4", "in": 2.0, "out": 8.0,
     "captions": [(0.0, "Doesn't send every frame."),
                  (3.0, "Telemetry selects suspicious windows.")]},
    {"id": "v2", "src": CL/"05_report_exhibits_ui.mp4", "in": 0.0, "out": 8.0,
     "captions": [(0.0, "High-res visual mining checks relevant cameras.")]},

    # 6. REFUTATION (66-93) — 27s — narrative climax
    {"id": "r1", "src": CL/"09_operator_refutation_report.mp4", "in": 0.0, "out": 11.0,
     "captions": [(0.0, "The tunnel mildly degraded GNSS."),
                  (3.5, "But the RTK heading failure started"),
                  (5.5, "43 minutes earlier."),
                  (8.0, "Drive-by-wire was never engaged.")]},
    {"id": "r2", "src": CL/"04_report_overview_ui.mp4", "in": 0.0, "out": 13.0,
     "captions": [(0.0, "The tunnel could not have caused this."),
                  (4.0, "Verdict: operator hypothesis refuted."),
                  (8.5, "Cause sits lower in the stack.")]},
    {"id": "r3", "src": ST/"operator_refutation.png", "still_dur": 3.0, "zoom": True,
     "captions": [(0.0, "Operator hypothesis: refuted.")]},

    # 7. ROOT CAUSE (93-113) — 20s
    {"id": "rc1", "src": CL/"10_rtk_root_cause_charts.mp4", "in": 0.0, "out": 12.0,
     "captions": [(0.0, "Moving-base antenna: healthy."),
                  (4.0, "Rover: never receives valid RTK heading."),
                  (8.0, "Correction path broken before leaving the lot.")]},
    {"id": "rc2", "src": ST/"rtk_root_cause_chart.png", "still_dur": 3.0, "zoom": True,
     "captions": [(0.0, "carr=NONE 100%. REL_POS_VALID never set.")]},
    {"id": "rc3", "src": CL/"11_sanfer_pdf_scroll.mp4", "in": 0.0, "out": 5.0,
     "captions": [(0.0, "Findings written to a forensic report.")]},

    # 8. PATCH (113-131) — 18s
    {"id": "px1", "src": CL/"06_patch_diff_ui.mp4", "in": 0.0, "out": 13.0,
     "captions": [(0.0, "Output isn't a report — it's a scoped patch."),
                  (4.5, "RTCM message IDs. UART link check."),
                  (9.0, "Plus a human-review gate.")]},
    {"id": "px2", "src": ST/"patch_diff.png", "still_dur": 3.0, "zoom": True,
     "captions": [(0.0, "Black Box proposes. Engineer approves.")]},
    # tail UI frame for movement
    {"id": "px3", "src": CL/"06_patch_diff_ui.mp4", "in": 11.5, "out": 13.4,
     "captions": []},

    # 9. OPUS 4.7 (131-147) — 16s
    {"id": "o1", "src": CL/"19_opus47_delta_panel_real_capture.mp4", "in": 0.0, "out": 6.0,
     "captions": [(0.0, "Opus 4.7 vs 4.6, same benchmark slice."),
                  (3.0, "Same accuracy. Better judgment.")]},
    {"id": "o2", "src": CL/"20_vision_ab_artifact.mp4", "in": 0.0, "out": 6.0,
     "captions": [(0.0, "4.7 sees fine visual details 4.6 loses.")]},
    {"id": "o3", "src": CL/"17_opus47_delta_doc_scroll.mp4", "in": 6.0, "out": 10.0,
     "captions": [(0.0, "On under-specified cases, 4.7 abstains.")]},

    # 10. BREADTH (147-161) — 14s
    {"id": "b1", "src": CL/"07_cases_archive_ui.mp4", "in": 0.0, "out": 6.0,
     "captions": [(0.0, "Not a single-car demo.")]},
    {"id": "b2", "src": CL/"15_boat_report_broll.mp4", "in": 0.0, "out": 4.0,
     "captions": [(0.0, "More cars. A robotic boat.")]},
    {"id": "b3", "src": CL/"16_other_car_run_broll.mp4", "in": 0.0, "out": 4.0,
     "captions": [(0.0, "Clean recordings and injected failures.")]},

    # 11. GROUNDING (161-170) — 9s
    {"id": "g1", "src": CL/"08_grounding_gate_ui.mp4", "in": 0.0, "out": 9.0,
     "captions": [(0.0, "When evidence is weak, it refuses to invent a bug."),
                  (4.5, "No evidence. No claim.")]},

    # 12. OUTRO (170-176) — 6s — title-card built from real stills
    {"id": "out1", "src": ST/"breadth_cases_archive.png", "still_dur": 3.0, "zoom": True,
     "captions": [(0.0, "Open benchmark. Reproducible runs.")]},
    {"id": "out2", "src": ST/"hero_report_top.png", "still_dur": 3.0, "zoom": True,
     "captions": [(0.0, "Robot forensics in minutes, for cents.")]},
]


def main():
    cur = 0.0
    timeline = []
    captions = []
    for seg in TIMELINE:
        if "still_dur" in seg:
            dur = seg["still_dur"]
            entry = {"id": seg["id"], "kind": "still", "src": str(seg["src"]),
                     "duration_s": dur, "start_s": cur, "end_s": cur + dur,
                     "zoom": seg.get("zoom", False)}
        else:
            dur = seg["out"] - seg["in"]
            entry = {"id": seg["id"], "kind": "video", "src": str(seg["src"]),
                     "in_s": seg["in"], "out_s": seg["out"],
                     "duration_s": dur, "start_s": cur, "end_s": cur + dur}
        timeline.append(entry)
        for off, text in seg.get("captions", []):
            captions.append({"start_s": cur + off, "text": text, "seg_id": seg["id"]})
        cur += dur
    for i, c in enumerate(captions):
        seg = next(s for s in timeline if s["id"] == c["seg_id"])
        next_start = captions[i + 1]["start_s"] if i + 1 < len(captions) else cur
        c["end_s"] = min(next_start - 0.05, seg["end_s"] - 0.05)
        if c["end_s"] <= c["start_s"]:
            c["end_s"] = c["start_s"] + 1.2

    # major chapter boundaries (segment indices BEFORE which we crossfade)
    # 4 strategic 0.2s xfades: hook->problem (idx 2), mining->refutation (idx 8),
    # patch->opus (idx 16), grounding->outro (idx 25)
    xfade_at = ["p1", "r1", "o1", "out1"]
    out = {"total_duration_s": cur, "segments": timeline, "captions": captions,
           "target_fps": 30, "target_w": 1920, "target_h": 1080,
           "xfade_at_segment_ids": xfade_at, "xfade_dur": 0.25}
    p = OUT_DIR / "timeline_v2.json"
    p.write_text(json.dumps(out, indent=2))
    print(f"wrote {p} total={cur:.2f}s segments={len(timeline)} captions={len(captions)}")


if __name__ == "__main__":
    main()
