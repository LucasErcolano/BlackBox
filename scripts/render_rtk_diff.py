# SPDX-License-Identifier: MIT
"""Render the sanfer RTK fix as a 3-panel NTSB-style side-by-side diff.

Matches hypothesis-0 patch proposal verbatim:
  - MB UART2: enable RTCM3 4072.0/4072.1 + MSM7 (1077/1087/1097/1127) + 1230
  - Rover UART2: CFG-UART2INPROT-RTCM3X = 1 so rover ingests the MB stream
  - Prelaunch watchdog: block drive until carr_soln in {float,fixed} for 10 s

Writes demo_assets/diff_viewer/moving_base_rover.{html,png,2x.png}. The PNG
is screenshotted via playwright; the 2x version is a 2.0x CSS-pixel-ratio
capture (not an upscale).
"""
from __future__ import annotations

import html as _html
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

OUT_DIR = Path("demo_assets/diff_viewer")
OUT_HTML = OUT_DIR / "moving_base_rover.html"
OUT_PNG = OUT_DIR / "moving_base_rover.png"
OUT_PNG_2X = OUT_DIR / "moving_base_rover_2x.png"


@dataclass
class Panel:
    path: str
    title: str
    before: list[str]
    after: list[str]


PANELS = [
    Panel(
        path="ublox_gps/config/moving_base.yaml",
        title="1 / 3 — MB UART2: emit carrier-phase to rover",
        before=[
            "# ublox_gps — moving-base receiver (ZED-F9P)",
            "device: /dev/ttyACM0",
            "frame_id: gps_mb",
            "rate: 8                  # Hz, drove 'Frequency too high' diag at 0.52 s then 'too low' at 195.39 s",
            "tmode3: 1                # survey-in -- wrong for a MOVING base, flagged by diagnostics",
            "dynamic_model: portable",
            "",
            "uart2:",
            "  baudrate: 115200",
            "  in_protocol:  ubx",
            "  out_protocol: ubx        # <-- MB was NOT emitting carrier-phase to the rover",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "publish:",
            "  nav:",
            "    relposned: true",
            "    pvt:       true",
        ],
        after=[
            "# ublox_gps — moving-base receiver (ZED-F9P)",
            "device: /dev/ttyACM0",
            "frame_id: gps_mb",
            "rate: 5                  # Hz, matches u-blox driver watchdog band for the fix topic",
            "tmode3: 0                # DISABLED -- moving base must not be in survey-in / fixed mode",
            "dynamic_model: portable",
            "",
            "uart2:",
            "  baudrate: 460800",
            "  in_protocol:  none",
            "  out_protocol: ubx+rtcm3",
            "",
            "  # Enable the messages the rover needs to form a carrier-phase baseline:",
            "  out_msgs:",
            "    - {id: UBX-RXM-RAWX,  rate: 1}",
            "    - {id: UBX-RXM-SFRBX, rate: 1}",
            "    - {id: RTCM3-4072.0,  rate: 1}   # u-blox moving-base reference station",
            "    - {id: RTCM3-4072.1,  rate: 1}",
            "    - {id: RTCM3-1077,    rate: 1}   # MSM7 GPS",
            "    - {id: RTCM3-1087,    rate: 1}   # MSM7 GLONASS",
            "    - {id: RTCM3-1097,    rate: 1}   # MSM7 Galileo",
            "    - {id: RTCM3-1127,    rate: 1}   # MSM7 BeiDou",
            "    - {id: RTCM3-1230,    rate: 10}  # GLONASS code-phase biases, 10 s",
            "",
            "publish:",
            "  nav:",
            "    relposned: true",
            "    pvt:       true",
        ],
    ),
    Panel(
        path="ublox_gps/config/rover.yaml",
        title="2 / 3 — Rover UART2: accept the RTCM3 carrier-phase stream",
        before=[
            "# ublox_gps — rover receiver (ZED-F9P)",
            "device: /dev/ttyACM1",
            "frame_id: gps_rover",
            "rate: 8                  # Hz",
            "dynamic_model: portable",
            "",
            "uart2:",
            "  baudrate: 115200",
            "  in_protocol:  ubx       # <-- rover refused inbound RTCM3, so carr_soln never left 'none'",
            "  out_protocol: none",
            "",
            "  # Missing: CFG-UART2INPROT-RTCM3X",
            "",
            "",
            "publish:",
            "  nav:",
            "    relposned: true",
            "    pvt:       true",
        ],
        after=[
            "# ublox_gps — rover receiver (ZED-F9P)",
            "device: /dev/ttyACM1",
            "frame_id: gps_rover",
            "rate: 8                  # Hz",
            "dynamic_model: portable",
            "",
            "uart2:",
            "  baudrate: 460800",
            "  in_protocol:  rtcm3     # ACCEPT inbound RTCM3 observations from the MB",
            "  out_protocol: none",
            "",
            "  cfg:",
            "    CFG-UART2INPROT-RTCM3X: 1",
            "    CFG-UART2INPROT-UBX:    1",
            "",
            "publish:",
            "  nav:",
            "    relposned: true       # now carries heading once baseline resolves",
            "    pvt:       true",
        ],
    ),
    Panel(
        path="autonomy/src/autonomy/prelaunch_watchdog.py",
        title="3 / 3 — Prelaunch watchdog: refuse to drive without RTK heading",
        before=[
            "# Prelaunch gate — EXISTING. Checks DBW handshake + EKF liveness,",
            "# but never inspects RTK state -> stack proceeds with carr_soln='none'.",
            "",
            "from .handshake import dbw_ready",
            "from .ekf import ekf_alive",
            "",
            "",
            "def ready_to_drive(msg_bus) -> bool:",
            "    if not dbw_ready(msg_bus):",
            "        return False",
            "    if not ekf_alive(msg_bus):",
            "        return False",
            "    return True",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ],
        after=[
            "# Prelaunch gate — UPDATED. Adds a latched RTK-baseline check so we",
            "# refuse to hand off to autonomy with rover carr_soln stuck at 'none'.",
            "",
            "from .handshake import dbw_ready",
            "from .ekf import ekf_alive",
            "from .ublox import CarrSoln, latest_navrelposned",
            "",
            "",
            "RTK_OK_SET = {CarrSoln.FLOAT, CarrSoln.FIXED}",
            "RTK_STABLE_WINDOW_S = 10.0",
            "",
            "",
            "def ready_to_drive(msg_bus) -> bool:",
            "    if not dbw_ready(msg_bus):",
            "        return False",
            "    if not ekf_alive(msg_bus):",
            "        return False",
            "    rp = latest_navrelposned(msg_bus, window_s=RTK_STABLE_WINDOW_S)",
            "    if rp is None or rp.carr_soln not in RTK_OK_SET:",
            "        return False",
            "    if not rp.rel_pos_heading_valid:",
            "        return False",
            "    return True",
        ],
    ),
]


