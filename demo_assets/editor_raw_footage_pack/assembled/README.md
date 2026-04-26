# Combined silent cut — v1

Assembled from the 20 raw clips in `../clips/` per the manifest's `suggested_beat`
fields. Silent on purpose — VO (ElevenLabs) is muxed downstream.

**Output:** `blackbox_demo_combined_silent_v1.mp4` — 1920x1080, 30fps, h264, ~2:43, ~53MB.

**Build:** `bash build_combined.sh` (re-runs ffmpeg over `../clips/` → `/tmp/bb_combined/`).

## Cut order

| # | Beat | Source clip | Trim |
|---|------|-------------|------|
|  1 | Hook: real robot footage         | `13_sanfer_real_camera_broll.mp4`        | 10.0s |
|  2 | Operator-facing intake           | `01_intake_upload_ui.mp4`                | 10.0s |
|  3 | Live analysis running            | `02_live_analysis_ui.mp4`                | 14.0s |
|  4 | Managed agent stream             | `03_managed_agent_stream_ui.mp4`         | 12.0s |
|  5 | Verdict reveal                   | `04_report_overview_ui.mp4`              | 13.0s |
|  6 | Operator vs BlackBox refutation  | `09_operator_refutation_report.mp4`      | 11.0s |
|  7 | RTK root-cause evidence          | `10_rtk_root_cause_charts.mp4`           | 13.0s |
|  8 | Scoped patch / human review      | `06_patch_diff_ui.mp4`                   | 12.0s |
|  9 | Opus 4.7 model delta             | `17_opus47_delta_doc_scroll.mp4`         | 14.0s |
| 10 | 4.6 vs 4.7 vision detail         | `20_vision_ab_artifact.mp4`              |  8.0s |
| 11 | Breadth: cases archive           | `07_cases_archive_ui.mp4`                | 12.0s |
| 12 | Second car run                   | `16_other_car_run_broll.mp4`             |  9.0s |
| 13 | Robotic boat case                | `15_boat_report_broll.mp4`               |  9.0s |
| 14 | Grounding gate (refuses to invent) | `08_grounding_gate_ui.mp4`             | 10.0s |
| 15 | Delta panel close                | `19_opus47_delta_panel_real_capture.mp4` |  6.5s |

Total target: 163.5s.

## Skipped (overlap with picks)

- `05_report_exhibits_ui.mp4` — covered by 04
- `11_sanfer_pdf_scroll.mp4` — covered by 04 + 10
- `12_telemetry_files_broll.mp4` — covered by 13 + 16
- `14_multicam_composite_real.mp4` — covered by 13
- `18_opus47_delta_artifacts_folder.mp4` — covered by 17 + 19

Easy to swap any in by editing the `SLOTS` array in `build_combined.sh`.
