# BlackBox demo · visual language spec (hybrid v3)

## Canonical
- 1920x1080, 30fps CFR, h264 yuv420p, AAC silent stereo 192k.
- Safe area: x ∈ [96, 1824], y ∈ [72, 1008].
- Bg fallback color: `#0a0c10` (matches block panel BG).
- Transitions: 0.35s xfade between every adjacent segment. No hard cuts. No random zoom.

## Solving prior failure modes

### Failure 1 — "bad clip reel" (approach 1)
Cause: 20 isolated UI/footage clips strung together with no shared rhythm.
Fix in v3: every segment funnels through the same normalize+xfade pipeline as v2 (`render_final_video.py` primitives reused). All clips share the same yuv420p mezzanine and identical `setsar=1`. Visual rhythm is enforced by panel↔clip alternation, not editorial taste.

### Failure 2 — text overlap / panel fatigue (v2)
Cause: 51s of static designed-panel screen-time (28% of runtime). Even with motion-design, the same panel surface returned three times (operator_vs_blackbox, opus47_delta, breadth_montage).
Fix in v3: replace `breadth_montage` with the real `/cases` archive UI clip — same palette, but now demonstrated, not asserted. Net static-panel screen-time drops from 51s → 34s (19% of runtime). Two distinct panels remain: one for the climax (operator vs blackbox), one for the model-delta proof (opus47).

## Shot vocabulary (alternation, not repetition)

| # | shot type            | example asset                                    |
|---|----------------------|--------------------------------------------------|
| 1 | real-camera hook     | block_01_hook (operator quote)                   |
| 2 | repo-tree problem    | block_02_problem                                 |
| 3 | session setup        | block_03_setup                                   |
| 4 | live agent UI        | block_04_analysis_live_v2 (Playwright capture)   |
| 5 | evidence grid        | block_05_first_moment / block_06_second_moment   |
| 6 | refutation panel     | operator_vs_blackbox.png                         |
| 7 | real diff UI         | 06_patch_diff_ui.mp4 (real /report scroll) ★new  |
| 8 | benchmark panel      | opus47_delta_panel.png                           |
| 9 | real archive UI      | 07_cases_archive_ui.mp4 (real /cases) ★new       |
| 10| grounding gate clip  | block_07_grounding (JSON strike-through)         |
| 11| punchline + outro    | block_09_punchline → block_10_outro              |

Final cut alternates real-UI, designed-panel, evidence-clip — no two adjacent segments use the same surface kind.

## Caption / overlay rules
- Every panel asset already passes `qa_panel_layout.py` (font floors, bbox containment, safe-area). Inherited from v2; no new captions burned in v3.
- No additional caption layer added — every burned caption already lives inside its source panel/clip.
- VO/captions are not authored here (no real VO asset in repo). Output ships with silent AAC; downstream voiceover lay-in is non-destructive.

## Motion rules
- All static panels held with no Ken Burns. (v2 already does this — preserved.)
- Only real-UI clips have motion (HTMX scroll, page navigation), which is intrinsic to the capture.
- Xfade is the only inter-segment motion.
