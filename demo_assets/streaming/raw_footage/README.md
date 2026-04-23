# Raw footage — streaming replay

Unedited capture of `/analyze?replay=sanfer_tunnel` from page-load through `stage=done` + 3 s tail. Use for video editing, zoom crops, or re-encoding at different settings.

## Contents

| file | what | size | notes |
|------|------|-----:|-------|
| `frames/f_00000.png .. f_00325.png` | per-frame lossless PNG captures | ~24 MB total (326 frames, 15 fps) | 1920×1080, exactly what chromium-headless rendered |
| `replay_sanfer_tunnel_lossless.mp4` | H.264 CRF 0, yuv444p, preset veryslow | ~2.2 MB | Bit-exact from the PNG sequence — reference master |
| `replay_sanfer_tunnel_hq.mp4` | H.264 CRF 12, yuv420p, preset slow | ~1.6 MB | High-quality delivery format; plays in browsers/QuickTime |

The two mp4s compress so small because the UI is mostly static text/solid colors — H.264's intra + P-frame prediction eats it. No external bucket needed; everything fits in-repo.

## Relation to the "published" mp4

`../replay_sanfer_tunnel.mp4` (shipped in `demo_assets/streaming/`) is the 10-fps CRF-20 version used as the primary demo asset. If you want smoother motion or want to re-cut, start from `frames/` or `replay_sanfer_tunnel_lossless.mp4` here.

## Reproduce

```bash
# 1. Start UI
.venv/bin/uvicorn black_box.ui.app:app --host 127.0.0.1 --port 8765 &

# 2. Record raw
.venv/bin/python scripts/record_replay_raw.py
# Writes PNG frames + 2 mp4s into this directory.
```

Tune `FPS`, `DURATION_S`, `WIDTH`, `HEIGHT` at the top of `scripts/record_replay_raw.py`. Auto-stops 3 s after "Download report" link appears.
