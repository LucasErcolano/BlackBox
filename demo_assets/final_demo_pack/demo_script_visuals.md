# Demo script — visual layer

Pairs the VO from `docs/DEMO_SCRIPT.md` with explicit on-screen elements,
overlays, motion, and asset path. One row per beat. Editor reads
left-to-right per row.

| t in | t out | VO | on-screen | overlay / motion | asset (relative to repo root) |
|-----:|------:|----|-----------|------------------|--------------------------------|
| 0:00 | 0:12 | "operator told me the GPS failed under a tunnel… it said he was wrong." | hook block | operator-quote typography, 350 ms cross-fade out | `demo_assets/final_demo_pack/clips/block_01_hook.mp4` |
| 0:12 | 0:25 | "hundreds of bags per week, most theories wrong" | repo tree + 55.8 GB bag tile | static | `…/clips/block_02_problem.mp4` |
| 0:25 | 0:38 | "one hour real driving, ROS1, no labels, 'check the tunnel'" | session JSON panels + 3 frames | parallax pan | `…/clips/block_03_setup.mp4` |
| 0:38 | 0:55 | "Opus 4.7 reads telemetry, carrier-phase, fix quality, REL_POS_VALID" | live UI replay (REPLAY badge) | HTMX stream cursor blinks | `…/clips/block_04_analysis_live_v2.mp4` |
| 0:55 | 1:10 | "five cameras in one prompt" | multicam composite + window overlay | slow Ken Burns L→R | `…/charts/multicam_composite.png` (+ `visual_mining_v2_grid.png`) |
| 1:10 | 1:37 | "tunnel didn't cause it; heading broken 43 min earlier" | refutation card, RED vs TEAL | reveal RED first (200 ms), then TEAL | `…/panels/operator_vs_blackbox.png` |
| 1:37 | 1:57 | "moving-base healthy, rover never locks, REL_POS_VALID never sets" | 4-plot trio (carrier · valid · sats · MB-vs-rover) | quick cut every 3 s, hold final 9 s | `…/charts/rtk_carrier_contrast.png` → `rel_pos_valid.png` → `rtk_numsv.png` → `moving_base_vs_rover.png` |
| 1:57 | 2:15 | "specific message IDs, config diff, proposed for human review" | unified diff with PROPOSED badge | scroll diff slowly | `…/clips/block_08_money_shot.mp4` |
| 2:15 | 2:31 | "same accuracy, better judgment, more eyes" | 6-tile delta panel | each tile pops in 80 ms apart | `…/panels/opus47_delta_panel.png` |
| 2:31 | 2:44 | "other cars, a boat, a clean bag — same pipeline" | 4-up breadth grid | grid reveals tile-by-tile | `…/panels/breadth_montage.png` |
| 2:44 | 2:54 | "clean bag, returns nothing anomalous, will not fabricate" | grounding-gate block | strike-throughs animate, JSON snaps in | `…/clips/block_07_grounding.mp4` |
| 2:54 | 3:00 | "$0.46/run, bench open on GitHub" | cost ledger + URL | URL flashes 200 ms | `…/clips/block_09_punchline.mp4` (+ `clips/block_10_outro.mp4`) |

## Lower-thirds (optional, sparingly)

* 0:38: `model: claude-opus-4-7  ·  source: REPLAY  ·  case: sanfer_tunnel`
* 1:10: `data/final_runs/sanfer_tunnel/report.md  ·  hyp #5: REFUTED conf 0.05`
* 2:15: `bench: black-box-bench/cases/{bad_gain_01, pid_saturation_01, sensor_timeout_01, rtk_heading_break_01}`

## Voice-over posture

* **Calm and forensic.** Not a sales pitch.
* **Cuts at the verb.** "It said he was wrong." Not "…wrong about the cause."
* **Cost is the last word** (`$0.46`). Land it before the URL flashes.
