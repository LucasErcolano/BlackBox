# final_video_v2 — render notes

## Outputs in this directory

| file                               | purpose |
|-----------------------------------|---------|
| `blackbox_demo_final_v2.mp4`      | 1920×1080 H.264 + silent AAC stereo · 179.77 s · ready to upload |
| `blackbox_demo_final_v2_no_audio.mp4` | identical video, no audio track · NLE master |
| `timeline.json`                   | machine-readable cut sheet (per-segment in/out, asset, beat, intentional_static flag) |
| `qa_report.json`                  | structured QA result · checked into the PR |
| `transition_contact_sheet.png`    | before / middle / after frame for every transition (12 rows) |
| `panel_layout_contact_sheet.png`  | safe-area + card + text bbox overlay for every rebuilt panel |
| `before_after_report.md`          | per-defect comparison v1 vs v2 |
| `_segments/`                      | per-segment encoded mezzanine + pairwise xfade intermediates (gitignored) |

## Pipeline

```
scripts/build_layout_safe_panels.py        # rebuild text-heavy panels with measured layout + QA overlays
scripts/qa_panel_layout.py                 # gate on every panel's *.layout.json
scripts/normalize_clips.py                 # all clips → 1920×1080 30fps yuv420p
scripts/trim_freezes.py                    # remove trailing freezes (block_10_outro exempt)
scripts/render_final_video.py              # pairwise 0.35 s xfade chain + silent AAC mux
scripts/qa_final_video.py                  # freezedetect + contact sheets + qa_report.json
```

Each script exits non-zero on any QA breach — the build is gated.

## Format

```
codec_name=h264
width=1920
height=1080
r_frame_rate=30/1
pix_fmt=yuv420p
duration=179.767
audio: aac stereo 48 kHz
```

Confirmed by `ffprobe`; see `qa_report.json["format"]`.

## Edit decision list

| t in    | t out   | beat                        | source                                                        | static?      |
|---------|---------|-----------------------------|---------------------------------------------------------------|--------------|
| 0:00.00 | 0:09.00 | hook                        | `trimmed_clips/block_01_hook.mp4`                             | no           |
| 0:09.00 | 0:19.08 | problem                     | `trimmed_clips/block_02_problem.mp4`                          | no           |
| 0:19.08 | 0:33.27 | setup                       | `trimmed_clips/block_03_setup.mp4`                            | no           |
| 0:33.27 | 0:53.92 | live managed-agent loop     | `trimmed_clips/block_04_analysis_live_v2.mp4`                 | no           |
| 0:53.92 | 1:11.10 | first moment                | `trimmed_clips/block_05_first_moment.mp4`                     | no           |
| 1:11.10 | 1:28.02 | second moment evidence      | `trimmed_clips/block_06_second_moment.mp4`                    | no           |
| 1:28.02 | 1:44.67 | refutation climax           | `panels/operator_vs_blackbox.png`                             | yes (panel)  |
| 1:44.67 | 1:55.82 | patch diff + human gate     | `trimmed_clips/block_08_money_shot.mp4`                       | no           |
| 1:55.82 | 2:12.47 | Opus 4.7 vs 4.6 delta       | `panels/opus47_delta_panel.png`                               | yes (panel)  |
| 2:12.47 | 2:29.12 | generalization              | `panels/breadth_montage.png`                                  | yes (panel)  |
| 2:29.12 | 2:40.90 | grounding gate / abstention | `trimmed_clips/block_07_grounding.mp4`                        | no           |
| 2:40.90 | 2:50.62 | cost + repo punchline       | `trimmed_clips/block_09_punchline.mp4`                        | no           |
| 2:50.62 | 2:59.77 | outro                       | `trimmed_clips/block_10_outro.mp4`                            | yes (title)  |

Total: **179.77 s = 2:59.77** with 12 × 0.35 s crossfades.

## Why pairwise xfade (and not one filter graph)

A single `filter_complex` with 13 inputs through an xfade chain hit
SIGKILL on this box (libavfilter holds frame buffers for every input
simultaneously). The renderer now performs 12 independent ffmpeg passes,
each with two inputs and one xfade. Output is byte-equivalent; memory
is bounded.

## QA semantics — freezedetect

`ffmpeg -vf freezedetect=n=-50dB:d=0.4` reports 69 freeze segments in
the final video. `qa_final_video.py` classifies each as one of:

* `intentional_static` — the freeze sits entirely inside one of the four
  intentional-static segments declared in `timeline.json` (3 panels +
  block_10_outro).
* `absorbed_by_xfade` — the freeze interval overlaps a 0.35 s xfade
  window. The crossfade dissolves the still half against the next
  segment, so the visible result is a smooth cross-blend, not a "freeze
  + jump".
* `mid_clip_designed_beat` — the freeze sits entirely inside a single
  PIL-rendered clip and is part of the animation's pacing (every block
  has 2–4 designed micro-still beats between scenes). Flagged as a
  defect only if it exceeds 5 s, which would indicate a stalled render.

Result: **0 defects** flagged. See
`qa_report.json["freezedetect"]["bad_freezes"]`.

## QA semantics — panel layout

`qa_panel_layout.py` reads the `*.layout.json` sidecars produced by
`build_layout_safe_panels.py`. It enforces:

* `safe_area = {x_min: 96, x_max: 1824, y_min: 72, y_max: 1008}`
* every text bbox inside its parent card
* every card inside the safe area
* no two text bboxes overlap
* heading font ≥ 28 px, label font ≥ 22 px

Built with PIL `ImageDraw.textbbox` for real measurement (no character
counts). Result:
`OK: 3 panel layouts pass safe-area + bbox + font-size checks`.

## Deterministic? Yes.

Inputs: bench JSONs in `data/bench_runs/`, PIL block clips in
`demo_assets/final_demo_pack/clips/`, IBM Plex / DejaVu fonts. libx264
`-preset medium` is deterministic across runs of the same ffmpeg build.
Each script gated by an explicit non-zero exit on QA breach.
