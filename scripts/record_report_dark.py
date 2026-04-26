"""Record /report in DARK mode by injecting CSS vars at load time."""
from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

from playwright.async_api import async_playwright

OUT_DIR = Path("/tmp/bb_vo/playwright_video_dark")
URL = "http://127.0.0.1:8765/report?case=sanfer_tunnel"

DARK_OVERRIDE = """
:root {
  --bg:      #0a0c10 !important;
  --bg-2:    #11151b !important;
  --surface: #11151b !important;
  --ink:     #e7eaee !important;
  --ink-2:   #cfd5dd !important;
  --muted:   #7a8290 !important;
  --line:    #232831 !important;
  --rule:    #2c333d !important;
  --accent:      #62d4c8 !important;
  --accent-deep: #4cbab0 !important;
  --accent-soft: #1a2f2c !important;
  --signal-amber: #ffb840 !important;
  --signal-green: #62d4c8 !important;
  --signal-red:   #e0625a !important;
}
html, body {
  background: #0a0c10 !important;
  background-image: none !important;
  color: #e7eaee !important;
}
.card, .exhibit, .drop, .chip {
  background: #11151b !important;
  border-color: #232831 !important;
  color: #e7eaee !important;
}
.chip.is-accent { background: #1a2f2c !important; color: #62d4c8 !important; border-color: #2c4a45 !important; }
.btn { background: #62d4c8 !important; color: #0a0c10 !important; border-color: #62d4c8 !important; }
.btn:hover { background: #4cbab0 !important; }
.btn-ghost { background: transparent !important; color: #e7eaee !important; border-color: #2c333d !important; }
button.tab { color: #7a8290 !important; }
button.tab.is-on { color: #e7eaee !important; border-bottom-color: #62d4c8 !important; }
.diff-line.add { background: rgba(98, 212, 200, 0.12) !important; color: #c9efe9 !important; }
.diff-line.del { background: rgba(224, 98, 90, 0.12) !important; color: #e7c5c2 !important; }
.diff-line { color: #cfd5dd !important; }
pre, code, .mono, .diff-line { color: #cfd5dd !important; }
.verdict-pill, .verdict-pill.confirmed, .verdict-pill.inconclusive { color: #ffb840 !important; }
hr { border-top-color: #232831 !important; }
input, textarea, select { background: #11151b !important; color: #e7eaee !important; border-color: #2c333d !important; }
"""


async def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(OUT_DIR),
            record_video_size={"width": 1920, "height": 1080},
            device_scale_factor=1,
            color_scheme="dark",
        )
        page = await context.new_page()
        await page.goto(URL, wait_until="domcontentloaded")
        await page.add_style_tag(content=DARK_OVERRIDE)
        await page.wait_for_selector("section.verdict")
        try:
            await page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass

        # 0.0-2.0s — rest on verdict banner
        await page.mouse.move(960, 250)
        await asyncio.sleep(2.0)

        # 2.0-3.2s — small scroll to settle chips/cta
        await page.evaluate("window.scrollBy({top: 240, behavior: 'smooth'})")
        await asyncio.sleep(1.2)

        # 3.2-5.5s — switch to Recommended patch tab
        await page.evaluate(
            """() => {
              document.querySelectorAll('button.tab').forEach(b => b.classList.remove('is-on'));
              const t = document.querySelector("button.tab[data-tab='patch']");
              if (t) t.classList.add('is-on');
              ['exhibits','patch','trace'].forEach(id => {
                const el = document.getElementById('tab-' + id);
                if (el) el.style.display = (id === 'patch') ? 'block' : 'none';
              });
              const tp = document.getElementById('tab-patch');
              if (tp) tp.scrollIntoView({behavior: 'smooth', block: 'start'});
            }"""
        )
        await asyncio.sleep(2.3)

        # 5.5-9.5s — slow scroll down through diff
        for _ in range(8):
            await page.evaluate("window.scrollBy({top: 110, behavior: 'smooth'})")
            await asyncio.sleep(0.5)

        # 9.5-11.5s — focus an added line
        await page.evaluate(
            """() => {
              const lines = document.querySelectorAll('#tab-patch .diff-line.add');
              if (lines.length) {
                const el = lines[Math.floor(lines.length/2)];
                el.scrollIntoView({behavior: 'smooth', block: 'center'});
                el.style.outline = '2px solid #ffb840';
                el.style.outlineOffset = '-2px';
              }
            }"""
        )
        await asyncio.sleep(2.0)

        # 11.5-13.0s — scroll to Append to ledger button
        await page.evaluate(
            """() => {
              const e = document.getElementById('append-ledger');
              if (e) {
                e.scrollIntoView({behavior: 'smooth', block: 'center'});
                e.style.boxShadow = '0 0 0 2px #ffb840';
              }
            }"""
        )
        await asyncio.sleep(1.5)

        # 13.0-14.5s — simulate click outcome
        await page.evaluate(
            """() => {
              const flash = document.getElementById('ledger-flash');
              if (flash) {
                flash.textContent = 'Appended · ledger row 0042 · sanfer_tunnel';
                flash.style.color = '#62d4c8';
              }
              const btn = document.getElementById('append-ledger');
              if (btn) {
                btn.style.transform = 'translateY(1px)';
                btn.textContent = 'Appended ✓';
              }
            }"""
        )
        await asyncio.sleep(1.5)

        await context.close()
        await browser.close()

    webm = next(OUT_DIR.glob("*.webm"), None)
    if webm is None:
        print("ERROR: no video produced", file=sys.stderr)
        sys.exit(1)
    print(str(webm))


if __name__ == "__main__":
    asyncio.run(main())
