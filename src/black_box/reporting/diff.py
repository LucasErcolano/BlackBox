"""Diff utilities for Black Box forensic reports."""
from __future__ import annotations

import difflib
import html
import re
from typing import Tuple


def unified_diff_str(
    old: str,
    new: str,
    old_path: str = "a",
    new_path: str = "b",
) -> str:
    """Return a unified diff between two text blobs using difflib."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    # Ensure trailing newline so diff output is well-formed.
    if old_lines and not old_lines[-1].endswith("\n"):
        old_lines[-1] += "\n"
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=old_path,
        tofile=new_path,
        lineterm="\n",
    )
    return "".join(diff)


def scoped_check(
    diff_text: str,
    max_hunks: int = 3,
    max_lines: int = 40,
) -> Tuple[bool, str]:
    """Check whether a unified diff is narrowly scoped.

    Returns (is_scoped, reason).
    """
    if not diff_text.strip():
        return True, "empty diff"

    hunks = 0
    changed = 0
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            hunks += 1
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+") or line.startswith("-"):
            changed += 1

    if hunks > max_hunks:
        return False, f"too many hunks: {hunks} > {max_hunks}"
    if changed > max_lines:
        return False, f"too many changed lines: {changed} > {max_lines}"
    return True, f"ok: {hunks} hunk(s), {changed} changed line(s)"


def side_by_side_html(old: str, new: str, title: str = "patch") -> str:
    """Produce a minimal self-contained side-by-side diff HTML document."""
    added_bg = "#e6ffed"
    removed_bg = "#ffeef0"

    sm = difflib.SequenceMatcher(a=old.splitlines(), b=new.splitlines())
    left_rows: list[tuple[str, str]] = []   # (bg, text)
    right_rows: list[tuple[str, str]] = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        a_chunk = old.splitlines()[i1:i2]
        b_chunk = new.splitlines()[j1:j2]
        if tag == "equal":
            for line in a_chunk:
                left_rows.append(("#ffffff", line))
                right_rows.append(("#ffffff", line))
        elif tag == "replace":
            n = max(len(a_chunk), len(b_chunk))
            for k in range(n):
                if k < len(a_chunk):
                    left_rows.append((removed_bg, a_chunk[k]))
                else:
                    left_rows.append(("#ffffff", ""))
                if k < len(b_chunk):
                    right_rows.append((added_bg, b_chunk[k]))
                else:
                    right_rows.append(("#ffffff", ""))
        elif tag == "delete":
            for line in a_chunk:
                left_rows.append((removed_bg, line))
                right_rows.append(("#ffffff", ""))
        elif tag == "insert":
            for line in b_chunk:
                left_rows.append(("#ffffff", ""))
                right_rows.append((added_bg, line))

    def render_cell(bg: str, text: str) -> str:
        return (
            f'<pre style="margin:0;padding:2px 6px;background:{bg};'
            f'font-family:monospace;white-space:pre-wrap;">'
            f'{html.escape(text) or "&nbsp;"}</pre>'
        )

    rows_html = []
    for (lbg, ltxt), (rbg, rtxt) in zip(left_rows, right_rows):
        rows_html.append(
            "<tr>"
            f'<td style="vertical-align:top;width:50%;border-right:1px solid #ddd;">'
            f"{render_cell(lbg, ltxt)}</td>"
            f'<td style="vertical-align:top;width:50%;">'
            f"{render_cell(rbg, rtxt)}</td>"
            "</tr>"
        )

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
</head>
<body style="font-family:sans-serif;margin:16px;">
<h1 style="font-family:serif;">{html.escape(title)}</h1>
<table style="border-collapse:collapse;width:100%;border:1px solid #ddd;font-size:12px;">
<thead>
<tr style="background:#f6f8fa;">
<th style="text-align:left;padding:4px 6px;border-bottom:1px solid #ddd;">before</th>
<th style="text-align:left;padding:4px 6px;border-bottom:1px solid #ddd;">after</th>
</tr>
</thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
<p style="color:#666;font-size:11px;">added bg {added_bg} &middot; removed bg {removed_bg}</p>
</body>
</html>
"""
    return doc


