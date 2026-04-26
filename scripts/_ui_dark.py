# SPDX-License-Identifier: MIT
"""Dark-mode CSS injection for Playwright UI captures.

Overrides the cream/IBM Plex palette in src/black_box/ui/static/style.css with
a near-black palette that matches the rest of the demo video aesthetic.
Persists across htmx swaps because the style tag lives in <head>.
"""
from __future__ import annotations

import json

DARK_CSS = """
:root {
  --bg: #0e0f0a !important;
  --bg-2: #15170f !important;
  --surface: #1d1f17 !important;
  --ink: #e8e3d4 !important;
  --ink-2: #cec9b8 !important;
  --muted: #9a9786 !important;
  --line: #2a2c22 !important;
  --rule: #3a3c30 !important;
  --accent-soft: #1f2e22 !important;
  --console-bg: #0a0b07 !important;
  --console-bg-2: #131509 !important;
}
html, body { background: #0e0f0a !important; color: #e8e3d4 !important; }
input, select, textarea, button { background: #1d1f17 !important; color: #e8e3d4 !important; border-color: #3a3c30 !important; }
table, th, td { border-color: #2a2c22 !important; }
"""

DARK_INIT_JS = """
(() => {
  const css = %s;
  const apply = () => {
    if (document.getElementById('bb-dark-style')) return;
    const s = document.createElement('style');
    s.id = 'bb-dark-style';
    s.textContent = css;
    (document.head || document.documentElement).appendChild(s);
  };
  if (document.readyState !== 'loading') apply();
  else document.addEventListener('DOMContentLoaded', apply);
})();
""" % json.dumps(DARK_CSS)
