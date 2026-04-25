# Editor handoff — Black Box demo, v1 cut

Everything you need is in `demo_assets/final_demo_pack/`. This document is
the only thing you have to read before opening Resolve / Premiere / FCP /
ffmpeg.

## TL;DR

- A v0 stitched cut already lives at `clips/demo_final_v0.mp4`. Watch it
  first. The 10 prebuilt blocks (`block_01..block_10.mp4`) match the beat
  sheet 1:1.
- Three NEW headline panels (`panels/`) were generated this pass and replace
  three improvised slates in v0:
  - `panels/operator_vs_blackbox.png`  → swap into the **1:10–1:37** climax.
  - `panels/opus47_delta_panel.png`    → insert as a **15-s** beat at **2:15**.
  - `panels/breadth_montage.png`       → covers the **2:31–2:44** breadth beat.
- The hero spine is `sanfer_tunnel`. Don't lose the refutation moment.

## Build the v1 cut

Two options.

### Option A — keep the v0 stitch, surgically swap

1. Open `clips/demo_final_v0.mp4`.
2. Replace the placeholder slate at 1:10–1:37 with
   `panels/operator_vs_blackbox.png` (Ken Burns 8% in over 27 s, hold final 4 s).
3. Insert `panels/opus47_delta_panel.png` between `block_08_money_shot` and
   `block_07_grounding` for 16 s (each of the 6 tiles pops in with an 80-ms
   stagger; export-friendly since the source PNG already has a finished layout).
4. Replace whatever currently sits at 2:31–2:44 with
   `panels/breadth_montage.png` (13 s, simple cross-fade in).
5. Re-export at H.264 1080p, 30 fps, ~12 Mbps, AAC 192 kbps.

### Option B — full rebuild from blocks

Use the same concat order in `data/demo/concat.txt` but inject the three new
panels as still-image segments via ffmpeg:

```bash
ffmpeg -loop 1 -t 27 -i panels/operator_vs_blackbox.png \
       -vf "scale=1920:1080,format=yuv420p" -r 30 -c:v libx264 -crf 18 \
       panels/operator_vs_blackbox.mp4
# repeat for opus47_delta_panel.png (16 s) and breadth_montage.png (13 s)
```

Then build a new `concat_v1.txt` interleaving the new still-segments at the
right beats and run `scripts/compose_demo_v1_nopad.sh` (already in repo).

## Re-capturing the live UI (only if styling changed)

```bash
.venv/bin/python -m black_box.ui.app &        # serves at :8000
.venv/bin/python scripts/record_replay.py \
    --url "http://localhost:8000/analyze?replay=sanfer_tunnel&theme=dark" \
    --width 1920 --height 1080 --duration 17 \
    --out clips/block_04_analysis_live_v2.mp4
```

The replay route is the canonical capture surface. The `REPLAY` source badge
must be visible on camera — that is the truth-in-advertising contract.

## Style guardrails (don't violate)

- Palette: bg `#0a0c10`, amber `#ffb840`, teal `#62d4c8`, red `#e0625a`,
  muted `#7a8290`. All three new panels conform.
- Font: DejaVu Sans (display) + DejaVu Mono (code). All three new panels conform.
- Never overlay the word "multimodal." Use "video + logs + telemetry +
  controller code in one prompt."
- Never claim "4.7 is more accurate." Claim "same accuracy, better judgment."
- The patch is **PROPOSED**, not auto-applied. Keep the badge visible at 1:57.

## Top-10 assets, ranked by load-bearing-ness

1. `panels/operator_vs_blackbox.png` — climax. Without this, demo has no point.
2. `clips/block_04_analysis_live_v2.mp4` — proves the UI is real, not mocked.
3. `panels/opus47_delta_panel.png` — sole defense of "why 4.7."
4. `clips/block_08_money_shot.mp4` — proves the output is actionable, not narrative.
5. `charts/moving_base_vs_rover.png` — concrete telemetry receipts.
6. `clips/block_07_grounding.mp4` — anti-hallucination credibility.
7. `panels/breadth_montage.png` — defends "this is not a one-off car demo."
8. `clips/block_09_punchline.mp4` — cost + URL = judges' takeaway.
9. `clips/block_01_hook.mp4` — sets the operator-claim frame in 12 s.
10. `pdfs/sanfer_tunnel.pdf` — backup "is this real?" exhibit if a judge asks
    in Q&A.

## Known gaps

- **Lucas-on-camera webcam shot** in front of the real car for the hook is
  optional; `block_01_hook.mp4` is a stylistic stand-in. If shoot happens,
  spec: 1920×1080 @ 30 fps, 10–12 s, 1 m from front bumper, scratch audio.
- **No NAO6 footage** — cut deliberately per `docs/DEMO_SCRIPT.md`.
- **No live re-capture of `/cases` archive** in the pack — not on the cut
  list per the beat sheet. Add `ui/04_cases.png` only if a future cut
  needs the archive view.

## Sanity checks before export

- [ ] Total runtime 2:55–3:00.
- [ ] `REPLAY` badge visible during the live-analysis beat.
- [ ] Operator quote on screen exactly once and *before* the refutation.
- [ ] 4.7 vs 4.6 panel reads at 1080p (no tile cropped).
- [ ] Cost number ($0.46 or live cost from `data/costs.jsonl`) on screen at outro.
- [ ] Bench URL `github.com/.../black-box-bench` legible for ≥1.5 s.
