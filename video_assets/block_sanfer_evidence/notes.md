# block_sanfer_evidence — production notes

70.0 s · 1920×1080 · 30 fps · h264 · CRF 18 · no UI dependency.

Render script: `scripts/render_block_sanfer_evidence.py`.

## Narrative spine

Wrong operator hypothesis → evidence refutes it → real cause → scoped fix proposal.

| t (s)    | Beat                  | What's on screen                                                  |
|----------|-----------------------|-------------------------------------------------------------------|
| 0–10     | visual mining         | 5-cam grid + 7-window telemetry strip (priorities)                |
| 10–22    | operator hypothesis   | "el GPS falla cuando entramos al túnel." + provisional triage     |
| 22–32    | refutation            | rover numSV plot · REFUTED strike-through                         |
| 32–52    | real root cause       | carrier-phase contrast plot + REL_POS_VALID flat zero + stat card |
| 52–70    | scoped patch          | 3-file diff with slow vertical pan + human-review caveat          |

## Source artifacts (real vs. generated)

### Real bag-derived artifacts (ground-truth, do not relabel)

- `data/runs/sanfer_sanisidro__no_prompt/frames/w03___cam{1..5}_image_raw_compressed_04_*.jpg` — five real camera frames from the Sanfer 1-hour bag, window 3, slot 4. Used in beat A.
- `data/runs/sanfer_sanisidro__no_prompt/windows.json` — 7 candidate windows, rendered verbatim on the timeline strip (centers, spans, priorities).
- `black-box-bench/cases/rtk_heading_break_01/telemetry.npz` — upstream telemetry for the three plots.
- `docs/assets/rtk_numsv.png` — beat C, real `numSV` trace from telemetry.npz.
- `docs/assets/rtk_carrier_contrast.png` — beat D upper plot, real carrier-phase trace.
- `docs/assets/rel_pos_valid.png` — beat D lower plot, real `navrelposned.flags` trace.
- `black-box-bench/runs/sample/rtk_heading_break_01.json` — real Claude analyze output. Beat-D stat-card numbers (CARR_NONE 100% of 18 133, MB FLOAT 63.6% / FIXED 30.7%, REL_POS_VALID 0.0%, DIFF_SOLN 15.0%, conf 0.90) are read directly from this file's evidence array.
- `demo_assets/diff_viewer/moving_base_rover.png` — beat E. Real 3-panel diff produced by `scripts/render_rtk_diff.py` (playwright screenshot of the HTML).

### Statically generated panels (composited in PIL by the render script)

- Beat A title/subtitle/timeline strip backdrop and legend.
- Beat B operator-quote card, provisional-triage card, "what the data must show" checklist.
- Beat C verdict pills + REFUTED strike-through banner echoing the operator quote.
- Beat D right-side `rtk_heading_break_01.json` stat card (numbers sourced from the JSON; layout/typography is generated).
- Beat E left-side concise patch summary + amber "human review required" caveat box.

These are infographic compositions of real numbers, not screenshots of an existing dashboard.

## Claims that must be verified before final cut

1. **Operator quote** — `"el GPS falla cuando entramos al túnel."` is a faithful Spanish paraphrase of the field-note captured in `project_sanfer_finding.md` ("Operator reported 'GPS falla bajo un túnel'"). It is **not** a verbatim transcript of any recorded utterance. Either (a) tag as paraphrase in the final cut, or (b) replace with the exact wording from the original handover note. Do not present as a literal quote without confirmation.
2. **Confidence 0.90** — pulled from `rtk_heading_break_01.json` `hypotheses[0].confidence`. The memory note also references conf 0.9 for the same finding. If the cut reuses an older analysis run, double-check the value.
3. **Stat 18 133** — comes from the JSON evidence string `"FLAGS_REL_POS_VALID set on 0.0% of 18133 samples"`. Cross-check against `windows.json` and the bag's actual `/ublox_rover/navrelposned` count if a precise number is needed on the lower-third in the final cut.
4. **DIFF_SOLN 15.0%** — JSON says "15.0% of samples". Memory note `project_sanfer_finding.md` says "2715/18133 samples" (≈ 14.97%). Numbers are consistent within rounding; pick one representation and stay consistent across blocks.
5. **The operator note** — actual driver was Aayush/Lucas's bag operator, recorded in Spanish. If the final cut subtitles in English, mark the translation as ours, not theirs.
6. **No tunnel data** — the bag does not contain a labelled tunnel segment. We're framing the operator's *hypothesis* as the tunnel theory; the bag was selected because the operator believed a tunnel was responsible. If you want to add a tunnel-frame B-roll, source it externally and label it as illustrative (not from this bag).
7. **Patch is a proposal** — the on-screen caveat ("no auto-apply, no merge") is intentional and matches the project's hard rule that patches are scoped suggestions for human review. Do not add VO that overclaims autonomy.

## Production-side caveats (not story-side)

- Beat E uses a slow vertical pan over the diff PNG. The PNG is `2075×2705`; the visible window is 770×860. The pan eases over t=2–14 s of beat E. If the cut is shortened, retune the pan window in `make_beat_E`.
- The 5-cam grid uses `_small.jpg` peers when `_dense.jpg` peers are absent; we picked the full-resolution variant and resized in PIL to keep text-overlay legibility at 1080p.
- Fonts: DejaVu Sans / Sans Mono only. No external font fetch.
- `block · sanfer evidence · beat X / 5` footer is a render-time guide and may be cropped/replaced in the master timeline.

## Reproduce

```
python3 scripts/render_block_sanfer_evidence.py
```

Outputs land in `video_assets/block_sanfer_evidence/`.
