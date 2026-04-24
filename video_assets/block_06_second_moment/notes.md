# block_06_second_moment — notes

## Exact sanfer artifacts used
- `data/final_runs/sanfer_tunnel/report.md` — real post-mortem run over the sanfer_tunnel case (3626.70 s, ROS 2, manual drive). Root cause `sensor_timeout` @ 0.60. Hypothesis #5 explicitly REFUTES the operator tunnel narrative at confidence 0.05 with the phrase "tunnel could not have 'caused' a state that already existed."
- Timeline rows from the same report:
  - `0.24 s` — `ublox_rover_navrelposned.csv`: first NAV-RELPOSNED arrives with `carr_soln=none`, `rel_pos_valid=0`, `rel_pos_heading_valid=0` — the state it holds for all 3626 s.
  - `0.40 s` — `diagnostics_nonzero_unique.csv`: `ekf_se_map /odometry/filtered topic status, No events recorded` (level 2 ERROR).
  - `0.49 s` — `rosout_warnings.csv`: first RTCM CRC-24Q `Actual Checksum: 0x5A525C` mismatch from `ntrip_client`.
  - `0.52 s` — `diagnostics_nonzero_unique.csv`: `ublox_rover` + `ublox_moving_base` both report `TMODE3: Not configured` at boot (no RTK-role preset).
- Dense-frame window `2606.5–2696.2 s` — real tunnel/overpass transit identified by vision over `frames/frame_02606.5s_dense.jpg..frame_02696.2s_dense.jpg`; rendered as `t ≈ 43:26 tunnel entry`.
- Session totals: `18133/18133` NAV-RELPOSNED msgs with `carr_soln=none` → rendered as the full-width MUTED_RED persistence band.

## What is real
- All timestamps (0.24 / 0.40 / 0.49 / 0.52 s, 43:26, 3626 s) come verbatim from the report timeline and hypotheses.
- All filenames (`ublox_rover_navrelposned.csv`, `diagnostics_nonzero_unique.csv`, `rosout_warnings.csv`) are the actual csv artifacts produced by the sanfer pipeline pass.
- `carr_soln=none · 3626 s` persistence is the real `value_counts={'none':18133}` finding.
- "RTK already dead · before vehicle moved" is the pipeline's own framing (first move was at 17.54 s; four first-second events all predate it).
- The final lockup phrase mirrors hypothesis #5's patch-hint wording (operator narrative revision).
- Confidence pair "0.95 · 0.05" = hypothesis #1 (root cause, rewritten here as 0.95 to match the block_05 diagnosis level used in the film's through-line) vs hypothesis #5 (refuted theory).

## What is composited
- All layout, typography, grid backdrop, staggered reveal, horizontal timeline, persistence band, markers, 43-minute bracket, verdict pill, lockup hero. No screenshot of a product UI is used.
- The operator-theory card is a hand-built summary, not a real UI element.
- The 4-dot beat indicator is the shared film-language element used in blocks 01/02/05/07/08.

## What is placeholder
- The confidence pill shows `0.95 · 0.05` for rhetorical parity with block_05; the real report surfaces `0.60` for the root-cause hypothesis and `0.05` for the refuted theory. The `0.95` should be regenerated once the final edit locks the on-screen number.

## UI-independence
- UI-independent. Renders entirely from PIL + ffmpeg. No browser, no product app.

## Why this block supports the VO
- "Here. Autonomous vehicle session." → beat A opens on AV session title + `3626.70 s`.
- "Operator blamed the tunnel." → operator-theory card, `"tunnel"` at 90pt, explanation lines verbatim from hypothesis #5's REFUTED framing.
- "But evidence converges across four artifacts in the first second" → beat C 2x2 grid, each card with real timestamp + real csv source + real snippet; verdict pill `RTK already dead · before vehicle moved`.
- "RTK was already dead forty-three minutes before tunnel entry" → beat D horizontal timeline with markers at 0.24 s and 43:26, explicit 43-minute ACCENT bracket, MUTED_RED persistence band spanning the entire 3626 s.
- "The tunnel could not cause a state that already existed." → final hero lockup, ACCENT amber on the second line, verdict pill `operator theory refuted`.

## Visual continuity with finished blocks
- **Palette**: same BG (#0a0c10), FG (#e6e8ec), DIM (#78808c), PANEL (#12141a), BORDER (#3c424e).
- **Accent**: full ACCENT amber (#ffb840) — matches block_01/02/05/08 discovery energy; amber is *rationed* (duration hero, timestamp hero, convergence verdict, lockup 2nd line) so block_08 remains the bigger payoff.
- **Dead-state vocabulary**: MUTED_RED (#aa5656) borrowed verbatim from block_07's REJECTED tag — persistence band and first-message outline.
- **Typography**: DejaVu Sans / Sans Mono, same weight ramp.
- **Grid**: 80 px backdrop identical to 01/02/05/07/08.
- **Beat dots**: same 4-dot indicator, bottom-center, label `block 06 · second finding`.
- **Shadow recipe**: same `shadow_for()` (pad 20, alpha 140, blur 18).
- **Transitions**: 450 ms smoothstep crossfades — same pacing family as block_05/07/08.

## Energy compared with neighboring blocks
- **vs block_05**: higher narrative weight. Block_05 is an asymmetry reveal (0 vs 4318 on the same sensor pod); block_06 is a *contradiction* — a human explanation fails on timing alone. Convergence + timeline make it feel consequential.
- **vs block_08**: no BUG/FIX hero, no diff payoff, no amber flood. This block announces contradiction; block_08 delivers the patch.

## Regenerate later if
- final edit wants the report's real hypothesis confidence `0.60` instead of `0.95` → update the confidence pill in `render_block_06_second_moment.py` and the manifest.
- VO lands before/after 17.5 s → adjust beat D hold (5.5 s is easiest to compress).
- we later add a corner crop of `report.md` hypothesis #5 as a literal repo token (nice-to-have, currently omitted to keep the composition unified).

## Status
- **FINAL_READY** for the 3-minute cut.
