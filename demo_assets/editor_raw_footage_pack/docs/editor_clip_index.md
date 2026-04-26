# Editor clip index

## 01_intake_upload_ui.mp4
- **shows**: Real intake page (/) — mode cards, drop zone, hero copy.
- **source**: live BlackBox UI route /
- **beat**: Setup beat: 'this is the operator-facing intake'.
- **kind**: real UI
- **caveat**: —

## 02_live_analysis_ui.mp4
- **shows**: Live job panel after replay-trigger — pipeline stages, polling.
- **source**: GET /analyze?replay=sanfer_tunnel
- **beat**: Analysis-running beat.
- **kind**: real UI
- **caveat**: —

## 03_managed_agent_stream_ui.mp4
- **shows**: Trace/checkpoints view — managed agent events.
- **source**: GET /trace/{job_id} or /checkpoints
- **beat**: Managed agent / not-one-shot beat.
- **kind**: real UI
- **caveat**: Job ID hand-off may default to /checkpoints if trace ID not parseable.

## 04_report_overview_ui.mp4
- **shows**: Report top — verdict banner, summary scroll.
- **source**: GET /report?case=case_2026_04_18_sanfer
- **beat**: Verdict reveal.
- **kind**: real UI
- **caveat**: —

## 05_report_exhibits_ui.mp4
- **shows**: Report exhibits — telemetry, evidence sections.
- **source**: GET /report?case=...
- **beat**: Evidence montage.
- **kind**: real UI
- **caveat**: —

## 06_patch_diff_ui.mp4
- **shows**: Scoped patch / diff section, deep scroll.
- **source**: GET /report?case=... (deep scroll)
- **beat**: Patch / human-review beat.
- **kind**: real UI
- **caveat**: —

## 07_cases_archive_ui.mp4
- **shows**: Cases archive list — multiple cases.
- **source**: GET /cases
- **beat**: Breadth: 'not a one-off car demo'.
- **kind**: real UI
- **caveat**: —

## 08_grounding_gate_ui.mp4
- **shows**: Inconclusive case report (yard9) — abstention beat.
- **source**: GET /report?case=case_2026_04_12_yard9
- **beat**: Grounding gate / 'refuses to invent a bug'.
- **kind**: real UI
- **caveat**: demo_data falls back to SANFER content for unknown case ids — UI is real.

## 09_operator_refutation_report.mp4
- **shows**: sanfer_tunnel.md rendered & scrolled.
- **source**: demo_assets/final_demo_pack/pdfs/sanfer_tunnel.md
- **beat**: Operator vs BlackBox refutation beat.
- **kind**: real artifact (markdown→html in browser)
- **caveat**: —

## 10_rtk_root_cause_charts.mp4
- **shows**: RTK chart slideshow: moving_base_vs_rover, carrier, rel_pos_valid, num_sv.
- **source**: demo_assets/final_demo_pack/charts/*.png
- **beat**: Root-cause evidence beat.
- **kind**: real artifact (chart slideshow)
- **caveat**: —

## 11_sanfer_pdf_scroll.mp4
- **shows**: Real BlackBox sanfer report PDF, page-by-page.
- **source**: data/final_runs/sanfer_tunnel/report.pdf (pdftoppm)
- **beat**: Forensic report B-roll.
- **kind**: real artifact (PDF render)
- **caveat**: —

## 12_telemetry_files_broll.mp4
- **shows**: File listing of data/final_runs/sanfer_tunnel/ (real entries).
- **source**: filesystem listing
- **beat**: Telemetry/file-system B-roll.
- **kind**: real artifact (file listing)
- **caveat**: Rendered as HTML table, not OS file explorer.

## 13_sanfer_real_camera_broll.mp4
- **shows**: Real extracted camera frames from sanfer_tunnel bag.
- **source**: data/final_runs/sanfer_tunnel/bundle/frames/*.jpg
- **beat**: 'Real robot footage' beat.
- **kind**: real robot footage (extracted frames)
- **caveat**: —

## 14_multicam_composite_real.mp4
- **shows**: 3x2 grid of real frames.
- **source**: same frames
- **beat**: Multi-camera reasoning B-roll.
- **kind**: real robot footage (grid)
- **caveat**: Same camera, sampled at different times — labels minimal.

## 15_boat_report_broll.mp4
- **shows**: boat_lidar report markdown rendered & scrolled.
- **source**: data/final_runs/boat_lidar/report.md
- **beat**: Breadth — robotic boat case.
- **kind**: real artifact (no camera frames available)
- **caveat**: No camera frames in boat_lidar/ — report scroll only. Renamed from boat_real_broll.

## 16_other_car_run_broll.mp4
- **shows**: car_1 report markdown rendered & scrolled.
- **source**: data/final_runs/car_1/report.md
- **beat**: Breadth — second car run.
- **kind**: real artifact
- **caveat**: —

## 17_opus47_delta_doc_scroll.mp4
- **shows**: docs/OPUS47_DELTA.md rendered & scrolled.
- **source**: docs/OPUS47_DELTA.md
- **beat**: Model-delta beat.
- **kind**: real artifact
- **caveat**: —

## 18_opus47_delta_artifacts_folder.mp4
- **shows**: Listing of data/bench_runs/ — real bench JSONs.
- **source**: data/bench_runs/
- **beat**: Model-delta artifact B-roll.
- **kind**: real artifact (listing)
- **caveat**: —

## 19_opus47_delta_panel_real_capture.mp4
- **shows**: Static delta panel PNG with subtle pan.
- **source**: demo_assets/final_demo_pack/panels/opus47_delta_panel.png
- **beat**: Delta beat B-roll.
- **kind**: real artifact (panel image)
- **caveat**: —

## 20_vision_ab_artifact.mp4
- **shows**: Visual mining grid + d1_vision_plot.
- **source**: demo_assets/final_demo_pack/charts/visual_mining_v2_grid.png, d1_vision_plot.png
- **beat**: 4.6 vs 4.7 vision detail beat.
- **kind**: real artifact
- **caveat**: —