# ---------- demo-sized side-by-side renderer ----------

def parse_patch_proposal(text: str) -> Tuple[str, str, str]:
    """Extract (file_path, old, new) from a loose patch_proposal string.

    The schema stores patch_proposal as an informal pseudo-diff like:

        In pid.cpp, line 45:
        - integral += error;
        + integral += error;
        + integral = clamp(integral, -1, 1);

    This returns the file path (best-effort) plus the reconstructed old
    and new blobs so they can be fed to ``demo_side_by_side_html``. If no
    ``-``/``+`` lines exist, both blobs are empty.
    """
    path = "patch"
    old_lines: list[str] = []
    new_lines: list[str] = []

    m = re.match(r"\s*(?:In\s+)?([^\s:,]+)", text or "")
    if m:
        cand = m.group(1)
        if any(sep in cand for sep in (".", "/")):
            path = cand.rstrip(":,")

    for raw in (text or "").splitlines():
        if raw.startswith("+++") or raw.startswith("---") or raw.startswith("@@"):
            continue
        if raw.startswith("-"):
            old_lines.append(raw[1:].lstrip(" "))
        elif raw.startswith("+"):
            new_lines.append(raw[1:].lstrip(" "))
    return path, "\n".join(old_lines) + ("\n" if old_lines else ""), \
        "\n".join(new_lines) + ("\n" if new_lines else "")


