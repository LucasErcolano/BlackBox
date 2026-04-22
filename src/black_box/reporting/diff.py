"""Diff utilities for Black Box forensic reports."""
from __future__ import annotations

import difflib
import html
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
