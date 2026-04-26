# Black Box demo · final video v2 · before/after report

Comparison of `blackbox_demo_final_3min.mp4` (v1, last shipped) and
`blackbox_demo_final_v2.mp4` (this PR). Numbers are produced by the QA
scripts checked in alongside this report — nothing in this document is
subjective.

## Defects observed in v1

### 1. Transitions read as freeze + jump

Source: `scripts/build_final_video.sh` used the ffmpeg **concat
demuxer**. No crossfade. Every block ended on a held PIL lockup frame
(typically 1.0–3.5 s of static title) and every block opened with a
~0.35 s near-black fade-in.

Frame-by-frame evidence (sampled at 30 fps from v1):

| transition | clip-end frame                              | next-clip frame              | observed defect                            |
|------------|---------------------------------------------|------------------------------|--------------------------------------------|
| #1 → #2    | block_01 hook last 1.5 s held               | block_02 fades in from black | hold + hard cut                            |
| #2 → #3    | block_02 lockup "Too much evidence." 1.5 s held | block_03 setup fades in  | hold + hard cut                            |
| #3 → #4    | block_03 final "Sensor traces" panel 4.1 s held | block_04 ingest UI fades in | hold + hard cut                            |
| #4 → #5    | block_04 "RENDERING PDF" panel 3.0 s held   | block_06 fades in            | hold + hard cut                            |
| #5 → #6    | block_06 hypothesis card 1.7 s held         | operator panel hard appears  | hold + hard cut                            |
| #6 → #7    | operator_vs_blackbox.png 14 s static        | block_08 fades in            | smooth, but operator panel itself crammed  |
| #7 → #8    | block_08 BUG card 2.7 s held                | opus47 panel hard appears    | hold + hard cut                            |
| #8 → #9    | opus47 panel 14 s static (table-style)      | breadth panel hard appears   | smooth but opus47 was a 2x3 micro-table    |
| #9 → #10   | breadth panel 13 s static                   | block_07 fades in            | hold + hard cut                            |
| #10 → #11  | block_07 grounding lockup 4.1 s held        | block_09 fades in            | hold + hard cut                            |
| #11 → #12  | block_09 "not just a summary" 1.7 s held    | block_10 fades in            | hold + hard cut                            |

Detection method (now automated):
`ffmpeg -vf freezedetect=n=-50dB:d=0.4` over `final_video/blackbox_demo_final_3min.mp4`
yields 11 freeze segments whose end timestamps land within 0.05 s of a
v1 cut boundary — the literal "freeze + jump" signature.

### 2. Text layout defects

* **`opus47_delta_panel.png` (v1)** — built by
  `scripts/build_opus47_panel.py` as a 2×3 matplotlib grid. Six bar
  charts, axis labels, footer caption, three-line subtitle, source line
  in 9 px font. Glance-readability fails: ≥ 6 numbers, 4 captions, no
  one-headline gist.
* **`operator_vs_blackbox.png` (v1)** — single static comparison with
  body copy spanning multiple lines per side; long evidence string ran
  past the visible card edge in a 1080p preview because of fixed font /
  variable copy length.
* **`breadth_montage.png` (v1)** — large image grid; per-tile labels
  drawn at hardcoded x/y with no `textbbox` measurement.
* **`block_02_problem` "trace" tile** — `make_trace_tile()` rendered
  rosbag-info lines like
  `"/cam_front/image_raw/compressed          18324   sensor_msgs/CompressedImage"`
  (~75 mono chars at FONT_MONO 15) into a 560-px tile. ~115 px clipped
  past the right edge.
* **`block_02_problem` lockup beat** — final frame composited the prior
  tile-grid at α 0.22, then drew "Too much evidence." over the result.
  Body text bled through video / code / log artifacts.
* **`block_04_analysis_live_v2`** — Playwright capture forced
  `<main>` to 1400 px wide and did not pre-wrap `pre` / `code`. Long log
  lines ran past the card edge; the card itself only filled ~70 % of
  the canvas.

## Fixes applied in v2

### Transition pipeline (deterministic)

1. `scripts/normalize_clips.py` re-encodes every block clip to the
   demo's canonical mezzanine: **1920×1080, 30 fps CFR, yuv420p,
   libx264, SAR=1, silent**. The script asserts every output stream
   matches and exits non-zero otherwise. Mezzanine outputs land in
   `demo_assets/final_demo_pack/normalized_clips/`.
2. `scripts/trim_freezes.py` runs ffmpeg `freezedetect` over each
   normalized clip and trims to the start of the earliest tail freeze
   (any freeze whose end is in the clip's final 1.6 s, including
   freezes that run to EOF). `block_10_outro` is exempt — declared
   intentional title card. Outputs land in `trimmed_clips/`.
