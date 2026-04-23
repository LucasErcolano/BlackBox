# Streaming replay — recording

Screencast of `/analyze?replay=sanfer_tunnel` showing forensic-reasoning stream from `queued` → `done`.

Shipped: `replay_sanfer_tunnel.mp4` — 1920×1080 H.264, 31.4s, 10 fps, yuv420p, ~1.1 MB.

Recorded via `scripts/record_replay.py` (playwright chromium headless + imageio-ffmpeg bundled ffmpeg binary). Run reproducibly:

```bash
# 1. Start UI
.venv/bin/uvicorn black_box.ui.app:app --host 127.0.0.1 --port 8765 &

# 2. Record
.venv/bin/python scripts/record_replay.py
# Captures frames until the "Download report" link appears + 3s tail, then
# encodes H.264 @ CRF 20, writes demo_assets/streaming/replay_sanfer_tunnel.mp4
```

Tune: `FPS`, `DURATION_S`, `WIDTH`, `HEIGHT` at the top of `scripts/record_replay.py`. Replay pacing is controlled by `REPLAY_SCALE=0.15` in `src/black_box/ui/app.py`.

## Fallback snapshot

`replay_mid.png` — offline mid-run composite of the shell + progress fragment. Use it if the video has encoding trouble on stream day.

## Stream source

`data/final_runs/sanfer_tunnel/stream_events.jsonl` — 138 events, span 711.98 s real-time. Scaled via `REPLAY_SCALE=0.15` with `REPLAY_MAX_SLEEP=0.8` clamp.
