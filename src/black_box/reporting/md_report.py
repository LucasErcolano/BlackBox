# SPDX-License-Identifier: MIT
"""Markdown forensic report builder.

Drop-in replacement for the reportlab PDF path. Output is GitHub-flavored
markdown: no layout engine, no label collisions, cheaply diffable. The
path argument can still be named `out_pdf` for API stability; suffix is
coerced to `.md`.
"""
from __future__ import annotations

import io
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _fmt_t(t_ns: Any) -> str:
    try:
        t = float(t_ns)
    except (TypeError, ValueError):
        return "—"
    s = t / 1e9
    if s < 60:
        return f"{s:7.2f} s"
    m, sec = divmod(s, 60)
    return f"{int(m):02d}:{sec:05.2f}"


def _md_escape_cell(s: Any) -> str:
    if s is None:
        return ""
    return str(s).replace("|", "\\|").replace("\n", " ").strip()


def _embed_png(img: Any) -> str | None:
    """Base64-inline a PIL image as a data URI. Returns markdown or None."""
    if img is None:
        return None
    try:
        buf = io.BytesIO()
        im = img.convert("RGB") if hasattr(img, "convert") else img
        im.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


def build_report(
    report_json: dict,
    artifacts: dict,
    out_pdf: Path,
    case_meta: dict,
) -> Path:
    """Build the forensic markdown report. Returns the output path."""
    out = Path(out_pdf)
    if out.suffix.lower() != ".md":
        out = out.with_suffix(".md")
    out.parent.mkdir(parents=True, exist_ok=True)

    case_key = case_meta.get("case_key", "unknown")
    mode_label = case_meta.get("mode", "post_mortem")
    hypotheses = list(report_json.get("hypotheses", []) or [])
    timeline = list(report_json.get("timeline", []) or [])

    lines: list[str] = []
    push = lines.append

    # ---------- Header ----------
    push(f"# Black Box — Forensic Report")
    push("")
    push(f"**Case:** `{case_key}` &nbsp;·&nbsp; **Mode:** `{mode_label}`  ")
    if case_meta.get("bag_path"):
        push(f"**Source:** `{case_meta['bag_path']}`  ")
    if case_meta.get("duration_s") is not None:
        push(f"**Duration:** {case_meta['duration_s']:.2f} s  ")
    push(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}  ")
    push(f"**Model:** `claude-opus-4-7` (inference-only)")
    push("")
    if hypotheses:
        first = hypotheses[0]
        one = first.get("summary") or first.get("bug_class") or ""
        push(f"> {one}")
    else:
        push("> Nothing anomalous detected.")
    push("")
    push("---")
    push("")

    # ---------- Executive summary ----------
    push("## Executive Summary")
    push("")
    if hypotheses:
        # root cause: explicit flag > highest confidence
        root_idx = 0
        best = -1.0
        for i, h in enumerate(hypotheses):
            if h.get("is_root_cause"):
                root_idx = i
                break
            c = float(h.get("confidence", 0.0) or 0.0)
            if c > best:
                best = c
                root_idx = i
        root_idx = report_json.get("root_cause_idx", root_idx)

        push("| # | bug class | confidence | summary |")
        push("|---|-----------|-----------:|---------|")
        for i, h in enumerate(hypotheses):
            tag = " **[ROOT CAUSE]**" if i == root_idx else ""
            bug = _md_escape_cell(h.get("bug_class", "unclassified"))
            conf = float(h.get("confidence", 0.0) or 0.0)
            bar_n = int(round(conf * 10))
            bar = "█" * bar_n + "░" * (10 - bar_n)
            summ = _md_escape_cell(h.get("summary", ""))
            push(f"| {i+1} | `{bug}`{tag} | `{bar}` {conf:.2f} | {summ} |")
        push("")
    else:
        push("_No hypotheses generated._")
        push("")

    # ---------- Timeline ----------
    if timeline:
        push("## Timeline")
        push("")
        push("| t | label | source |")
        push("|---|-------|--------|")
        for ev in timeline:
            push(
                f"| `{_fmt_t(ev.get('t_ns'))}` "
                f"| {_md_escape_cell(ev.get('label') or ev.get('name'))} "
                f"| {_md_escape_cell(ev.get('source', 'cross-view' if ev.get('cross_view') else ''))} |"
            )
        push("")

    # ---------- Hypotheses detail ----------
    if hypotheses:
        push("## Hypotheses — Detail")
        push("")
        for i, h in enumerate(hypotheses):
            bug = h.get("bug_class", "unclassified")
            conf = float(h.get("confidence", 0.0) or 0.0)
            push(f"### {i+1}. `{bug}` — confidence {conf:.2f}")
            push("")
            if h.get("summary"):
                push(h["summary"])
                push("")
            evidence = h.get("evidence") or []
            if evidence:
                push("**Evidence**")
                push("")
                for ev in evidence:
                    src = _md_escape_cell(ev.get("source", ""))
                    topic = _md_escape_cell(
                        ev.get("topic_or_file") or ev.get("topic") or ev.get("file") or ""
                    )
                    tns = ev.get("t_ns")
                    tstr = f" @ `{_fmt_t(tns)}`" if tns is not None else ""
                    snippet = str(ev.get("snippet", "")).replace("\n", " ")
                    push(f"- **{src}** · `{topic}`{tstr}")
                    if snippet:
                        push(f"  > {snippet}")
                push("")
            if h.get("patch_hint"):
                push(f"**Patch hint:** {h['patch_hint']}")
                push("")

    # ---------- Annotated frames ----------
    frames = [f for f in (artifacts.get("frames") or []) if f is not None][:6]
    if frames:
        push("## Annotated Frames")
        push("")
        for i, fr in enumerate(frames):
            uri = _embed_png(fr)
            if not uri:
                continue
            push(f"![frame-{i+1}]({uri})")
            push(f"_Figure {i+1}. Frame {i+1} (annotated)._")
            push("")

    # ---------- Plots ----------
    plots = [p for p in (artifacts.get("plots") or []) if p is not None][:3]
    if plots:
        push("## Telemetry")
        push("")
        for i, pl in enumerate(plots):
            uri = _embed_png(pl)
            if not uri:
                continue
            push(f"![plot-{i+1}]({uri})")
            push(f"_Plot {i+1}._")
            push("")

    # ---------- Patch ----------
    code_diff = (
        artifacts.get("code_diff")
        or report_json.get("patch_proposal")
    )
    if code_diff:
        push("## Proposed Patch")
        push("")
        push("```diff")
        push(str(code_diff).rstrip())
        push("```")
        push("")

    push("---")
    push("_Black Box · inference-only · Opus 4.7_")
    push("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out
