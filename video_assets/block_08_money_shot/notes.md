# block_08_money_shot — notes

## What is real
- Diff hunk hero: `localization/engage_gate.py` — extracted verbatim from `demo_assets/analyses/sanfer_tunnel.json` → `patch_proposal` field. Render script asserts the hunk is present in source before rendering.
- Evidence tie line ("rel_pos_heading_valid = 0 for 18,133 / 18,133 RTK samples") — real numbers from the same sanfer_tunnel.json timeline entry and hypothesis[0].evidence.
- Patch matches the RTK-heading finding surfaced by Black Box and referenced in the project memory (project_sanfer_finding.md).

## What is composited
- Dark grid backdrop, drop shadows, beat-dot indicator — shared visual identity with blocks 01/02/07.
- "scoped_patch.diff" card chrome (title bar, +8 −1 count) is a framing device around the real hunk.
- Beat A BUG tag, Beat C FIX tag, Beat D lockup text — narrative labels, not simulated UI.
- Beat C amber vertical strip on added lines — emphasis overlay only.

## What is placeholder
- None. All code shown is from the real `patch_proposal`. The condensed `ERROR` token on the broadcast line is a light formatting trim of the verbatim `DiagnosticStatus.ERROR` to keep the line legible at 32pt mono — same semantics.

## Why this supports the VO
- "This is the bug" → Beat A labels the bug + its evidence.
- "This is the fix. One scoped diff." → Beats B/C: one file, +8 −1, single hunk, diff as hero.
- "Not a redesign" → Beat D lockup states it verbatim; patch is additive guards on one function.
- "A targeted change tied directly to the evidence the system found" → Beat A evidence line + engage_gate surfaces the exact signal (rtk_heading_invalid) that block 07's gate would have preserved.

## Continuity with blocks 01, 02, 07
- Same palette (BG 10,12,16 / FG 230,232,236 / DIM 120,128,140).
- Same ACCENT amber (255,184,64) as blocks 01/02 — deliberate re-intensify after block_07 used desaturated MUTED_AMBER.
- Same DejaVu Sans / Sans Mono typography.
- Same 80px grid, same drop-shadow recipe, same 4-dot beat indicator (active=3 for the closing block).
- Same centered-lockup discipline from block_07's principle card (generous negative space, hairline divider, mono signature).
- XFADE 0.4s — between block_02's 0.35s (more energy) and block_07's 0.45s (clinical). Payoff should breathe but not drag.

## UI independence
- UI-independent. Zero dependency on the FastAPI/HTMX product UI. All assets rendered via PIL + ffmpeg from the on-disk analysis JSON.

## Final-ready or partial
- Final-ready for the current cut.

## What could be regenerated later
- If product UI ships a real diff viewer that matches this palette, swap the "scoped_patch.diff" card for a screen capture of that viewer for the same hunk.
- If the final sanfer analysis JSON is re-run with different wording in `patch_proposal`, rerun `scripts/render_block_08_money_shot.py` — it reads the JSON fresh.
- Minor: extend beat-C card vertical crop to show the trailing `return True` line, or shrink row height so all 8 added lines fit within the 1080p safe area.
