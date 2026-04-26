# Capture notes

- App: `uvicorn black_box.ui.app:app --host 127.0.0.1 --port 8765`
- UI clips (01–08): Playwright Chromium, 1920x1080, device_scale_factor=1, headless. Driver: `_work/capture_ui.py`.
- Artifact clips (09, 12, 15–18): markdown→HTML wrapper rendered in same Playwright session, scrolled with `mouse.wheel`.
- PDF clip (11): `pdftoppm -r 144` → PNG pages → ffmpeg slideshow with subtle zoom.
- Slideshows (10, 13, 14, 19, 20): ffmpeg `-loop 1` + `zoompan` + `concat`. CRF 20, preset veryfast.
- All clips re-encoded to H.264 / yuv420p / 30fps via ffmpeg.
- No Remotion. No AI-generated terminal. No synthetic UI. All footage either is the live FastAPI/HTMX UI or a static asset already shipped in the repo.

## Reproduce
```
PYTHONPATH=src nohup python3 -m uvicorn black_box.ui.app:app --host 127.0.0.1 --port 8765 &
python3 demo_assets/editor_raw_footage_pack/_work/capture_ui.py
python3 demo_assets/editor_raw_footage_pack/_work/build_artifact_clips.py     # clips 09, 11, 12, 15-18
python3 demo_assets/editor_raw_footage_pack/_work/build_remaining.py          # clips 10, 13, 14, 19, 20
python3 demo_assets/editor_raw_footage_pack/_work/finalize_pack.py            # stills + sheets + manifest
```
