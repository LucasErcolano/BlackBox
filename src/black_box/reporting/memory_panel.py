# SPDX-License-Identifier: MIT
"""Renderer for the 'Memory used' panel (#76).

Reads the deterministic JSON output of ``scripts/memory_loop_demo.py``
(or any equivalent two-run capture) and renders a sober HTML fragment
suitable for embedding in a report. The structure is intentionally
compact: one chain of evidence + a delta summary the operator can
verify at a glance.
"""
from __future__ import annotations

from html import escape
from typing import Any


def render_memory_used_panel(panel: dict[str, Any]) -> str:
    title = escape(panel.get("title", "Memory used"))
    subtitle = escape(panel.get("subtitle", ""))

    chain_html = "".join(
        f"<li><strong>From {escape(c.get('from_case',''))}</strong> "
        f"<em>{escape(c.get('prior_kind',''))}</em>: "
        f"<code>{escape(c.get('signature',''))}</code><br/>"
        f"<span>{escape(c.get('effect',''))}</span></li>"
        for c in panel.get("evidence_chain", [])
    )

    delta = panel.get("delta_summary", {})
    delta_html = (
        f"<table class='memory-delta'>"
        f"<thead><tr><th>without memory</th><th>with memory</th><th>changed?</th></tr></thead>"
        f"<tbody><tr>"
        f"<td><code>{escape(str(delta.get('without_memory_top','')))}</code></td>"
        f"<td><code>{escape(str(delta.get('with_memory_top','')))}</code></td>"
        f"<td>{'✓' if delta.get('changed') else '—'}</td>"
        f"</tr></tbody></table>"
    )

    primed = panel.get("primed_prompt_block_preview") or ""
    primed_html = (
        f"<details><summary>Primed prompt block</summary>"
        f"<pre><code>{escape(str(primed))}</code></pre></details>"
        if primed
        else ""
    )

    return (
        "<article class='memory-used-panel'>"
        f"<header><h3>{title}</h3>"
        f"{f'<p>{subtitle}</p>' if subtitle else ''}</header>"
        f"<ol class='memory-chain'>{chain_html}</ol>"
        f"{delta_html}"
        f"{primed_html}"
        "</article>"
    )
