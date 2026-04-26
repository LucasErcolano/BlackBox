# Black Box — 3-minute demo, shot-by-shot plan

Total runtime target: **2:55–3:00**.
Spine = `sanfer_sanisidro` / sanfer_tunnel hero.
A v0 stitched cut already exists at `clips/demo_final_v0.mp4` (16.8 MB, ten
prebuilt blocks). This plan re-targets the v1 cut against the brief: hero
refutation + Opus 4.7 delta panel + breadth + grounding gate + human-in-loop.

Each beat below lists: window · what's on screen · primary asset · capture
or build instruction · transition · VO posture.

---

## 0:00–0:12 · Hook

* **On screen:** Lucas in front of the real autonomous car, operator quote
  superimposed: *"The tunnel killed the GPS."*
* **Asset:** `clips/block_01_hook.mp4` (prebuilt, 12 s, real palette continuity).
* **VO over:** *"Last week the operator told me the GPS failed when the car
  went under a tunnel. I gave the bag to Black Box. It said he was wrong."*
* **Transition out:** 350 ms cross-fade to dark grid.
* **Manual still required:** webcam clip of Lucas in front of the real car if
  the prebuilt hook is rejected by the editor.

## 0:12–0:25 · Problem

* **On screen:** repo tree + 55.8 GB bag callout + evidence tile grid (video,
  plot, log, controller, trace).
* **Asset:** `clips/block_02_problem.mp4` (prebuilt, 13 s, real bag size).
* **VO:** *"Hundreds of bags per week. Nobody reads them. Everybody has a
  theory. Most theories are wrong."*

## 0:25–0:38 · Setup

* **On screen:** `data/final_runs/{boat_lidar,sanfer_tunnel}/bundle/summary.json`
  panels + three real frames from sanfer.
* **Asset:** `clips/block_03_setup.mp4` (prebuilt, 13 s).
* **VO:** *"One hour of real driving. ROS1 bag. No labels. Operator gave me
  one sentence: 'check the tunnel.'"*

## 0:38–0:55 · Managed agent loop (live analysis)

* **On screen:** the shipped FastAPI/HTMX UI at
  `http://localhost:8000/analyze?replay=sanfer_tunnel&theme=dark` —
  `REPLAY` source badge, stage pills, reasoning stream, polling progress bar.
* **Asset:** `clips/block_04_analysis_live_v2.mp4` (Playwright-captured live UI
  over real `data/final_runs/sanfer_tunnel/stream_events.jsonl`, 17 s).
* **Backup still:** `ui/02_live_panel.png` if the clip stutters.
* **VO:** *"Opus 4.7 reads the telemetry. Carrier-phase, fix quality,
  relative-position validity. Long-horizon agent loop with native memory and
  streaming events."*

## 0:55–1:10 · Visual mining / multi-camera evidence

* **On screen:** 5-camera composite + dense-frame window overlay; cross-view
  call-outs of overpass transit at t≈43:26.
* **Asset:** `charts/multicam_composite.png` + `charts/visual_mining_v2_grid.png`.
* **Build:** already exists. Editor: pan slowly across the composite (Ken Burns).
* **VO:** *"Five cameras in one prompt. The model agrees on the same window."*

## 1:10–1:37 · Refutation of operator hypothesis (CLIMAX)

* **On screen:** `panels/operator_vs_blackbox.png` (left RED card = operator
  blamed tunnel; right TEAL card = Black Box says heading broken from t=0.24 s).
