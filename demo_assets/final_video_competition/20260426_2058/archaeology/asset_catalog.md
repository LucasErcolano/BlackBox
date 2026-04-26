# BlackBox demo · asset catalog

All probed clips are 1920x1080 @ 30fps, h264. Only `final_video_v2/blackbox_demo_final_v2.mp4` carries audio (aac).

## v2 baseline (preserve as A/B reference master)

`demo_assets/final_demo_pack/final_video_v2/blackbox_demo_final_v2.mp4` — 179.77s — already passes hard gates.

## Approach-2 trimmed_clips (block_NN, all silent)

| Path | dur | beat | verdict | rationale |
|---|---|---|---|---|
| trimmed_clips/block_01_hook.mp4 | 9.00 | 0:00-0:12 | preserve | Operator quote frame; no superior real shot exists |
| trimmed_clips/block_02_problem.mp4 | 10.43 | 0:12-0:25 | preserve | Repo-tree + 55.8GB bag stylized — on-brand |
| trimmed_clips/block_03_setup.mp4 | 14.53 | 0:25-0:38 | modify | Intercut `13_sanfer_real_camera_broll.mp4` for realism |
| trimmed_clips/block_04_analysis_live_v2.mp4 | 21.00 | 0:38-0:55 | preserve | Canonical Playwright REPLAY capture |
| trimmed_clips/block_05_first_moment.mp4 | 17.53 | breadth-insert | preserve | Optional |
| trimmed_clips/block_06_second_moment.mp4 | 17.27 | breadth-insert | preserve | Optional |
| trimmed_clips/block_07_grounding.mp4 | 12.13 | 2:44-2:54 | preserve | JSON strike-through animation; replacing breaks motion design |
| trimmed_clips/block_08_money_shot.mp4 | 11.50 | 1:57-2:15 | modify | Real diff UI from `06_patch_diff_ui.mp4` is realism upgrade |
| trimmed_clips/block_09_punchline.mp4 | 10.07 | 2:54-3:00 | preserve | $0.46 + bench URL load-bearing |
| trimmed_clips/block_10_outro.mp4 | 9.50 | 2:54-3:00 | preserve | Silent logo card |

## Approach-2 panels / charts

- panels/operator_vs_blackbox.png — designed-panel — 1:10-1:37 — preserve (climax, non-negotiable)
- panels/opus47_delta_panel.png — designed-panel — 2:15-2:31 — preserve
- panels/breadth_montage.png — designed-panel — 2:31-2:44 — replace with `07_cases_archive_ui.mp4`
- charts/multicam_composite.png — 0:55-1:10 — preserve
- charts/{rtk_carrier_contrast,rel_pos_valid,rtk_numsv,moving_base_vs_rover}.png — 1:37-1:57 — preserve

## Approach-1 raw clips

| Clip | dur | kind | beat | hero/B/skip | verdict |
|---|---|---|---|---|---|
| 01_intake_upload_ui.mp4 | 11.13 | real-ui | 0:12-0:25 | b-roll | 1.5s flash inside Problem |
| 02_live_analysis_ui.mp4 | 21.53 | real-ui | 0:38-0:55 | hero-alt | replace block_04 alt |
| 03_managed_agent_stream_ui.mp4 | 16.00 | real-ui | 0:38-0:55 | hero | REPLACE candidate |
| 04_report_overview_ui.mp4 | 15.13 | real-ui | 1:10-1:37 | hero | REPLACE candidate (verdict banner) |
| 05_report_exhibits_ui.mp4 | 19.17 | real-ui | 1:37-1:57 | b-roll | intercut behind charts |
| 06_patch_diff_ui.mp4 | 13.40 | real-ui | 1:57-2:15 | hero | REPLACE candidate (real diff UI) |
| 07_cases_archive_ui.mp4 | 13.43 | real-ui | 2:31-2:44 | hero | REPLACE candidate (real /cases) |
| 08_grounding_gate_ui.mp4 | 11.37 | real-ui | 2:44-2:54 | b-roll | 2s tail behind block_07 |
| 09_operator_refutation_report.mp4 | 11.67 | real-artifact | 1:10-1:37 | b-roll | backup, not replacement |
| 10_rtk_root_cause_charts.mp4 | 13.33 | chart | 1:37-1:57 | skip | redundant w/ v2 charts |
| 11_sanfer_pdf_scroll.mp4 | 10.50 | real-artifact | 1:10-1:37 | skip | Q&A safety net |
| 12_telemetry_files_broll.mp4 | 8.37 | real-artifact | 0:25-0:38 | b-roll | 2s flash inside Setup |
| 13_sanfer_real_camera_broll.mp4 | 11.00 | real-camera | 0:00-0:12 / 0:25-0:38 | hero | REPLACE candidate (real bag frames) |
| 14_multicam_composite_real.mp4 | 10.00 | real-camera | 0:55-1:10 | b-roll | intercut for motion |
| 15_boat_report_broll.mp4 | 11.43 | real-artifact | 2:31-2:44 | b-roll | breadth filler |
| 16_other_car_run_broll.mp4 | 11.43 | real-artifact | 2:31-2:44 | b-roll | breadth filler |
| 17_opus47_delta_doc_scroll.mp4 | 21.43 | real-artifact | 2:15-2:31 | b-roll | doc behind opus47 |
| 18_opus47_delta_artifacts_folder.mp4 | 10.37 | real-artifact | 2:15-2:31 | b-roll | bench-JSON proof |
| 19_opus47_delta_panel_real_capture.mp4 | 6.67 | real-artifact | 2:15-2:31 | skip | duplicates v2 panel |
| 20_vision_ab_artifact.mp4 | 8.33 | chart | 2:15-2:31 | b-roll | vision A/B insert |

## Top-3 swap recommendations (panel → real clip)

1. **breadth_montage panel → `07_cases_archive_ui.mp4`** at 2:31-2:44. Real `/cases` UI demonstrates breadth instead of asserting it. Duration matches.
2. **block_08_money_shot composite → `06_patch_diff_ui.mp4`** at 1:57-2:15. Real `/report` diff UI for the patch claim. Realism upgrade on a load-bearing beat.
3. **block_03_setup intercut with `13_sanfer_real_camera_broll.mp4` + `12_telemetry_files_broll.mp4`** at 0:25-0:38. Adds real bag frames + real file listing to break visual repetition.
