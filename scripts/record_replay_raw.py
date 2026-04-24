# SPDX-License-Identifier: MIT
"""Raw-footage recorder: keep PNG frames + produce lossless mp4."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

RAW_DIR = Path("demo_assets/streaming/raw_footage")
FRAMES_DIR = RAW_DIR / "frames"
OUT_LOSSLESS = RAW_DIR / "replay_sanfer_tunnel_lossless.mp4"
OUT_HQ = RAW_DIR / "replay_sanfer_tunnel_hq.mp4"
URL = "http://127.0.0.1:8765/analyze?replay=sanfer_tunnel"
FPS = 15
DURATION_S = 180
WIDTH, HEIGHT = 1920, 1080


def main() -> int:
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    for p in FRAMES_DIR.glob("*.png"):
        p.unlink()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1
        )
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded")

        n = FPS * DURATION_S
        dt = 1.0 / FPS
        t0 = time.monotonic()
        done_at = None
        for i in range(n):
            target = t0 + (i + 1) * dt
            page.screenshot(
                path=str(FRAMES_DIR / f"f_{i:05d}.png"),
                full_page=False, type="png",
            )
            try:
                if page.locator("a.link-report").count() > 0 and done_at is None:
                    done_at = i
            except Exception:
                pass
            if done_at is not None and i - done_at >= FPS * 3:
                print(f"done at frame {done_at}, cut after +3s tail", flush=True)
                break
            now = time.monotonic()
            if now < target:
                time.sleep(target - now)

        browser.close()

    frames = sorted(FRAMES_DIR.glob("*.png"))
    if not frames:
        print("no frames", file=sys.stderr)
        return 1
    total_png = sum(p.stat().st_size for p in frames)
    print(f"captured {len(frames)} PNG frames ({total_png/1024/1024:.1f} MB raw)",
          flush=True)

    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    def encode(out: Path, extra: list[str]) -> int:
        cmd = [ffmpeg, "-y", "-framerate", str(FPS),
               "-i", str(FRAMES_DIR / "f_%05d.png"),
               *extra, "-movflags", "+faststart", str(out)]
        print(" ".join(cmd), flush=True)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr[-1500:], file=sys.stderr)
            return r.returncode
        print(f"  -> {out.name} ({out.stat().st_size/1024/1024:.1f} MB)", flush=True)
        return 0

    if encode(OUT_LOSSLESS,
              ["-c:v", "libx264", "-preset", "veryslow", "-crf", "0",
               "-pix_fmt", "yuv444p"]):
        return 1
    if encode(OUT_HQ,
              ["-c:v", "libx264", "-preset", "slow", "-crf", "12",
               "-pix_fmt", "yuv420p"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
