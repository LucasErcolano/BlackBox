# Black Box — final demo render notes

## Outputs

| file | purpose |
|------|---------|
| `blackbox_demo_final_3min.mp4` | 1920×1080 H.264 + silent AAC stereo · ~2:59.5 · ready to upload |
| `blackbox_demo_final_3min_no_audio.mp4` | identical video, no audio track · NLE master |
| `subtitles.srt` | 23 cues spanning 0:00 → 2:59.5 · burn-in or sidecar |
| `timeline.json` | machine-readable cut sheet (per-segment in/out, asset, beat, motion) |

## Build

```bash
bash scripts/build_final_video.sh
```

Re-encodes every block clip and renders each panel still as a static
1920×1080 / 30 fps / yuv420p / libx264 segment (CRF 18 for clips, CRF 20
`-tune stillimage` for panels), then concats via the ffmpeg concat demuxer.
No NLE required. Ken-burns motion was prototyped but dropped: zoompan over a
3840×2160 source is ~10× slower than the rest of the pipeline combined and
adds nothing on a 14-s readable panel. Add motion in your NLE if desired.

## Edit decision list (cumulative timecode)

| t in   | t out  | beat                            | source                                         |
|--------|--------|---------------------------------|------------------------------------------------|
| 0:00.0 | 0:11.0 | hook                            | `clips/block_01_hook.mp4`                      |
| 0:11.0 | 0:25.5 | problem                         | `clips/block_02_problem.mp4`                   |
| 0:25.5 | 0:44.1 | setup                           | `clips/block_03_setup.mp4`                     |
| 0:44.1 | 1:05.1 | managed-agent loop / live UI    | `clips/block_04_analysis_live_v2.mp4`          |
| 1:05.1 | 1:24.5 | true root cause (evidence)      | `clips/block_06_second_moment.mp4`             |
| 1:24.5 | 1:38.5 | **refutation climax** (NEW)     | `panels/operator_vs_blackbox.png` (static)     |
| 1:38.5 | 1:53.0 | patch diff + human-review gate  | `clips/block_08_money_shot.mp4`                |
| 1:53.0 | 2:07.0 | **Opus 4.7 vs 4.6 delta** (NEW) | `panels/opus47_delta_panel.png` (static)       |
| 2:07.0 | 2:20.0 | **generalization** (NEW)        | `panels/breadth_montage.png` (static)          |
| 2:20.0 | 2:37.5 | grounding gate / abstention     | `clips/block_07_grounding.mp4`                 |
| 2:37.5 | 2:50.0 | cost + repo punchline           | `clips/block_09_punchline.mp4`                 |
| 2:50.0 | 2:59.5 | outro                           | `clips/block_10_outro.mp4`                     |

Total: **179.5 s = 2:59.5**, inside the 2:50–3:00 envelope.

## Constraints checklist

- [x] 2:50–3:00 (179.5 s)
- [x] 1920×1080
- [x] H.264
- [x] Includes `panels/opus47_delta_panel.png`
- [x] Includes `panels/operator_vs_blackbox.png`
- [x] Includes `panels/breadth_montage.png`
- [x] Includes money-shot diff (`block_08_money_shot.mp4`)
- [x] Includes grounding-gate beat (`block_07_grounding.mp4`)
- [x] No NAO6 footage anywhere in the cut
- [x] No claims without an on-screen asset backing them
- [x] No audio track from VO recording → ships **silent + timed captions** (`subtitles.srt`)
- [x] Only stand-in: `block_01_hook.mp4` substitutes the optional Lucas-on-camera webcam shot. Flagged below.

## Dropped from cut (deliberate)

- `clips/block_05_first_moment.mp4` (boat first-moment) — content covered by
  the `breadth_montage` panel; including it would push runtime past 3:00.

## Known gap

- **Webcam-on-Lucas hook**: `block_01_hook.mp4` is the stylistic stand-in.
  When the real shot lands, swap directly into segment #1 of `timeline.json`
  and re-run `scripts/build_final_video.sh`. Length must be ≤ 11.0 s to keep
  total runtime in envelope.

## Burning in captions (optional)

Sidecar `subtitles.srt` is loaded automatically by most players. To burn into
a hard-subbed export:

```bash
ffmpeg -i blackbox_demo_final_3min.mp4 \
       -vf "subtitles=subtitles.srt:force_style='FontName=DejaVu Sans,FontSize=22,PrimaryColour=&H00e7eaee,OutlineColour=&H000a0c10,BorderStyle=3,Outline=2,Shadow=0,MarginV=60'" \
       -c:v libx264 -preset veryfast -crf 18 -c:a copy \
       blackbox_demo_final_3min_subbed.mp4
```

## Reproducibility

All inputs are tracked under `demo_assets/final_demo_pack/`. The script is
deterministic given identical inputs (libx264 with `-preset veryfast` is
deterministic across runs on the same ffmpeg build).
