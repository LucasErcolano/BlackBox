# BlackBox demo · final delivery

## Status: reverted to v2 baseline

Hybrid v3 attempt (with two real-UI swaps) was rendered and reviewed. User found **two regressions** that broke visual cohesion:

1. **`06_patch_diff_ui.mp4`** at 1:44–1:57 — real `/report` UI renders in **light/white mode**, clashing with v2's dark theme; clip also re-shows the same `/report` page twice within the segment.
2. **`07_cases_archive_ui.mp4`** at 2:14–2:27 — real `/cases` archive also in **light/white mode**, same theme clash.

Both swap clips are real Playwright captures of the live FastAPI/HTMX UI, but the BlackBox UI itself ships in light mode. No dark-mode equivalent exists in `demo_assets/editor_raw_footage_pack/clips/`. Generating dark-mode variants would require modifying the UI stylesheet and re-running the capture pipeline (`capture_ui.py`).

Decision: ship `final_demo_pack/final_video_v2/blackbox_demo_final_v2.mp4` verbatim as the final deliverable. v2 was specifically called out by the user as the preferred baseline and already passes every documented hard gate.

## Final deliverable
- `final/blackbox_demo_final.mp4` — **= `final_demo_pack/final_video_v2/blackbox_demo_final_v2.mp4`** — 179.77s, 1920x1080@30, h264 + AAC silent stereo.
- `final/blackbox_demo_final_no_audio.mp4` — same video, no audio track.
- `final/blackbox_demo_final.srt` — caption track, 12 cues aligned to script beats.
- `final/timeline_final.json` — v2 timeline (13 segments, 0.35s xfade).

## Pre-existing v2 defects flagged by user (not fixed here)

These exist in v2 source block clips and require re-running the corresponding `scripts/render_block_NN.py`:

| User report | Likely block | Fix path |
|---|---|---|
| Frame 2, "raw evidence" excede pantalla | block_02_problem | `scripts/render_block_02_problem.py` — re-tighten right-edge bbox |
| Frame 3, diferencias muy pequeñas, white version | block_02 / block_03 | tighter trace tile |
| Frame 4, `pid_controller.cpp` excede caja en ambos paneles | block_02 / block_05 | wrap source-code lines or shrink font |
| Frame 5, scale muy cerca de la consola | block_03_setup or block_05 | spacing fix |
| Replay cost siempre en 0 | block_04_analysis_live_v2 | data binding bug; fix in render_block_04_analysis_live_v2.py |
| USV session metadata, `case`/`mode` overflow | block_03 setup | tighten metadata column width |
| AV session "throughout" smushed + overlaps operator-theory box | block_03 / block_06_second_moment | spacing/anchor fix |
| "But the data disagrees…" "before the vehicle.." pegado al `0.24s` | block_06_second_moment | gap between caption and timestamp |
| Block 09 "deliverable" flash 1s then reappears | block_09_punchline | timeline ordering bug in render script |
| Hybrid swaps light/white mode | 06_patch_diff_ui, 07_cases_archive_ui | reverted (this commit) |

## Re-render commands (for follow-up fixes)
```bash
# Each block clip is re-renderable in isolation
.venv/bin/python scripts/render_block_02_problem.py
.venv/bin/python scripts/render_block_03_setup.py
.venv/bin/python scripts/render_block_04_analysis_live_v2.py
.venv/bin/python scripts/render_block_06_second_moment.py
.venv/bin/python scripts/render_block_09_punchline.py
# Then re-run the v2 pipeline:
.venv/bin/python scripts/normalize_clips.py
.venv/bin/python scripts/trim_freezes.py
.venv/bin/python scripts/render_final_video.py
```

## Hybrid v3 archived for reference
- `drafts/hybrid/blackbox_demo_hybrid.mp4` — failed cohesion check; kept for diff/audit.
- `archaeology/asset_catalog.md`, `visual_lang/visual_language.md`, `production_ledger.md`, `scorecard_final.md`, `visual_qa_report.md` — competition artifacts retained.
