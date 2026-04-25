# `scripts/` — taxonomy

Per #90: classify each script as **eval / demo / ops / dev** so evaluators can tell which scripts are core product vs submission artifacts vs one-off utilities. Layout stays flat (Option B); rename/move would break cross-repo references and CI for low gain pre-deadline. A future PR may move into subdirectories — the classification below is the contract that move would honor.

## Categories

- **eval** — benchmark and tier runners. Anything that produces a number that goes into the README or `data/bench_runs/`.
- **demo** — assets for the submission video, screenshots, recording, and asset assembly. Re-runnable but not part of the live forensic loop.
- **ops** — release packaging, batch ops, scheduled runs, cost reporting, anything an operator runs in production-shape.
- **dev** — one-off utilities: ingestion experiments, format probes, salvage tools, ad-hoc data extraction. Useful but not on the critical path.

## Inventory

| Script | Class | One-line purpose |
|---|---|---|
| `run_opus_bench.py` | eval | budgeted benchmark runner producing `data/bench_runs/opus47_<UTC>.json`. README ground truth. |
| `run_rtk_heading_case.py` | eval | hero-case telemetry-only one-shot for the sanfer RTK finding. |
| `run_session.py` | eval | end-to-end forensic session over a folder of bags (real pipeline entry point). |
| `bench_context_mode.py` | eval | context-mode A/B benchmark — measures live vs replay vs sample cost shape. |
| `end_to_end_smoke.py` | eval | smoke harness that walks ingest → analyze → report on the synthetic fixture. |
| `grounding_gate_live.py` | eval | grounding-gate regression on a known-clean window; CI fixture. |
| `hero_analysis.py` | eval | hero analysis driver wrapper. |
| `hero_bag0_indoor.py` | eval | hero-case indoor variant (legacy). |
| `managed_agent_smoke.py` | eval | smoke for the ForensicAgent / Managed Agents wiring. |
| `exercise_steering_live.py` | eval | live verification of `/steer/{job_id}` consumer on the sanfer hero (#129). |
| `analyze_bag.py` | eval | single-bag analysis (legacy v1). |
| `analyze_bag_v2.py` | eval | single-bag analysis (current; v2). |
| `memory_loop_demo.py` | demo | two-run sequence proving memory L1–L4 priors are read and applied (#76). |
| `record_batch_asciicast.py` | demo | produces v2 asciicast of the offline batch runner for `docs/recordings/` (#88). |
| `cost_report.py` | ops | summarize / chart `data/costs.jsonl` — cumulative spend, per-prompt CSV. |
| `overnight_batch.py` | ops | unattended bench runner with budget gates; pairs with `OVERNIGHT_BATCH.md`. |
| `record_replay.py` | ops | record a deterministic replay of a session (compressed). |
| `record_replay_raw.py` | ops | record a raw replay (uncompressed) for forensic re-walk. |
| `regen_reports_md.py` | ops | regenerate `*.md` reports from session artifacts. |
| `legal_review.py` | ops | scan repo for license/legal risk markers (release gating). |
| `snapshot_controllers.py` | ops | freeze the controller source tree for an analysis. |
| `download_sample_bag.py` | ops | fetch the public sample bag (idempotent). |
| `list_managed_memory_stores.py` | ops | list all native managed memory stores (id/name/created/size); JSON or table. |
| `archive_old_case_memory_stores.py` | ops | dry-run/apply deletion of `bb-case-*` stores older than N days; refuses platform store. |
| `delete_case_memory_store.py` | ops | delete one specific managed memory store by id or name; refuses `bb-platform-priors`. |
| `export_memory_versions.py` | ops | dump every memory path's version history from a store to `data/memory_exports/`. |
| `final_pipeline.py` | demo | submission-cut full pipeline driver (long; produces final video assets). |
| `build_grounding_gate_demo.py` | demo | builds the grounding-gate replay demo asset. |
| `build_sanfer_timelapse.py` | demo | timelapse of the sanfer hero session for the demo video. |
| `build_bag_timelapse.py` | demo | generic bag timelapse for promo/demo cuts. |
| `build_multicam_composite.py` | demo | 5-camera composite for the cross-view beat. |
| `build_visual_mining_v2_grid.py` | demo | 5-camera grid PNG anchored on a telemetry window — proof asset for the cross-modal beat (#128). |
| `build_boat_traffic_plot.py` | demo | marine USV traffic plot for the cross-platform demo beat. |
| `capture_screenshots.py` | demo | capture UI screenshots for README / submission. |
| `capture_nao6.py` | demo | NAO6 fixture capture (bonus only — see `NAO6_CAPTURE_GUIDE.md`). |
| `compose_demo.sh` | demo | top-level demo composition driver. |
| `compose_demo_v1_nopad.sh` | demo | demo composition variant: no padding. |
| `compose_demo_v2_xfade.sh` | demo | demo composition variant: crossfade. |
| `compose_demo_v3_nopad_xfade.sh` | demo | demo composition variant: no-pad + crossfade. |
| `compose_demo_v4_xfade_exp.sh` | demo | demo composition variant: experimental xfade. |
| `render_block_01_hook.py` | demo | submission video block 01 — hook. |
| `render_block_02_problem.py` | demo | submission video block 02 — problem. |
| `render_block_03_setup.py` | demo | submission video block 03 — setup. |
| `render_block_04_analysis_live.py` | demo | submission video block 04 — analysis live (v1). |
| `render_block_04_analysis_live_v2.py` | demo | submission video block 04 — analysis live (current). |
| `render_block_05_first_moment.py` | demo | submission video block 05 — first moment. |
| `render_block_06_second_moment.py` | demo | submission video block 06 — second moment. |
| `render_block_07_grounding.py` | demo | submission video block 07 — grounding gate. |
| `render_block_08_money_shot.py` | demo | submission video block 08 — money shot. |
| `render_block_09_punchline.py` | demo | submission video block 09 — punchline. |
| `render_block_10_outro.py` | demo | submission video block 10 — outro. |
| `render_diff.py` | demo | render a unified diff into the demo's HTML aesthetic. |
| `render_rtk_diff.py` | demo | render the RTK diff for the hero-case money shot. |
| `render_rtk_plots.py` | demo | render the RTK telemetry plots for the demo. |
| `salvage_analysis.py` | dev | salvage partial analysis output when a session crashes mid-run. |
| `bag_duration.py` | dev | print bag duration; used during ingestion debugging. |
| `inspect_bag.py` | dev | print bag topic schema / counts; used to bootstrap a new platform adapter. |
| `extract_hires.py` | dev | extract hi-res frames for visual inspection. |
| `extract_window.py` | dev | extract a single timestamped window from a bag (legacy). |
| `extract_windows_v2.py` | dev | windowed extraction (current). |
| `extract_session_frames.py` | dev | dump session frames into a directory. |
| `extract_sanfer_cam.py` | dev | extract sanfer cam frames (legacy). |
| `extract_sanfer_cam_smart.py` | dev | extract sanfer cam frames with smart sub-sampling. |
| `rtk.py` | dev | RTK debugging toolkit — interactive helpers used to author the hero finding. |

## Companion files

- `NAO6_CAPTURE_GUIDE.md` — bonus-platform capture playbook. Tied to the demoted NAO6 scope (#91).

## How to add a new script

Pick the smallest category that fits, then add a row above with a one-line purpose. If a script promotes from `dev` → `eval` (e.g. produces a number you cite in README), update the row and the README's *Status* table.