def demo_side_by_side_html(
    old: str,
    new: str,
    file_path: str = "patch",
    case_key: str = "",
    title: str = "Proposed Fix",
) -> str:
    """Large-font side-by-side diff designed for the 2:00–2:20 demo beat.

    Same row-opcode logic as ``side_by_side_html`` but NTSB-styled: IBM Plex
    Serif header, monospace at 14px so it reads at 1080p, case banner, red
    accent on the title bar, muted green/red row backgrounds.
    """
    added_bg = "#eaf7ec"
    removed_bg = "#fbecec"
    added_marker = "#2f855a"
    removed_marker = "#b33"

    old_lines_all = old.splitlines()
    new_lines_all = new.splitlines()
    sm = difflib.SequenceMatcher(a=old_lines_all, b=new_lines_all)

    left_rows: list[tuple[str, str, str]] = []   # (bg, marker, text)
    right_rows: list[tuple[str, str, str]] = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        a_chunk = old_lines_all[i1:i2]
        b_chunk = new_lines_all[j1:j2]
        if tag == "equal":
            for line in a_chunk:
                left_rows.append(("#ffffff", " ", line))
                right_rows.append(("#ffffff", " ", line))
        elif tag == "replace":
            n = max(len(a_chunk), len(b_chunk))
            for k in range(n):
                if k < len(a_chunk):
                    left_rows.append((removed_bg, "−", a_chunk[k]))
                else:
                    left_rows.append(("#ffffff", " ", ""))
                if k < len(b_chunk):
                    right_rows.append((added_bg, "+", b_chunk[k]))
                else:
                    right_rows.append(("#ffffff", " ", ""))
        elif tag == "delete":
            for line in a_chunk:
                left_rows.append((removed_bg, "−", line))
                right_rows.append(("#ffffff", " ", ""))
        elif tag == "insert":
            for line in b_chunk:
                left_rows.append(("#ffffff", " ", ""))
                right_rows.append((added_bg, "+", line))

    def cell(bg: str, marker: str, text: str, marker_color: str) -> str:
        return (
            f'<pre style="margin:0;padding:4px 10px 4px 6px;background:{bg};'
            f"font-family:ui-monospace,SFMono-Regular,Menlo,monospace;"
            f'font-size:14px;line-height:1.45;white-space:pre;overflow-x:auto;'
            f'color:#1c1c1a;">'
            f'<span style="color:{marker_color};user-select:none;'
            f'display:inline-block;width:1em;">{marker}</span>'
            f'{html.escape(text) or "&nbsp;"}</pre>'
        )

    rows_html = []
    for i, ((lbg, lmark, ltxt), (rbg, rmark, rtxt)) in enumerate(zip(left_rows, right_rows)):
        ln_l = i + 1
        ln_r = i + 1
        rows_html.append(
            "<tr>"
            f'<td class="ln">{ln_l}</td>'
            f'<td class="side left">{cell(lbg, lmark, ltxt, removed_marker)}</td>'
            f'<td class="ln">{ln_r}</td>'
            f'<td class="side right">{cell(rbg, rmark, rtxt, added_marker)}</td>'
            "</tr>"
        )

    case_tag = (
        f'<span style="color:#9a958a;font-family:ui-monospace,monospace;'
        f'font-size:12px;">CASE {html.escape(case_key)}</span>'
        if case_key else ""
    )

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(title)} — {html.escape(file_path)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:wght@400;600&family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
  html, body {{ margin: 0; padding: 0; background: #f6f4ef; color: #1c1c1a;
    font-family: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, sans-serif; }}
  main {{ max-width: 1180px; margin: 0 auto; padding: 2rem 1.5rem 3rem; }}
  .banner {{ display:flex; justify-content:space-between; align-items:baseline;
    border-bottom: 2px solid #1c1c1a; padding-bottom: 0.6rem; margin-bottom: 1.25rem; }}
  .banner h1 {{ font-family: "IBM Plex Serif", Georgia, serif; font-weight: 600;
    font-size: 1.6rem; margin: 0; }}
  .banner .sub {{ color: #b33; font-family: ui-monospace, monospace; font-size: 0.85rem;
    text-transform: uppercase; letter-spacing: 0.1em; }}
  .path {{ display:inline-block; background: #fffdf8; border: 1px solid #d9d6cc;
    padding: 0.35rem 0.7rem; border-radius: 3px; font-family: ui-monospace, monospace;
    font-size: 0.9rem; margin-bottom: 1rem; }}
  table.diff {{ border-collapse: collapse; width: 100%; background: #fffdf8;
    border: 1px solid #d9d6cc; border-radius: 4px; overflow: hidden; }}
  table.diff thead th {{ text-align: left; padding: 0.55rem 0.75rem;
    font-family: "IBM Plex Sans", sans-serif; font-size: 0.78rem;
    text-transform: uppercase; letter-spacing: 0.08em; color: #6b6b66;
    background: #f2efe6; border-bottom: 1px solid #d9d6cc; }}
  table.diff td.ln {{ width: 2.5em; text-align: right; padding: 0 8px; color: #a8a49a;
    font-family: ui-monospace, monospace; font-size: 12px;
    background: #faf8f2; border-right: 1px solid #eeeae0; user-select: none; }}
  table.diff td.side {{ vertical-align: top; }}
  table.diff td.side.left {{ border-right: 1px solid #eeeae0; }}
  .legend {{ margin-top: 0.9rem; color: #6b6b66; font-size: 0.82rem;
    font-family: ui-monospace, monospace; }}
  .legend .pill {{ display:inline-block; padding: 1px 8px; border-radius: 2px;
    margin-right: 6px; }}
</style>
</head>
<body>
<main>
  <div class="banner">
    <h1>{html.escape(title)}</h1>
    <span class="sub">BLACK BOX — FORENSIC DIFF</span>
  </div>
  <div class="path">{html.escape(file_path)}</div>
  <table class="diff">
    <thead>
      <tr>
        <th style="width:2.5em;"></th>
        <th>Before</th>
        <th style="width:2.5em;"></th>
        <th>After</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
  <div class="legend">
    <span class="pill" style="background:{removed_bg};color:{removed_marker};">− removed</span>
    <span class="pill" style="background:{added_bg};color:{added_marker};">+ added</span>
    &middot; {case_tag}
  </div>
</main>
</body>
</html>
"""
    return doc