def _render_panel(p: Panel) -> str:
    rows = []
    max_lines = max(len(p.before), len(p.after))
    for i in range(max_lines):
        l = p.before[i] if i < len(p.before) else ""
        r = p.after[i] if i < len(p.after) else ""
        changed = l != r
        left_bg = "#fbecec" if changed and l else "#ffffff"
        right_bg = "#eaf7ec" if changed and r else "#ffffff"
        left_marker = "−" if changed and l else " "
        right_marker = "+" if changed and r else " "
        left_color = "#b33" if changed and l else "#a8a49a"
        right_color = "#2f855a" if changed and r else "#a8a49a"

        def _cell(marker: str, bg: str, marker_color: str, text: str) -> str:
            text_html = _html.escape(text) if text else "&nbsp;"
            return (
                f'<td class="side"><pre style="margin:0;padding:4px 10px 4px 6px;'
                f'background:{bg};font-family:ui-monospace,SFMono-Regular,Menlo,monospace;'
                f'font-size:14px;line-height:1.45;white-space:pre;overflow-x:auto;color:#1c1c1a;">'
                f'<span style="color:{marker_color};user-select:none;display:inline-block;width:1em;">'
                f'{marker}</span>{text_html}</pre></td>'
            )

        rows.append(
            f'<tr><td class="ln">{i+1}</td>'
            + _cell(left_marker, left_bg, left_color, l)
            + f'<td class="ln">{i+1}</td>'
            + _cell(right_marker, right_bg, right_color, r)
            + "</tr>"
        )
    return (
        f'<h2 class="panel-title">{_html.escape(p.title)}</h2>'
        f'<div class="path">{_html.escape(p.path)}</div>'
        '<table class="diff"><thead><tr>'
        '<th style="width:2.5em;"></th><th>Before</th>'
        '<th style="width:2.5em;"></th><th>After</th>'
        '</tr></thead><tbody>'
        + "".join(rows) +
        "</tbody></table>"
    )


