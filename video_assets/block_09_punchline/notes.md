# block_09_punchline — notes

## Exact sanfer artifacts used
- `data/final_runs/sanfer_tunnel/report.md` — real post-mortem. Case header ("sanfer_tunnel · post_mortem"), duration (3626.70 s), model (claude-opus-4-7), and five-row executive-summary confidences (0.60 / 0.55 / 0.35 / 0.15 / 0.05) rendered verbatim.
- Ranked outcome card mirrors the report's executive summary exactly:
  - #1 `sensor_timeout` 0.60 ROOT
  - #2 `missing_null_check` 0.55 supporting
  - #3 `other` 0.35 partial
  - #4 `latency_spike` 0.15 symptom
  - #5 `other` 0.05 REFUTED (operator tunnel narrative)
- Report prose excerpt is the actual blockquote from the report: moving-baseline RTCM uplink dead, `carr_soln` never leaves `none`, 18,133/18,133 NAV-RELPOSNED messages.
- Patch card hunk is the real `localization/engage_gate.py` `can_engage` guard from `demo_assets/analyses/sanfer_tunnel.json.patch_proposal` (same source block_08 uses); trimmed to 9 rows to fit a 540 px card.
- Bundle path `data/final_runs/sanfer_tunnel/` is the actual directory containing `report.md`, `report.pdf`, `analysis.json`, `bundle/`.

## What is real
- All confidence numbers, bug-class labels, the ROOT / REFUTED tags.
- File name `scoped_patch.diff`, file header, hunk header, every add/del/ctx line — all from the real patch_proposal.
- Report metadata block (case, duration, model).
- Counts `Timeline · 13 rows`, `Hypotheses · 5 ranked`, `Patch proposal · 1 hunk` all match the report.

## What is composited
- All layout, typography, card geometry, three-slot composition, staggered reveal, dim-for-focus transition, accent strip, brand lockup. No product UI screenshot.
- The "forensic report" card is a hand-built summary of the real `report.md` — it is a compositional stand-in, not a screenshot of any app.
- The ranked-outcome bars (confidence visualization) are drawn from the real numbers but not a literal screenshot of the report's markdown table.
- The 4-dot beat indicator and BLACK BOX lockup are shared film-language elements from blocks 01/02/05/06/07/08.

## What is placeholder
- The report card prose is a prose rendition (7 lines) of the real blockquote — the actual `report.md` exec summary is one long sentence. Fine for the film scale, but it is a re-rendering, not a verbatim crop.
- The ranked-outcome tags ("supporting", "partial", "symptom") are my plain-English labels for the report's longer per-hypothesis framing; swap for verbatim text if desired.
- No literal PDF page crop is shown. `data/final_runs/sanfer_tunnel/bundle/` contains `report.pdf`; embedding a real crop is listed in `remaining_work`.

## UI-independence
- UI-independent. Renders entirely from PIL + ffmpeg. No browser, no product app.

## Why this block supports the VO
- "So the output is not just a summary." → beat A: DELIVERABLE eyebrow + "not just a summary" hero.
- "It is a forensic report," → beat B slot 1: report card with real case/duration/model and the executive-summary prose.
- "ranked hypotheses," → beat B slot 2: ranked card with five real rows and real confidences.
- "and a patch a human can review immediately." → beat B slot 3 + beat C: patch card with real hunk; beat C adds amber strip + "human reviews · system does not auto-apply" annotation.
- Final lockup: "not just a summary." / "ready for review." — restatement of the VO's opening negation and closing stance.

## Visual continuity with finished blocks
- **Palette**: identical BG/FG/DIM/PANEL/BORDER/ACCENT/MUTED_AMBER to blocks 01/02/05/06/07/08.
- **Diff color language**: ADD_BG/ADD_FG, DEL_BG/DEL_FG, HUNK_FG borrowed verbatim from block_08's `render_diff_card`.
- **Typography**: DejaVu Sans / Sans Mono, same weight ramp.
- **Grid**: 80 px backdrop identical to prior blocks.
- **Beat dots**: same 4-dot indicator, bottom-center, label `block 09 · deliverable`.
- **Shadow recipe**: same `shadow_for()` (pad 20, alpha 140, blur 18) used in 05/06/07.
- **Transitions**: 450 ms smoothstep crossfades — same pacing family.
- **Accent ration**: ACCENT amber used only on patch label, patch add-line strip, lockup second line, and hairline dividers — continues the discipline from block_06.

## Energy compared with neighboring blocks
- **vs block_08**: explicitly steps down. No BUG/FIX hero, no single diff-as-hero frame, no amber flood. Patch is one of three cards; it keeps slightly more weight (full ACCENT label + strip) but does not dominate.
- **vs block_05/06**: no new evidence, no timeline, no artifact grid. This block is closure — the investigation is packaged, not re-opened.

## Regenerate later if
- a real cropped PNG of `report.pdf` is preferred over the hand-built report card → swap `render_report_card` with a cropped-PDF paste.
- VO lands before/after 12.5 s → adjust beat D hold (3.0 s is easiest to compress).
- final edit wants all five ranked tags to use the report's verbatim per-hypothesis phrases → update the `rows` list in `render_ranked_card`.

## Status
- **FINAL_READY** for the 3-minute cut.
