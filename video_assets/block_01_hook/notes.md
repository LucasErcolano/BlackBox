# block_01_hook — notes

## What is real
- Bag frame `frame_00133.4s_dense.jpg` — real frame extracted from `sanfer_tunnel` rosbag.
- RTK plot `moving_base_rover.png` — rendered from real UBX RTK telemetry; the same "carrSoln=NONE 100%" / "relPosValid never set" finding tracked in memory.
- Diff — exact `old`/`new` strings from `data/patches/054061f2c1f9.json` (PID integral + output clamp patch). Per-line + / - marks computed by comparing the two stanzas.

## What is composited
- Title card, right-side labels, progress dots, grid backdrop, drop shadows, ken-burns zoom, wipe-in reveal, amber highlight sweep, crossfades. All rendered in PIL.
- No alpha product UI. No dashboards. No fake "analysis" chrome.

## What is placeholder
- None. Every artifact on screen is either real repo data or repo-derived text.

## UI independence
- UI-independent: yes. Block renders entirely from files under `demo_assets/` and `data/patches/`. Zero dependency on the unfinished FastAPI/HTMX UI.

## Final-ready?
- Yes. Can drop straight into final edit as the opening 11s.

## What should wait for finished UI
- Nothing for this block. Later blocks ("live analysis", "upload flow") should use the finished UI when it lands; this hook shot does not need it.

## Regenerate later if
- Editorial picks a different hero case (swap `FRAME` / `PLOT` / `PATCH` constants in the render script).
- Brand kit lands and title typography should match.
- Narration reworded (update title text in `make_title_frame` + manifest).

## Reproduce
```
python3 scripts/render_block_01_hook.py
```
Outputs `video_assets/block_01_hook/{clip.mp4,preview.png}`.