def main() -> int:
    panels_html = "\n".join(_render_panel(p) for p in PANELS)
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Proposed Fix — enable MB↔rover carrier-phase baseline — sanfer_tunnel</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:wght@400;600&family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
  html, body {{ margin: 0; padding: 0; background: #f6f4ef; color: #1c1c1a;
    font-family: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, sans-serif; }}
  main {{ max-width: 1180px; margin: 0 auto; padding: 2rem 1.5rem 3rem; }}
  .banner {{ display:flex; justify-content:space-between; align-items:baseline;
    border-bottom: 2px solid #1c1c1a; padding-bottom: 0.6rem; margin-bottom: 0.9rem; }}
  .banner h1 {{ font-family: "IBM Plex Serif", Georgia, serif; font-weight: 600;
    font-size: 1.5rem; margin: 0; }}
  .banner .sub {{ color: #b33; font-family: ui-monospace, monospace; font-size: 0.85rem;
    text-transform: uppercase; letter-spacing: 0.1em; }}
  h2.panel-title {{ font-family: "IBM Plex Serif", Georgia, serif; font-weight: 600;
    font-size: 1.05rem; color: #1c1c1a; margin: 1.6rem 0 0.4rem; }}
  .path {{ display:inline-block; background: #fffdf8; border: 1px solid #d9d6cc;
    padding: 0.3rem 0.65rem; border-radius: 3px; font-family: ui-monospace, monospace;
    font-size: 0.85rem; margin-bottom: 0.75rem; }}
  table.diff {{ border-collapse: collapse; width: 100%; background: #fffdf8;
    border: 1px solid #d9d6cc; border-radius: 4px; overflow: hidden; }}
  table.diff thead th {{ text-align: left; padding: 0.5rem 0.75rem;
    font-family: "IBM Plex Sans", sans-serif; font-size: 0.75rem;
    text-transform: uppercase; letter-spacing: 0.08em; color: #6b6b66;
    background: #f2efe6; border-bottom: 1px solid #d9d6cc; }}
  table.diff td.ln {{ width: 2.5em; text-align: right; padding: 0 8px; color: #a8a49a;
    font-family: ui-monospace, monospace; font-size: 12px;
    background: #faf8f2; border-right: 1px solid #eeeae0; user-select: none; }}
  table.diff td.side {{ vertical-align: top; }}
  .legend {{ margin-top: 1rem; color: #6b6b66; font-size: 0.82rem;
    font-family: ui-monospace, monospace; }}
  .legend .pill {{ display:inline-block; padding: 1px 8px; border-radius: 2px;
    margin-right: 6px; }}
  .caption {{ color: #6b6b66; font-size: 0.82rem; font-family: ui-monospace, monospace;
    margin-top: 0.4rem; }}
</style>
</head>
<body>
<main>
  <div class="banner">
    <h1>Proposed Fix — enable MB↔rover carrier-phase baseline</h1>
    <span class="sub">BLACK BOX — FORENSIC DIFF</span>
  </div>
  <div class="caption">Root cause: moving-baseline RTCM uplink silently dead for the whole session —
  rover carr_soln never left 'none' (18 133/18 133 NAV-RELPOSNED messages). Patch scoped to driver
  config + a prelaunch gate; no architectural rewrites.</div>
  {panels_html}
  <div class="legend">
    <span class="pill" style="background:#fbecec;color:#b33;">− removed</span>
    <span class="pill" style="background:#eaf7ec;color:#2f855a;">+ added</span>
    &middot; <span style="color:#9a958a;font-family:ui-monospace,monospace;font-size:12px;">CASE sanfer_tunnel</span>
  </div>
</main>
</body>
</html>
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(doc)
    print(f"wrote {OUT_HTML}")

    # Render PNGs via playwright (1x + 2x device scale).
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"playwright not available: {e}", file=sys.stderr)
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for out_png, dsr in [(OUT_PNG, 1), (OUT_PNG_2X, 2)]:
            ctx = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=dsr,
            )
            page = ctx.new_page()
            page.goto(OUT_HTML.absolute().as_uri(), wait_until="networkidle")
            page.wait_for_timeout(400)
            page.screenshot(path=str(out_png), full_page=True, type="png")
            ctx.close()
            print(f"wrote {out_png} ({out_png.stat().st_size//1024} KB, dsr={dsr})")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
