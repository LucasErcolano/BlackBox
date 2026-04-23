# Streaming replay — recording instructions

Goal: ~90s 1080p screencast of `/analyze?replay=sanfer_tunnel` showing the forensic-reasoning stream from `queued` → `done`.

Output target: `demo_assets/streaming/replay_sanfer_tunnel.mp4`

## Why this doc (and not the .mp4 directly)

Headless ffmpeg + headless Firefox screencast is unreliable on this machine:
- Firefox headless refuses offscreen frame capture ("Unable to open a connection to the X server" on `--screenshot` + no Xvfb available in sandbox).
- Chromium is not installed.
- `ffmpeg -f x11grab` needs a live X display, which this shell does not have.

Easiest path: record locally with Tella / OBS / Loom against a live FastAPI instance.

## Repro steps (local, ~2 min)

```bash
# 1. Terminal A — start the UI
cd /home/hz/Desktop/BlackBox
uvicorn black_box.ui.app:app --host 127.0.0.1 --port 8765

# 2. Browser — open at T=0 in your recorder
#    URL: http://127.0.0.1:8765/analyze?replay=sanfer_tunnel
#    The page loads pre-populated with an in-flight job_id.
#    htmx polls /status/<job_id> every 1s; progress bar + reasoning buffer
#    update live. Finishes ~85-95s after page load (REPLAY_SCALE=0.15 on
#    712s of real events, capped at 0.8s per sleep).

# 3. Record from page-load until stage "done" lights up + "Download report"
#    link appears. Framerate 30 fps. 1920x1080. Audio off.
```

## Recorder settings

| setting | value |
|---------|-------|
| resolution | 1920×1080 |
| fps | 30 |
| codec | H.264 (mp4) |
| crop | just the main column — hide browser chrome if the recorder supports it |
| duration | ~90s (stop ~2s after "Download report" is visible) |

## Fallback snapshot (already produced)

`replay_mid.png` — mid-run composite of the shell + progress fragment, captured offline.
Use it if the screencast has encoding trouble on video day.

## Stream source for the replay

`data/final_runs/sanfer_tunnel/stream_events.jsonl` — 138 events, span 711.98s real-time.
Scaled to ~107s demo-clock by `REPLAY_SCALE=0.15` in `src/black_box/ui/app.py`, with
`REPLAY_MAX_SLEEP=0.8` clamp so no single gap is longer than a TTS beat.
