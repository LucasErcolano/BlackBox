# final_intro_outro — production notes

## Files

- `intro_card.mp4` — 4.0s, 1920x1080, 30 fps, h264 yuv420p, no audio
- `outro_card.mp4` — 6.0s, same spec
- `intro.png`, `outro.png` — single-frame stills for thumbnails / mobile preview

## Visual identity

Matches `src/black_box/ui/static/style.css` `:root` palette:
- `--bg` cream `#f3efe6`
- `--ink` `#14150f`
- `--muted` `#6e6c5e`
- `--rule` `#b8b09b`

Typography mirrors UI:
- Serif headline → DejaVu Serif Bold (IBM Plex Serif fallback; same metrics class)
- Sans subline → DejaVu Sans (IBM Plex Sans fallback)
- Mono support text → DejaVu Sans Mono (IBM Plex Mono fallback)

No glow, no gradients, no emojis. Thin 2 px hairlines only.

## Intro (4s)

- Headline: **BlackBox**
- Subline: Forensic copilot for robot failures
- Mono row: video · telemetry · tools · memory · patch
- Hairline beneath headline.

## Outro (6s)

- Hairline frame top + bottom (270 / 820 y).
- Headline: Robot forensics in minutes, for cents.
- Pillars: Open benchmark · Reproducible runs · Evidence-grounded.
- Repo: `github.com/LucasErcolano/BlackBox`
- Cost line: `bench: black-box-bench · cost ledger: data/costs.jsonl (283 calls, $53.13)` — pulled from `block_credibility_opus47/notes.md`.
- Footer: `Built with Opus 4.7`.

## Claims that depend on external artifacts

- `283 calls, $53.13` — depends on `data/costs.jsonl` snapshot used by Batch B. If ledger is regenerated with new totals, re-render `outro_card.mp4` with updated `/tmp/io/o4.txt`.
- `github.com/LucasErcolano/BlackBox` — repo URL. Update if repo moves.

## How to integrate with the 3-min cut

Concat order (when ready):
```
intro_card.mp4 (4s) → final_demo_3min_visual_only.mp4 (180s) → outro_card.mp4 (6s)
```
Total 190s. Above 3:00 cap — only use intro/outro as standalone bumpers, OR rebuild the 3-min cut budget with intro=4s and outro=6s carved from the existing block budgets (recommend trimming 2s from generalization montage and 8s from intake/setup if integrating).
