# SPDX-License-Identifier: MIT
"""Record /analyze?replay=sanfer_tunnel to mp4 via playwright + imageio_ffmpeg."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_DIR = Path("demo_assets/streaming/_frames")
OUT_MP4 = Path("demo_assets/streaming/replay_sanfer_tunnel.mp4")
URL = "http://127.0.0.1:8765/analyze?replay=sanfer_tunnel"
FPS = 10
DURATION_S = 120
WIDTH, HEIGHT = 1920, 1080


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p in OUT_DIR.glob("*.png"):
        p.unlink()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": WIDTH, "height": HEIGHT},
                                  device_scale_factor=1)
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded")

        n = FPS * DURATION_S
        dt = 1.0 / FPS
        t0 = time.monotonic()
        done_seen_at = None
        for i in range(n):
            target = t0 + (i + 1) * dt
            page.screenshot(path=str(OUT_DIR / f"f_{i:05d}.png"),
                            full_page=False, type="png")
            try:
                done = page.locator("a.link-report").count() > 0
            except Exception:
                done = False
            if done and done_seen_at is None:
                done_seen_at = i
            if done_seen_at is not None and i - done_seen_at >= FPS * 3:
                print(f"done at frame {done_seen_at}, cut after +3s tail", flush=True)
                break
            now = time.monotonic()
            if now < target:
                time.sleep(target - now)

        browser.close()

    frames = sorted(OUT_DIR.glob("*.png"))
    if not frames:
        print("no frames captured", file=sys.stderr)
        return 1
    print(f"captured {len(frames)} frames", flush=True)

    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y",
        "-framerate", str(FPS),
        "-i", str(OUT_DIR / "f_%05d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "20",
        "-preset", "medium",
        "-movflags", "+faststart",
        str(OUT_MP4),
    ]
    print(" ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:], file=sys.stderr)
        return r.returncode
    print(f"wrote {OUT_MP4} ({OUT_MP4.stat().st_size/1024:.1f} KB)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