* **Asset:** `panels/operator_vs_blackbox.png` (NEW, 1920×1080, generated from
  real `data/final_runs/sanfer_tunnel/report.md` hyp #5 conf 0.05 REFUTED).
* **Transition:** 200 ms hold on right card after both reveal.
* **VO:** *"The tunnel mildly degraded GNSS — sat count 29 → 16. But the RTK
  heading break started forty-three minutes earlier and drive-by-wire was
  never engaged. Operator is wrong about the cause."*

## 1:37–1:57 · True root cause (telemetry proof)

* **On screen:** moving-base vs rover carrier contrast plot + REL_POS_VALID flat-zero
  trace + sat-count trace.
* **Assets in order:** `charts/rtk_carrier_contrast.png` (3 s) →
  `charts/rel_pos_valid.png` (5 s) → `charts/rtk_numsv.png` (3 s) →
  `charts/moving_base_vs_rover.png` (9 s, hold).
* **VO:** *"Moving-base antenna: clean RTK 94% of the bag. Rover antenna:
  never locks. REL_POS_VALID never sets. The dual-antenna heading pipeline was
  broken before the car left the lot."*

## 1:57–2:15 · Patch / diff / human approval gate

* **On screen:** `clips/block_08_money_shot.mp4` — config diff for ublox_rover
  + ublox_moving_base + ekf_se_map; "PROPOSED — awaiting human review" badge.
* **Asset:** `clips/block_08_money_shot.mp4` (prebuilt, 18 s).
* **VO:** *"Specific message IDs. RTCM3 1077/1087/1097/1127, 4072.0, 4072.1.
  Config diff, not a redesign. Proposed for human review."*

## 2:15–2:31 · Opus 4.7 vs 4.6 delta panel

* **On screen:** `panels/opus47_delta_panel.png` — 6-tile chart "Same accuracy.
  Better judgment. More eyes." (solvable acc 67/67 · abstention 0/100 ·
  Brier 0.239→0.162 · vision 0/3→3/3 · ~30% wall time · cost parity).
* **Asset:** `panels/opus47_delta_panel.png` (NEW, generated from
  `data/bench_runs/opus46_vs_opus47_*.json` + `opus_vision_d1_*.json`).
* **VO:** *"Same single-shot accuracy. But 4.7 abstains when the taxonomy can't
  cleanly tag the case. Better calibrated under wrong operator framing.
  Reads small text in 3.84-MP plots that 4.6 downsamples away. Thirty
  percent faster."*

## 2:31–2:44 · Generalization montage

* **On screen:** four-up `panels/breadth_montage.png` (sanfer hero ·
  car_1 Tier-2 · boat_lidar `/lidar_imu` silent · clean grounding-gate exit).
* **Asset:** `panels/breadth_montage.png` (NEW). Optional inserts:
  `clips/block_05_first_moment.mp4`, `clips/block_06_second_moment.mp4`.
* **VO:** *"Other car runs. A robotic boat. A clean bag. Same pipeline.
  Different robots."*

## 2:44–2:54 · Grounding gate / abstention

* **On screen:** `clips/block_07_grounding.mp4` showing 4 raw hyps → REJECTED
  → `gated_report.json` `"hypotheses": []`, `NO_ANOMALY_PATCH`.
* **Asset:** `clips/block_07_grounding.mp4` + `gated_report.json` overlay.
* **VO:** *"Same tool, clean bag. Returns nothing anomalous. Will not
  fabricate a bug."*

## 2:54–3:00 · Punchline + repo + cost

* **On screen:** `clips/block_09_punchline.mp4` (cost ledger $0.46/run on
  sanfer · benchmark URL `github.com/.../black-box-bench`).
* **VO:** *"One hour of real driving. Forty-six cents. Bench open on GitHub."*
* **Outro:** 200 ms fade to `clips/block_10_outro.mp4` logo (silent).

---

## Cumulative timecheck

12 + 13 + 13 + 17 + 15 + 27 + 20 + 18 + 16 + 13 + 10 + 6 = **180 s = 3:00**.

## Backup cut (slip plan)

If runtime overruns:
1. Drop the `1:37–1:57` plot trio to a single 12-s contact-shot of
   `charts/moving_base_vs_rover.png` only.
2. Cut the breadth montage from 13 → 9 s.
Last to cut: the Opus 4.7 delta panel — that's the differentiator.
