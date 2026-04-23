# block_03_setup — notes

## Session / case asset used
- `data/final_runs/sanfer_tunnel/` — the real sanfer_tunnel recording bundle. Same case referenced in project memory (`project_sanfer_finding.md`) and by block_08's hero patch. Using it here establishes the session *before* any analysis is shown; blocks 07/08 later pay it off.
- Specifically: `bundle/summary.json` (case, duration 3626.8s, Lincoln MKZ drive-by-wire / dual-antenna u-blox RTK, artifact list) and four real extracted frames from `bundle/frames/`.

## What is real
- The directory path `data/final_runs/sanfer_tunnel/bundle/` and the 14 listed filenames — verbatim `ls`-style output of the real bundle.
- Case name `sanfer_tunnel`, duration (60m 26s), platform string, artifact count — all read from `summary.json` at render time.
- Four frame thumbnails in beat C are the real on-disk `frame_00000.0s_dense.jpg`, `frame_00518.2s_base.jpg`, `frame_01036.3s_base.jpg`, `frame_02072.5s_base.jpg` — loaded from `bundle/frames/` and resized.
- CSV pill labels (`ublox_rover_navrelposned.csv`, `diagnostics_nonzero_unique.csv`, `rosout_warnings.csv`, `imu_1hz.csv`, `twist_20hz.csv`, `steering_20hz.csv`) are a subset of `SUMMARY["artifacts"]`.

## What is composited
- Dark grid backdrop, drop shadows, 4-dot beat indicator — shared visual identity with 01/02/07/08.
- Terminal card chrome (title bar with `$ ls …`) is a framing device around the real listing.
- "UNSEEN / no prior analysis" badge is a narrative label, not a system-emitted flag.
- `case_manifest.json` card in beat B is presented as a manifest view; the fields inside it are read from the real `summary.json`, but the "prior labels / prior rubric = none" rows are narrative assertions (they are true — there is no label file in the bundle — but they're stated, not extracted).
- Red strike-through on "no labels" / "no handcrafted rubric" is an emphasis overlay.

## What is placeholder
- None. All file names, frame images, and session facts are from the real bundle.

## Why this supports the VO
- "one session it has never seen before" → beat A lists the real bundle, badge = UNSEEN.
- "No labels. No handcrafted rubric." → beat B manifest rows state it; beat D strikes them through.
- "Just raw evidence." → beat C shows real frames + real telemetry CSV names.
- "find what matters, reject what doesn't, and return a grounded hypothesis" → final lockup, with `reject what doesn't · return a grounded hypothesis` sub-line.

## Continuity with blocks 01, 02, 07, 08
- Same palette (BG 10,12,16 / FG 230,232,236 / DIM 120,128,140 / PANEL 18,20,26 / BORDER 60,66,78).
- ACCENT amber (255,184,64) — same as 01/02/08, re-intensified from 07's MUTED_AMBER but used with restraint (hairlines, one badge, pill stripes, one divider), not as a hero color — diff hero stays in block_08.
- DejaVu Sans / Sans Mono typography.
- 80px grid_bg, same drop-shadow recipe, same 4-dot beat indicator (active=0 here).
- XFADE 0.38s — deliberately between block_02's 0.35s (energetic problem framing) and block_07's 0.45s (clinical austerity). Intake should feel intentional but keep forward momentum.
- Beat-dot label reads `block 03 · setup`, matching 07's `block 07 · grounding` and 08's equivalent.

## UI independence
- UI-independent. Zero dependency on the FastAPI/HTMX product UI. Everything is rendered from on-disk artifacts via PIL + ffmpeg.

## Final-ready or partial
- Final-ready for the current cut.

## What could be regenerated later
- If product UI ships a real "session picker", swap beat A's terminal-style listing for a capture of that picker pointed at the same bundle.
- If the `sanfer_tunnel/bundle/summary.json` gets re-exported with updated duration or platform, rerun `scripts/render_block_03_setup.py` — values are read fresh.
- Optional: swap the 4 chosen frames for a denser sampling if the final cut wants more "raw modality" feel — change `FRAME_PICKS` in the render script.
