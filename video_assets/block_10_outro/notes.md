# block_10_outro — notes

## Repo reference used
- `github.com/LucasErcolano/BlackBox` — taken verbatim from the CI badge in `README.md` (`https://github.com/LucasErcolano/BlackBox/actions/workflows/ci.yml/badge.svg`). This is the canonical public URL of the project.

## Benchmark reference used
- `black-box-bench/` — real sibling package inside the repo. Its own `README.md` describes it as MIT-licensed "benchmark suite for robot forensic-analysis agents" and "Companion to Black Box". Rendered on-screen as `black-box-bench/ · MIT` to keep the path readable without a URL (the benchmark currently ships inside the main repo, not as a separate GitHub project).

## What is real
- Repo URL (from README badge).
- Benchmark path and MIT label (from `black-box-bench/README.md` and `black-box-bench/LICENSE`).
- Project tagline `forensic copilot for robots` — first line of `CLAUDE.md`.
- Palette, fonts, grid, beat-dot indicator — all reused verbatim from blocks 01/02/05/06/07/08/09.

## What is composited
- Layout, typography, two-column repo/benchmark band, ACCENT hairlines, vignette, timings. No UI screenshot, no dashboard, no synthetic artwork.
- Beat-dot indicator shows dot #4 active (final beat of the film) and fades out at t=8.5s — a deliberate end-of-film signal; the dots otherwise follow the same geometry used in earlier blocks.
- Ambient top/bottom vignette is new-in-this-block but additive only, not a new visual system.

## What is placeholder
- None of the on-screen text is placeholder. Every label, URL, and path is either real or a project-level tagline already used in `CLAUDE.md` / `README.md`.
- If the final edit wants the repo URL rendered with a visible protocol prefix (`https://`) or a QR code in the corner, that would be a layout addition, not a content change.

## Why this block supports the VO or silent ending
- "Open benchmark." → beat B left column reveals `benchmark  black-box-bench/ · MIT` at t=2.9 s.
- "Open repo." → beat B right column reveals `repo  github.com/LucasErcolano/BlackBox` at t=2.1 s.
- "Real forensic workflow." → beat C reveals the tagline `real forensic workflow` at t=4.7 s with ACCENT underline at t=5.2 s.
- Silent fallback: the composition reaches full-readable state by t≈6.5 s and holds motionless through t=9.5 s, so even with no voiceover the viewer reads brand → repo → benchmark → tagline in order and lands on a locked final frame.

## Visual continuity with finished blocks
- **Palette**: identical BG/FG/DIM/PANEL/BORDER/ACCENT/MUTED_AMBER to blocks 01/02/05/06/07/08/09.
- **Typography**: DejaVu Sans / Sans Mono, same weight ramp.
- **Grid**: same 80 px backdrop but at alpha 0.55 — deliberately quieter so the final card does not feel as "live" as an investigation beat.
- **Beat dots**: same 4-dot indicator, bottom-center, label `block 10 · outro`; dot #4 is the active one (end of film).
- **Amber rationing**: ACCENT amber used only on brand hairline, tagline underline, and the final beat-dot — continues block_06/09 discipline.
- **Motion**: no inter-beat crossfades; single continuous layered reveal. This is the only block in the film with no scene cuts — reinforcing "this is the end."

## Energy compared with neighboring blocks
- **vs block_09_punchline**: strictly quieter. Block_09 still has three cards, staggered reveals, and a lockup transition; block_10 is one composition that only *gains* elements, never replaces them. No investigation energy, no convergence.
- **vs block_01_hook**: mirror-bookend. Block_01 opens on "Black Box" as a question; block_10 closes on "Black Box" as a resolved claim.

## Regenerate later if
- editor prefers the URL rendered with `https://` prefix.
- editor wants a QR code linking to the repo in the corner of the locked frame.
- VO lands before/after 9.5 s → adjust tagline reveal timing (`T_TAGLINE` constant in the render script is the single knob).
- silent-outro decision is finalized → tagline underline amber sweep can be slowed down for more dwell.
- a subtle blurred still from block_06 timeline is preferred over the flat grid backdrop.

## Status
- **FINAL_READY** for the 3-minute cut. Works with or without VO.