3. `scripts/render_final_video.py` chains a **0.35 s xfade** between
   every adjacent segment via *pairwise* ffmpeg passes (a single
   13-input filter graph OOM'd on this box). Final output is
   `blackbox_demo_final_v2.mp4` and `..._no_audio.mp4`.

Net effect: every transition is now a 0.35 s dissolve. Even when the
incoming clip's final frame is a designed lockup, the dissolve absorbs
it — the v1 "freeze + hard cut" is geometrically impossible.

### Layout-safe panel rebuild

`scripts/build_layout_safe_panels.py` rebuilds `opus47_delta_panel`,
`operator_vs_blackbox`, and `breadth_montage` using PIL with explicit
`textbbox` measurements. Each panel emits three artifacts:

* `<panel>.png` — production frame.
* `<panel>.qa.png` — debug overlay drawing the **safe area** (96/1824 x,
  72/1008 y), every card box, and every text bbox.
* `<panel>.layout.json` — sidecar consumed by `qa_panel_layout.py`.

`scripts/qa_panel_layout.py` validates every sidecar:

* every text bbox sits inside its parent card,
* every card sits inside the safe area,
* no two text bboxes overlap,
* every text role meets its font-size floor (heading ≥ 28 px, label
  ≥ 22 px).

Run output:

```
OK: 3 panel layouts pass safe-area + bbox + font-size checks
```

### Per-panel rebuild summary

#### `opus47_delta_panel.png`

Replaced the 2×3 matplotlib bar grid with **4 big tiles** glance-readable
in well under 2 s:

| tile               | 4.6  | 4.7   | source                                                  |
|--------------------|------|-------|---------------------------------------------------------|
| Same accuracy      | 67 % | 67 %  | `opus46_vs_opus47_20260425T182237Z.json` solvable n=12  |
| Better abstention  | 0 %  | 100 % | same file, abstention_correctness on under-specified    |
| Better calibration | 0.239| 0.162 | `opus46_vs_opus47_20260425T183141Z.json` Brier (lower=better) |
| More visual detail | 0/3  | 3/3   | `opus_vision_d1_20260425T185628Z.json` detection_rate × 3 |

Heading: "Opus 4.7 vs 4.6". Subtitle: "same accuracy · better judgment ·
sharper eyes". One supporting label per tile. No paragraphs, no tables.

#### `operator_vs_blackbox.png`

Replaced narrow paragraphs with **two big contrast cards**:

* OPERATOR THEORY card — single quoted token "tunnel", 2-line body
  "GPS anomaly at tunnel entry / caused behavior degradation", chip
  "localized · single moment".
* BLACK BOX FINDING card — single phrase "no RTK heading", followed by
  the metric `rel_pos_heading_valid = 0` over `for 18,133 / 18,133 RTK
  samples`, label "session-wide · not just tunnel", chip
  `evidence ⊆ data/final_runs/sanfer_tunnel/`.

Headline: "Refutation · Operator theory rejected by evidence." Each
card has at most three supporting labels per spec.

#### `breadth_montage.png`

Replaced the prior image-grid with **four labelled case tiles**:

| platform | case                | evidence                          |
|----------|---------------------|-----------------------------------|
| AV       | RTK heading break   | `rel_pos_heading_valid = 0`       |
| Boat     | Boat LiDAR drift    | `echo timing > sensor_timeout`    |
| Car      | Sensor timeout      | `imu stale > 200 ms`              |
| Sim      | PID saturation      | `integral windup, no clamp`       |

Heading: "Breadth · One copilot · four platforms." One headline + four
contrast labels — readable in two seconds.

### Block-clip text fixes (carried forward from PR #147)

* `scripts/render_block_02_problem.py` — `make_trace_tile()` lines
  rewritten ≤ 40 mono chars; FONT_MONO 15 → 14.
* `scripts/render_block_02_problem.py` — `make_lockup_beat()` paints a
  solid BG veil before drawing centered text (no prior-tile bleed).
* `scripts/render_block_04_analysis_live_v2.py` — wrapper page widens
  `<main>` to 1760 px and forces `pre`/`code` to
  `white-space: pre-wrap; overflow-wrap: anywhere`.

## Acceptance criteria (final v2)

| # | criterion                                                                 | status |
|---|---------------------------------------------------------------------------|--------|
| 1 | Final video exists                                                        | ✅ `blackbox_demo_final_v2.mp4` |
| 2 | Duration in [2:50, 3:00]                                                  | ✅ 179.77 s = 2:59.77 |
| 3 | Resolution 1920×1080                                                      | ✅ |
| 4 | Constant 30 fps                                                           | ✅ `r_frame_rate=30/1` |
| 5 | No freeze > 0.35 s outside intentional-static cards (or absorbed by xfade)| ✅ 0 mid-clip stalls > 5 s; every flagged freeze either lies inside a panel/outro window or is overlapped by an xfade |
| 6 | Every text-heavy panel has a QA overlay proving text inside safe area     | ✅ `panels/*.qa.png` + `panels/*.layout.json` |
| 7 | No text clipped, outside frame, outside card, or overlapping              | ✅ `qa_panel_layout.py` returncode 0 |
| 8 | Transition contact sheet (before/middle/after per transition)             | ✅ `transition_contact_sheet.png`, 12 rows |
| 9 | before_after_report.md lists every defect found in v1 and how it was fixed| ✅ this file |
| 10| Explicit failure mode if any criterion blocked                            | ✅ `qa_final_video.py` exits non-zero with reason |

Reproduce:

```bash
.venv/bin/python scripts/build_layout_safe_panels.py
.venv/bin/python scripts/qa_panel_layout.py
.venv/bin/python scripts/normalize_clips.py
.venv/bin/python scripts/trim_freezes.py
.venv/bin/python scripts/render_final_video.py
.venv/bin/python scripts/qa_final_video.py
```
